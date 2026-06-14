## What I was doing
Building claude-setup — a CLI wizard that bootstraps the claude loader fleet.

## What's done
- Design spec: docs/superpowers/specs/2026-06-13-claude-setup-design.md
- keys.py — age keypair + SSH keypair generation
- secrets.py — armored age encryption (pyrage>=1.3.0)
- config.py — GlobalConfig/AccountConfig dataclasses, TOML roundtrip
- loader.py — build_loader_zip() for Mode A and Mode B
- templates/main_mode_a.py.j2 — config-driven loader main.py
- templates/main_mode_b.py.j2 — hardcoded loader main.py
- repos.py — gh-optional repo creation (falls back to zip)
- wizard.py — full interactive wizard flow
- __main__.py — CLI entrypoint (click)
- README.md
- Full smoke test passing on all modules

## What's in flight
- Nothing

## What's next
- tests/ — unit tests for keys, secrets, config, loader
- repos.py: test the zip fallback path end to end
- Consider: `claude-setup rotate` subcommand for key rotation
- Consider: `claude-setup add-account` for adding a second account to a fleet
