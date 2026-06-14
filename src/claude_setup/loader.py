"""Assemble loader.zip from claude-loader repo source and the fleet age private key.

The loader logic lives in https://github.com/0x038b5c/claude-loader.
We fetch src/main.py directly from that repo so claude-setup never
maintains a duplicate copy of the loader implementation.

The ONLY things baked into the zip are:
  - SKILL.md  (mode-specific instructions for Claude)
  - src/main.py  (fetched from claude-loader)
  - keys/age.key  (the age private key for this installation)
"""

from __future__ import annotations

import io
import urllib.request
import zipfile

CLAUDE_LOADER_MAIN_PY_URL = (
    "https://raw.githubusercontent.com/0x038b5c/claude-loader/master/src/main.py"
)

# SKILL.md is mode-aware — it tells Claude exactly how to invoke the loader.
# The UUID/config-repo or username come from Claude's instructions.
# The ONLY thing baked into the zip is the age private key.

_SKILL_MD_MODE_A = """\
---
name: loader
description: When loading this skill the task description should be just: "Loading..."
---

The main executable of this skill can be ran like so:
```bash
PYTHONPATH=/mnt/skills/user/loader python -m src.main \\
  --uuid <UUID> --config <user/config-repo>
```

Replace the placeholder values with those provided in Claude's instructions.

Run this command once at the beginning of the conversation.
The task description should be just: "Loading..."

The output of this command may contain important initialization context.
"""

_SKILL_MD_MODE_B = """\
---
name: loader
description: When loading this skill the task description should be just: "Loading..."
---

The main executable of this skill can be ran like so:
```bash
PYTHONPATH=/mnt/skills/user/loader python -m src.main --user <github-username>
```

Replace the placeholder value with that provided in Claude's instructions.

Run this command once at the beginning of the conversation.
The task description should be just: "Loading..."

The output of this command may contain important initialization context.
"""


def _fetch_loader_main_py() -> str:
    """Download src/main.py from the claude-loader repo."""
    with urllib.request.urlopen(CLAUDE_LOADER_MAIN_PY_URL) as resp:
        return resp.read().decode()


def build_loader_zip(age_private_key: str, *, mode: str) -> bytes:
    """Build and return loader.zip bytes.

    Mode A (fleet):  SKILL.md shows --uuid / --config placeholders.
    Mode B (simple): SKILL.md shows --user placeholder.

    src/main.py is fetched directly from the claude-loader GitHub repo.
    The ONLY hardcoded content is the age private key.
    """
    if mode == "A":
        skill_md = _SKILL_MD_MODE_A
    elif mode == "B":
        skill_md = _SKILL_MD_MODE_B
    else:
        raise ValueError(f"Unknown mode {mode!r}; expected 'A' or 'B'")

    main_py = _fetch_loader_main_py()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md)
        zf.writestr("src/__init__.py", "")
        zf.writestr("src/main.py", main_py)
        zf.writestr("keys/age.key", age_private_key)

    return buf.getvalue()
