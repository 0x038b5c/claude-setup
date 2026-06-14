# claude-setup Design Spec

## Overview

`claude-setup` is a CLI wizard that bootstraps the entire claude loader system for one
or more GitHub accounts. Running it produces:

1. A `loader.zip` (Claude skill) with the fleet age key baked in
2. A `claude-secrets` GitHub repo with encrypted secrets
3. Optionally a `claude-config` GitHub repo for fleet/multi-account management
4. A forked `claude-payload` repo under the user's GitHub account

The loader is intentionally thin and stable — it almost never needs to change.
All behaviour lives in payload and config.

---

## Loader Modes

`claude-setup` generates one of two loader variants at wizard time. The choice is
permanent for that loader (it is baked in at generation).

### Mode A — Config-driven (fleet mode)

Baked into loader:
- Fleet age key
- UUID for this account
- `claude-config` repo URL

Boot sequence:
```
loader
  → clone claude-config
  → lookup UUID → { github_username, payload_repo, secrets_repo, state_repo }
  → clone payload
  → run payload <github_username>
```

Use this when managing multiple Claude accounts or when you want to change
payload/secrets repo locations without regenerating the loader.

### Mode B — Hardcoded (simple mode)

Baked into loader:
- Fleet age key
- `github_username`
- `payload_repo` URL
- `secrets_repo` URL
- `state_repo` URL

Boot sequence:
```
loader
  → clone payload
  → run payload <github_username>
```

Use this for a single account with no need for fleet management. Simpler,
fewer moving parts, but changing any URL requires regenerating the loader.

---

## Repository Layout

### claude-secrets (always created)

```
claude-secrets/
  github-token.age          # default account PAT, armored
  signing-key.age           # optional SSH signing key, armored
```

Config can override secret paths to support additional accounts without UUID
directories:

```toml
[account.work]
github_token_secret = "github-token-work.age"
signing_key_secret  = "signing-key-work.age"
```

### claude-config (Mode A only)

```
claude-config/
  config.toml               # global defaults + per-UUID account entries
```

`config.toml` schema:

```toml
[global]
payload_repo    = "username/claude-payload"
secrets_repo    = "username/claude-secrets"
state_repo      = "username/claude-state"
signing_enabled = false

[account.<uuid>]
github_username = "alice"
# optional overrides:
payload_repo    = "alice/claude-payload"        # override global
signing_enabled = true
github_token_secret = "github-token.age"        # default, can omit
signing_key_secret  = "signing-key.age"         # default, can omit
```

The loader looks up its own UUID in `[account.<uuid>]` and merges with
`[global]` defaults (account wins on conflicts).

### claude-payload (forked per user)

The user's fork of `0x038b5c/claude-payload`. `claude-setup` forks it via the
GitHub API using the provided PAT.

`src/main.py` receives `github_username` as a required positional argument.
It uses this to determine which secrets to decrypt and which state repo to clone.

---

## Wizard Flow

```
$ python -m claude_setup

[1/7] Checking dependencies (age, gh, python cryptography, pyrage)...
[2/7] GitHub PAT: ********  (stored as secret, never written to disk unencrypted)
      Detected username: alice
[3/7] Loader mode?
        (A) Config-driven  — fleet management via claude-config repo
        (B) Hardcoded      — single account, simpler
[4/7] SSH signing key?
        (y) Generate a new Ed25519 signing key
        (n) Skip
[5/7] Generating keys...
      ✓ Age keypair generated
      ✓ SSH signing key generated  (if opted in)
[6/7] Creating repos...
      ✓ Forked claude-payload → alice/claude-payload
      ✓ Created claude-secrets, pushed encrypted secrets
      ✓ Created claude-config, pushed config  (Mode A only)
      ✓ Created claude-state (empty)
[7/7] Building loader.zip...
      ✓ Written to ./loader.zip

Next steps:
  1. Go to claude.ai → Customize → Skills → + → Create Skill → Upload Zip
  2. Add to Claude's instructions:
       At the start of every conversation, before doing anything else, check the
       <available_skills> block in your context for a skill named loader and, if
       present, immediately read and follow its SKILL.md without consulting any
       other files.
  3. Start a new conversation — Claude will self-provision on first message.

Age public key (keep this to encrypt future secrets):
  age1...

SSH public key (add to GitHub → Settings → SSH keys → Signing keys):
  ssh-ed25519 AAAA...
```

---

## Key Generation

### Age keypair

