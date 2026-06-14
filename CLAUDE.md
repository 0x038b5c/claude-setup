# claude-setup

CLI wizard that bootstraps the claude loader system for one or more GitHub accounts.

## Structure

```
claude-setup/
  pyproject.toml                   # build config, deps: pyrage, cryptography, click, tomli-w, jinja2
  src/claude_setup/
    __main__.py                    # entry: runs wizard, writes loader.zip + optional repo zips
    wizard.py                      # interactive prompts, orchestrates all steps
    keys.py                        # age keypair + optional SSH signing key generation
    secrets.py                     # encrypt_string/encrypt_secret via pyrage (armored)
    repos.py                       # create_repo + fork_repo via gh CLI or zip fallback
    config.py                      # GlobalConfig + AccountConfig dataclasses, TOML read/write
    loader.py                      # build_loader_zip: assembles SKILL.md + src/main.py + age key
    templates/
      main_mode_a.py.j2            # Mode A loader: clones config, looks up UUID, runs payload
      main_mode_b.py.j2            # Mode B loader: hardcoded repos, runs payload directly
  docs/superpowers/plans/          # implementation plans
```

## Loader Modes

**Mode A (fleet):** bakes in age key + UUID + config_repo URL.
Boot: clone config → lookup UUID → get (github_username, payload_repo) → run payload.

**Mode B (simple):** bakes in age key + github_username + all repo URLs.
Boot: clone payload → run payload directly.

Both pass `github_username` to `python -m src.main <github_username>`.

## Related Repos

- `claude-payload` — cloned by loader at runtime; `src/main.py` accepts `github_username` as argv[1]
- `claude-secrets` — private repo with encrypted `.age` secrets per user
- `claude-config` — public repo with `config.toml` (Mode A only)
- `claude-state` — per-user state repo cloned by payload

## Notes

- pyrage ≥1.3.0 required (armored encryption added in Jun 2025)
- `gh` CLI optional; absent → repos returned as zip bytes for manual push
- age key lives in memory only during wizard; baked into loader.zip but never written to disk unencrypted elsewhere
