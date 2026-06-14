"""Interactive wizard prompts for claude-setup."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import click

from .keys import AgeKeypair, SSHKeypair, generate_age_keypair, generate_ssh_keypair
from .config import GlobalConfig, GitAuthorConfig, build_config, config_to_toml
from .secrets import encrypt_string
from .loader import build_loader_zip
from .repos import RepoOutput, create_repo, fork_repo, gh_available, gh_authenticated


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SetupResult:
    age: AgeKeypair
    ssh: Optional[SSHKeypair]
    config: Optional[GlobalConfig]
    loader_zip: bytes
    secrets_repo: RepoOutput
    config_repo: Optional[RepoOutput]
    payload_url: Optional[str]
    mode: str               # "A" or "B"
    account_uuid: str       # only meaningful for Mode A
    github_username: str
    use_gh: bool
    # Mode A: values to put in Claude's instructions
    config_repo_url: Optional[str]
    # Mode B: values to put in Claude's instructions
    payload_repo_url: Optional[str]


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

def run_wizard(output_dir: Path) -> SetupResult:
    click.echo()
    click.secho("  claude-setup", bold=True)
    click.echo("  Bootstrap the claude loader fleet")
    click.echo()

    # ── Step 1: Use gh CLI? ─────────────────────────────────────────────────
    click.secho("[1/9] GitHub CLI (gh)", bold=True)
    if not gh_available():
        click.secho("      ✗ gh not found on PATH — repos will be saved as local git directories", fg="yellow")
        use_gh = False
    else:
        if not gh_authenticated():
            click.secho("      ✗ gh found but not authenticated — repos will be saved as local git directories", fg="yellow")
            click.echo("        Run `gh auth login` to authenticate and re-run setup.")
            use_gh = False
        else:
            click.secho("      ✓ gh CLI found and authenticated", fg="green")
            use_gh = click.confirm(
                "      Create repositories directly on GitHub using gh?",
                default=True,
            )
    click.echo()

    # ── Step 2: GitHub PAT ──────────────────────────────────────────────────
    click.secho("[2/9] GitHub PAT", bold=True)
    click.echo("      This will be encrypted and stored in claude-secrets.")
    pat = click.prompt("      PAT", hide_input=True)
    click.echo()

    # ── Step 3: GitHub username ─────────────────────────────────────────────
    click.secho("[3/9] GitHub username", bold=True)
    click.echo("      Default username for all accounts (can be overridden per-account in config).")
    github_username = click.prompt("      Username")
    click.echo()

    # ── Step 4: Loader mode ─────────────────────────────────────────────────
    click.secho("[4/9] Loader mode", bold=True)
    click.echo("      (A) Config-driven  — fleet management via claude-config repo")
    click.echo("          UUID and config-repo URL go into Claude's instructions.")
    click.echo("          Best for multiple accounts; change config without touching the loader.")
    click.echo("      (B) Hardcoded      — single account, simpler, no extra repo")
    click.echo("          Username and payload-repo URL go into Claude's instructions.")
    mode_raw = click.prompt("      Mode", type=click.Choice(["A", "B", "a", "b"]), default="A")
    mode = mode_raw.upper()
    click.echo()

    # ── Step 5: Git signing ─────────────────────────────────────────────────
    click.secho("[5/9] Git commit signing", bold=True)
    want_signing = click.confirm("      Enable commit signing?", default=False)
    git_signing_format = "gpg"
    if want_signing:
        fmt_raw = click.prompt(
            "      Signing format",
            type=click.Choice(["gpg", "ssh"]),
            default="gpg",
        )
        git_signing_format = fmt_raw
    click.echo()

    # ── Step 6: Git author identity ─────────────────────────────────────────
    click.secho("[6/9] Git author identity", bold=True)
    click.echo("      (1) Claude <claude@anthropic.com>")
    click.echo(f"      (2) {github_username} <{github_username}@users.noreply.github.com>")
    click.echo("      (3) Custom name and email")
    author_choice = click.prompt(
        "      Author",
        type=click.Choice(["1", "2", "3"]),
        default="1",
    )
    if author_choice == "1":
        git_author = GitAuthorConfig(name="Claude", email="claude@anthropic.com")
    elif author_choice == "2":
        git_author = GitAuthorConfig(
            name=github_username,
            email=f"{github_username}@users.noreply.github.com",
        )
    else:
        author_name = click.prompt("      Name")
        author_email = click.prompt("      Email")
        git_author = GitAuthorConfig(name=author_name, email=author_email)
    click.echo()

    # ── Step 7: Generate keys ───────────────────────────────────────────────
    click.secho("[7/9] Generating keys...", bold=True)
    age_keypair = generate_age_keypair()
    click.secho("      ✓ Age keypair generated", fg="green")

    ssh_keypair: Optional[SSHKeypair] = None
    if want_signing and git_signing_format == "ssh":
        ssh_keypair = generate_ssh_keypair()
        click.secho("      ✓ SSH signing key generated", fg="green")
    elif want_signing and git_signing_format == "gpg":
        click.secho("      ✗ GPG signing: you must supply your own GPG key", fg="yellow")
        click.echo("        The payload will configure git to use gpg.format=gpg.")
        click.echo("        Export your GPG private key armored and it will be stored in claude-secrets.")
        gpg_key_str = click.prompt("      GPG private key (armored, paste all lines)", hide_input=False)
    else:
        gpg_key_str = None
    click.echo()

    # ── Step 8: Encrypt secrets and create repos ────────────────────────────
    click.secho("[8/9] Encrypting secrets and creating repos...", bold=True)

    account_uuid = str(uuid.uuid4()) if mode == "A" else ""

    encrypted_pat = encrypt_string(pat, age_keypair.public_key)
    secrets_files: dict[str, bytes] = {
        "github-token.age": encrypted_pat,
    }

    if want_signing:
        if git_signing_format == "ssh" and ssh_keypair is not None:
            encrypted_signing = encrypt_string(
                ssh_keypair.private_pem.decode(), age_keypair.public_key
            )
        elif git_signing_format == "gpg":
            encrypted_signing = encrypt_string(gpg_key_str, age_keypair.public_key)
        else:
            encrypted_signing = None

        if encrypted_signing is not None:
            secrets_files["signing-key.age"] = encrypted_signing

    # claude-secrets (always)
    secrets_repo = create_repo(
        f"{github_username}/claude-secrets",
        secrets_files,
        private=True,
        description="claude loader encrypted secrets",
        use_gh=use_gh,
        output_dir=output_dir,
    )
    _print_repo_result(secrets_repo, "claude-secrets")

    # claude-config (Mode A only)
    config_repo: Optional[RepoOutput] = None
    config: Optional[GlobalConfig] = None
    config_repo_url: Optional[str] = None

    if mode == "A":
        config = build_config(
            github_username=github_username,
            uuid=account_uuid,
            signing_enabled=want_signing,
            git_signing_format=git_signing_format,
            git_author=git_author,
        )
        config_toml = config_to_toml(config)
        config_repo = create_repo(
            f"{github_username}/claude-config",
            {"config.toml": config_toml},
            private=False,
            description="claude loader fleet config",
            use_gh=use_gh,
            output_dir=output_dir,
        )
        _print_repo_result(config_repo, "claude-config")
        config_repo_url = (
            config_repo.url
            or f"https://github.com/{github_username}/claude-config"
        )

    # Fork or note claude-payload
    payload_url: Optional[str] = None
    payload_repo_url: Optional[str] = None
    if use_gh:
        try:
            payload_url = fork_repo("0x038b5c/claude-payload")
            click.secho(f"      ✓ Forked claude-payload → {payload_url}", fg="green")
            payload_repo_url = payload_url
        except Exception as e:
            click.secho(f"      ✗ Could not fork claude-payload: {e}", fg="yellow")
            click.echo("        Fork manually: https://github.com/0x038b5c/claude-payload/fork")
            payload_repo_url = f"https://github.com/{github_username}/claude-payload"
    else:
        click.secho("      ✗ gh not in use — fork claude-payload manually:", fg="yellow")
        click.echo("        https://github.com/0x038b5c/claude-payload/fork")
        payload_repo_url = f"https://github.com/{github_username}/claude-payload"

    click.echo()

    # ── Step 9: Build loader.zip ────────────────────────────────────────────
    click.secho("[9/9] Building loader.zip...", bold=True)

    loader_zip = build_loader_zip(age_keypair.private_key, mode=mode)
    click.secho("      ✓ loader.zip built", fg="green")
    click.echo()

    return SetupResult(
        age=age_keypair,
        ssh=ssh_keypair,
        config=config,
        loader_zip=loader_zip,
        secrets_repo=secrets_repo,
        config_repo=config_repo,
        payload_url=payload_url,
        mode=mode,
        account_uuid=account_uuid,
        github_username=github_username,
        use_gh=use_gh,
        config_repo_url=config_repo_url,
        payload_repo_url=payload_repo_url,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(result: SetupResult, output_dir: str) -> None:
    """Print the post-wizard summary."""
    click.echo()
    click.secho("━" * 60, fg="bright_black")
    click.secho("  Setup complete!", bold=True, fg="green")
    click.secho("━" * 60, fg="bright_black")
    click.echo()

    if result.mode == "A":
        click.secho("  Account UUID", bold=True)
        click.echo(f"    {result.account_uuid}")
        click.echo()

    click.secho("  Age public key  (save this to encrypt future secrets)", bold=True)
    click.echo(f"    {result.age.public_key}")
    click.echo()

    if result.ssh:
        click.secho("  SSH signing public key", bold=True)
        click.echo("    Add to: GitHub → Settings → SSH and GPG keys → New signing key")
        click.echo(f"    {result.ssh.public_ssh.decode().strip()}")
        click.echo()

    click.secho("  Output files", bold=True)
    click.echo(f"    {output_dir}/loader.zip")
    if result.secrets_repo.local_dir:
        click.echo(f"    {result.secrets_repo.local_dir}/  (push to GitHub manually)")
    if result.config_repo and result.config_repo.local_dir:
        click.echo(f"    {result.config_repo.local_dir}/  (push to GitHub manually)")
    click.echo()

    click.secho("  Next steps", bold=True)
    click.echo("    1. Upload loader.zip to Claude:")
    click.echo("       claude.ai → Customize → Skills → + → Create Skill → Upload Zip")
    click.echo()
    click.echo("    2. Add to Claude's instructions (Profile → Custom Instructions):")
    click.echo()

    _print_claude_instructions(result)

    click.echo()
    click.echo("    3. Start a new conversation — Claude will self-provision.")
    click.echo()

    if not result.payload_url:
        click.secho("  ⚠  Don't forget to fork claude-payload:", fg="yellow")
        click.echo("     https://github.com/0x038b5c/claude-payload/fork")
        click.echo()


def _print_claude_instructions(result: SetupResult) -> None:
    """Print the exact text to paste into Claude's Custom Instructions."""
    if result.mode == "A":
        invocation = (
            f"PYTHONPATH=/mnt/skills/user/loader python -m src.main "
            f"--uuid {result.account_uuid} "
            f"--config {result.config_repo_url}"
        )
    else:
        invocation = (
            f"PYTHONPATH=/mnt/skills/user/loader python -m src.main "
            f"--user {result.github_username}"
        )

    instructions = (
        "At the start of every conversation, before doing anything else,\n"
        "check the <available_skills> block in your context for a skill\n"
        "named loader and, if present, read its SKILL.md and invoke it\n"
        "using the following command:\n\n"
        f"  {invocation}"
    )
    click.secho(instructions, fg="cyan")


def _print_repo_result(repo: RepoOutput, label: str) -> None:
    if repo.via_gh:
        click.secho(f"      ✓ {label} → {repo.url}", fg="green")
    else:
        click.secho(f"      ✓ {label} saved to {repo.local_dir}/", fg="green")