Generated with `pyrage`:

```python
from pyrage import x25519
identity = x25519.Identity.generate()
private_key = str(identity)          # AGE-SECRET-KEY-1...
public_key  = str(identity.to_public())  # age1...
```

The private key is baked into `loader/keys/age.key` (which becomes the zip).
The public key is used to encrypt all `.age` secrets and printed at the end
for the user to save.

### SSH signing key (optional)

Generated with `cryptography`:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)
key = Ed25519PrivateKey.generate()
private_pem = key.private_bytes(Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption())
public_ssh  = key.public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH)
```

The private key is encrypted with age (armored) and pushed to `claude-secrets`
as `signing-key.age`. The public key is printed for the user to add to GitHub.

### Secret encryption

All secrets are encrypted with age in armored format using pyrage ≥1.3.0, which
added `armored=` support in v1.3.0 (Jun 2025). No CLI tools required — pure Python:

```python
from pyrage import encrypt, x25519

def encrypt_secret(secret_bytes: bytes, public_key: str) -> bytes:
    """Encrypt secret_bytes to public_key, returning armored age ciphertext."""
    recipient = x25519.Recipient.from_str(public_key)
    return encrypt(secret_bytes, [recipient], armored=True)
    # returns b"-----BEGIN AGE ENCRYPTED FILE-----\n..."
```

---

## Loader Generation

The loader is built by:

1. Copying `claude-loader/` as a template
2. Writing the age private key to `keys/age.key`
3. Rendering `src/main.py` from a template (Jinja2 or simple str.replace)
   with mode-specific values baked in
4. Zipping the result → `loader.zip`

### Mode A main.py (rendered)

```python
UUID        = "<uuid>"
CONFIG_REPO = "https://github.com/<username>/claude-config.git"
```

Boot logic: clone config, lookup UUID, extract payload_repo + github_username,
clone payload, run `python -m src.main <github_username>`.

### Mode B main.py (rendered)

```python
GITHUB_USERNAME = "<username>"
PAYLOAD_REPO    = "https://github.com/<username>/claude-payload.git"
SECRETS_REPO    = "https://github.com/<username>/claude-secrets.git"
STATE_REPO      = "https://github.com/<username>/claude-state.git"
```

Boot logic: clone payload, run `python -m src.main <github_username>`.

---

## Project Structure

```
claude-setup/
  pyproject.toml
  README.md
  src/
    claude_setup/
      __init__.py
      __main__.py         # entry point, wizard orchestration
      keys.py             # age + SSH key generation
      secrets.py          # encryption helpers (wraps pyrage)
      repos.py            # GitHub repo creation, forking, pushing (wraps gh CLI)
      loader.py           # loader.zip assembly
      config.py           # config.toml read/write (tomllib / tomli-w)
      wizard.py           # interactive prompts (click or simple input())
      templates/
        main_mode_a.py.j2 # loader src/main.py template for Mode A
        main_mode_b.py.j2 # loader src/main.py template for Mode B
  tests/
    test_keys.py
    test_secrets.py
    test_loader.py
    test_config.py
```

---

## Dependencies

```toml
[project]
dependencies = [
  "pyrage>=1.3.0",    # age key generation + armored encryption (armor added in 1.3.0)
  "cryptography",     # SSH key generation
  "click",            # CLI prompts
  "tomli-w",          # write TOML (tomllib for reading is stdlib 3.11+)
  "jinja2",           # loader template rendering
]
```

`gh` CLI is **optional**. If present and authenticated, repos are created and pushed to GitHub directly. If absent, repo contents are saved as `.zip` files for the user to push manually. No `age` CLI required — encryption is handled entirely by pyrage.

---

## Security Notes

- The age private key is **never written to disk unencrypted** outside of `keys/age.key`
  inside the zip. It exists in memory only during the wizard run.
- The GitHub PAT is **never written to disk unencrypted**. It is encrypted
  immediately after entry and only the `.age` file is persisted.
- `claude-secrets` should be a **private** GitHub repo. `claude-setup` creates
  it as private via the API.
- `claude-config` can be public (it contains no secrets, only repo URLs and
  usernames) but defaults to private.
- SSH signing key private material is encrypted with age before leaving memory.

---

## Out of Scope

- Key rotation (future: `claude-setup rotate`)
- Adding a second account to an existing fleet (future: `claude-setup add-account`)
- Windows support (age + gh assumed to be on PATH in a Unix environment)
