"""GitHub repository management.

If `gh` CLI is available and the user opts to use it, repos are created and pushed directly.
Otherwise repo contents are saved as initialized bare git directories for the user to push manually.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# gh helpers
# ---------------------------------------------------------------------------

def gh_available() -> bool:
    """Return True if the gh CLI is on PATH."""
    return shutil.which("gh") is not None


def gh_authenticated() -> bool:
    """Return True if gh is on PATH and authenticated."""
    if not gh_available():
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


# ---------------------------------------------------------------------------
# Repo init helpers
# ---------------------------------------------------------------------------

def _init_local_repo(dest: Path, files: dict[str, bytes]) -> None:
    """Create an initialized git repo at dest with the given files committed."""
    dest.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "-b", "main", str(dest)], check=True, capture_output=True)

    for name, content in files.items():
        fpath = dest / name
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_bytes(content)

    subprocess.run(["git", "-C", str(dest), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(dest), "commit", "-m", "chore: initial setup via claude-setup"],
        check=True, capture_output=True,
    )


def _push_repo_via_gh(
    repo_name: str,
    files: dict[str, bytes],
    private: bool,
    description: str,
) -> str:
    """Create a GitHub repo via gh CLI, commit files, push. Returns clone URL."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        _init_local_repo(tmpdir, files)

        vis = "--private" if private else "--public"
        _run_gh(
            "repo", "create", repo_name, vis,
            "--description", description,
            "--push", "--source", str(tmpdir),
        )

        result = _run_gh("repo", "view", repo_name, "--json", "url", "--jq", ".url")
        return result.stdout.strip()


def fork_repo(source: str, new_name: str | None = None) -> str:
    """Fork source (e.g. '0x038b5c/claude-payload') via gh. Returns new repo URL."""
    args = ["repo", "fork", source, "--clone=false"]
    if new_name:
        args += ["--fork-name", new_name]
    result = _run_gh(*args)
    for line in result.stderr.splitlines() + result.stdout.splitlines():
        if "github.com" in line:
            return line.strip().split()[-1]
    whoami = _run_gh("api", "user", "--jq", ".login")
    username = whoami.stdout.strip()
    repo_part = new_name or source.split("/")[-1]
    return f"https://github.com/{username}/{repo_part}"


# ---------------------------------------------------------------------------
# RepoOutput
# ---------------------------------------------------------------------------

class RepoOutput:
    """Result of a repo creation."""

    def __init__(self, name: str, url: str | None, local_dir: Path | None):
        self.name = name
        self.url = url              # set if gh was used
        self.local_dir = local_dir  # set if gh was not used; initialized git repo on disk

    @property
    def via_gh(self) -> bool:
        return self.url is not None

    def __repr__(self) -> str:
        if self.via_gh:
            return f"<RepoOutput {self.name!r} → {self.url}>"
        return f"<RepoOutput {self.name!r} (local git dir: {self.local_dir})>"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_repo(
    name: str,
    files: dict[str, bytes],
    *,
    private: bool = True,
    description: str = "",
    use_gh: bool,
    output_dir: Path | None = None,
) -> RepoOutput:
    """Create a repo with the given files.

    If use_gh=True, creates and pushes to GitHub via gh CLI.
    Otherwise saves an initialized git repo to output_dir/<short-name>/.
    """
    if use_gh:
        url = _push_repo_via_gh(name, files, private=private, description=description)
        return RepoOutput(name=name, url=url, local_dir=None)
    else:
        short_name = name.split("/")[-1]
        dest = (output_dir or Path(".")) / short_name
        if dest.exists():
            shutil.rmtree(dest)
        _init_local_repo(dest, files)
        return RepoOutput(name=name, url=None, local_dir=dest)
