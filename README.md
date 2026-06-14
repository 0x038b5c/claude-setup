# claude-setup

Bootstrap the claude loader fleet for one or more GitHub accounts.

Running `claude-setup` once produces everything needed for Claude to
self-provision at the start of every conversation:

- **`loader.zip`** — Claude skill with the fleet age key baked in
- **`claude-secrets`** repo — GitHub PAT (and optionally SSH signing key),
  encrypted with age in armored format
- **`claude-config`** repo — fleet config mapping account UUIDs to GitHub
  usernames and payload repos (Mode A / fleet mode only)
- Forks **`claude-payload`** into your GitHub account

## Requirements

- Python ≥ 3.11
- `gh` CLI (optional — if absent, repos are saved as `.zip` files instead)

## Install

```bash
git clone https://github.com/0x038b5c/claude-setup
cd claude-setup
pip install -e .
```

## Usage

```bash
python -m claude_setup
# or, after pip install -e .:
claude-setup
```

Output files are written to the current directory by default:

```bash
claude-setup --output-dir ~/Desktop
```

## Loader modes

| Mode | What's baked into the loader | Best for |
|------|------------------------------|----------|
| **A** Config-driven | Age key + UUID + `claude-config` URL | Multiple accounts / fleet |
| **B** Hardcoded | Age key + username + all repo URLs | Single account, simpler |

In both modes the loader is thin and stable — it almost never needs updating.
All behaviour lives in `claude-payload` (shared) and `claude-config` (Mode A).

## After setup

1. Upload `loader.zip` to Claude:
   **claude.ai → Customize → Skills → + → Create Skill → Upload Zip**

2. Add to Claude's custom instructions:

   > At the start of every conversation, before doing anything else, check the
   > `<available_skills>` block in your context for a skill named `loader` and,
   > if present, immediately read and follow its `SKILL.md` without consulting
   > any other files.

3. Start a new conversation — Claude will self-provision.

## Key management

The age **private key** is baked into `loader.zip` — keep the zip safe.
The age **public key** is printed at the end of setup — save it to encrypt
future secrets (e.g. when rotating the GitHub PAT).

To encrypt a new secret manually:

```bash
echo -n "ghp_newtoken" | age --armor --recipient age1... > github-token.age
```

Then commit `github-token.age` to `claude-secrets`.
