"""GitHub repository management.

If the `gh` CLI is available, repos are created and pushed directly.
If not, repo contents are returned as zip bytes for the user to push manually.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Callable


def gh_available() -> bool:
    """Return True if the gh CLI is on PATH and authenticated."""
    if shutil.which("gh") is None:
        return False
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _run_gh(*args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh {' '.join(args)} failed:\n{result.stderr.strip()}"
        )
    return result


def _init_repo_zip(files: dict[str, bytes]) -> bytes:
    """Pack a flat dict of {filename: content} into a zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _push_repo_via_gh(
    repo_name: str,
    files: dict[str, bytes],
    private: bool,
    description: str,
) -> str:
    """Create a GitHub repo via gh CLI, commit files, push. Returns clone URL."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        subprocess.run(["git", "init", str(tmpdir)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmpdir), "checkout", "-b", "main"],
            check=True, capture_output=True,
        )

        for name, content in files.items():
            dest = tmpdir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

        subprocess.run(
            ["git", "-C", str(tmpdir), "add", "-A"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmpdir), "commit", "-m", "chore: initial setup via claude-setup"],
            check=True, capture_output=True,
        )

        vis = "--private" if private else "--public"
        _run_gh("repo", "create", repo_name, vis, "--description", description, "--push",
                "--source", str(tmpdir))

        result = _run_gh("repo", "view", repo_name, "--json", "url", "--jq", ".url")
        return result.stdout.strip()


def fork_repo(source: str, new_name: str | None = None) -> str:
    """Fork source (e.g. '0x038b5c/claude-payload') via gh. Returns new repo URL."""
    args = ["repo", "fork", source, "--clone=false"]
    if new_name:
        args += ["--fork-name", new_name]
    result = _run_gh(*args)
    # gh prints the new repo URL on success
    for line in result.stderr.splitlines() + result.stdout.splitlines():
        if "github.com" in line:
            return line.strip().split()[-1]
    # Fallback: derive URL from source + authenticated user
    whoami = _run_gh("api", "user", "--jq", ".login")
    username = whoami.stdout.strip()
    repo_part = new_name or source.split("/")[-1]
    return f"https://github.com/{username}/{repo_part}"


class RepoOutput:
    """Result of a repo creation — either a live URL or a zip of files to push."""

    def __init__(self, name: str, url: str | None, zip_bytes: bytes | None):
        self.name = name
        self.url = url           # set if gh was used
        self.zip_bytes = zip_bytes  # set if gh was not available

    @property
    def via_gh(self) -> bool:
        return self.url is not None

    def __repr__(self) -> str:
        if self.via_gh:
            return f"<RepoOutput {self.name!r} → {self.url}>"
        return f"<RepoOutput {self.name!r} (zip, {len(self.zip_bytes)} bytes)>"


def create_repo(
    name: str,
    files: dict[str, bytes],
    *,
    private: bool = True,
    description: str = "",
    use_gh: bool | None = None,
) -> RepoOutput:
    """Create a repo with the given files.

    If use_gh is None, auto-detect gh availability.
    If gh is available (or use_gh=True), creates and pushes to GitHub.
    Otherwise returns zip bytes for manual push.
    """
    if use_gh is None:
        use_gh = gh_available()

    if use_gh:
        url = _push_repo_via_gh(name, files, private=private, description=description)
        return RepoOutput(name=name, url=url, zip_bytes=None)
    else:
        return RepoOutput(
            name=name,
            url=None,
            zip_bytes=_init_repo_zip(files),
        )
