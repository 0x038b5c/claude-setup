"""Interactive wizard prompts for claude-setup."""

from __future__ import annotations

import uuid

import click

from .keys import AgeKeypair, SSHKeypair, generate_age_keypair, generate_ssh_keypair
from .config import GlobalConfig, build_config, config_to_toml
from .secrets import encrypt_string
from .loader import build_loader_zip
from .repos import RepoOutput, create_repo, fork_repo, gh_available


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

class SetupResult:
    def __init__(
        self,
        age: AgeKeypair,
        ssh: SSHKeypair | None,
        config: GlobalConfig | None,
        loader_zip: bytes,
        secrets_repo: RepoOutput,
        config_repo: RepoOutput | None,
        payload_url: str | None,
        mode: str,
        account_uuid: str,
        github_username: str,
    ):
        self.age = age
        self.ssh = ssh
        self.config = config
        self.loader_zip = loader_zip
        self.secrets_repo = secrets_repo
        self.config_repo = config_repo
        self.payload_url = payload_url
        self.mode = mode
        self.account_uuid = account_uuid
        self.github_username = github_username


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

def run_wizard() -> SetupResult:
    click.echo()
    click.secho("  claude-setup", bold=True)
    click.echo("  Bootstrap the claude loader fleet")
    click.echo()

    use_gh = gh_available()
    if use_gh:
        click.secho("  ✓ gh CLI detected — repos will be created on GitHub", fg="green")
    else:
        click.secho("  ✗ gh CLI not found — repos will be saved as .zip files", fg="yellow")
    click.echo()

    # ── Step 1: GitHub PAT ──────────────────────────────────────────────────
    click.secho("[1/7] GitHub PAT", bold=True)
    click.echo("      This will be encrypted and stored in claude-secrets.")
    pat = click.prompt("      PAT", hide_input=True)
    click.echo()

    # ── Step 2: GitHub username ─────────────────────────────────────────────
    click.secho("[2/7] GitHub username", bold=True)
    github_username = click.prompt("      Username")
    click.echo()

    # ── Step 3: Loader mode ─────────────────────────────────────────────────
    click.secho("[3/7] Loader mode", bold=True)
    click.echo("      (A) Config-driven  — fleet management via claude-config repo")
    click.echo("          Best for multiple accounts; change config without touching the loader.")
    click.echo("      (B) Hardcoded      — single account, simpler, no extra repo")
    mode_raw = click.prompt("      Mode", type=click.Choice(["A", "B", "a", "b"]), default="A")
    mode = mode_raw.upper()
    click.echo()

    # ── Step 4: SSH signing key ─────────────────────────────────────────────
    click.secho("[4/7] SSH signing key (optional)", bold=True)
    click.echo("      Used for git commit signing. Public key goes to GitHub → Settings → SSH keys.")
    want_signing = click.confirm("      Generate signing key?", default=False)
    click.echo()

    # ── Step 5: Generate keys ───────────────────────────────────────────────
    click.secho("[5/7] Generating keys...", bold=True)
    age_keypair = generate_age_keypair()
    click.secho("      ✓ Age keypair generated", fg="green")

    ssh_keypair: SSHKeypair | None = None
    if want_signing:
        ssh_keypair = generate_ssh_keypair()
        click.secho("      ✓ SSH signing key generated", fg="green")
    click.echo()

    # ── Step 6: Generate UUID and encrypt secrets ───────────────────────────
    account_uuid = str(uuid.uuid4())

    encrypted_pat = encrypt_string(pat, age_keypair.public_key)
    secrets_files: dict[str, bytes] = {
        "github-token.age": encrypted_pat,
    }
    if ssh_keypair is not None:
        encrypted_signing = encrypt_string(
            ssh_keypair.private_pem.decode(), age_keypair.public_key
        )
        secrets_files["signing-key.age"] = encrypted_signing

    # ── Step 7: Create repos ────────────────────────────────────────────────
    click.secho("[6/7] Creating repos...", bold=True)

    # claude-secrets (always)
    secrets_repo = create_repo(
        f"{github_username}/claude-secrets",
        secrets_files,
        private=True,
        description="claude loader encrypted secrets",
        use_gh=use_gh,
    )
    _print_repo_result(secrets_repo, "claude-secrets")

    # claude-config (Mode A only)
    config_repo: RepoOutput | None = None
    config: GlobalConfig | None = None
    config_repo_url: str | None = None

    if mode == "A":
        config = build_config(
            github_username=github_username,
            uuid=account_uuid,
            signing_enabled=want_signing,
        )
        config_toml = config_to_toml(config)
        config_repo = create_repo(
            f"{github_username}/claude-config",
            {"config.toml": config_toml},
            private=False,
            description="claude loader fleet config",
            use_gh=use_gh,
        )
        _print_repo_result(config_repo, "claude-config")
        config_repo_url = (
            config_repo.url
            or f"https://github.com/{github_username}/claude-config"
        )

    # Fork claude-payload
    payload_url: str | None = None
    if use_gh:
        try:
            payload_url = fork_repo("0x038b5c/claude-payload")
            click.secho(f"      ✓ Forked claude-payload → {payload_url}", fg="green")
        except Exception as e:
            click.secho(f"      ✗ Could not fork claude-payload: {e}", fg="yellow")
            click.echo("        Fork manually: https://github.com/0x038b5c/claude-payload/fork")
    else:
        click.secho(
            "      ✗ gh not available — fork claude-payload manually:", fg="yellow"
        )
        click.echo("        https://github.com/0x038b5c/claude-payload/fork")

    click.echo()

    # ── Step 8: Build loader.zip ────────────────────────────────────────────
    click.secho("[7/7] Building loader.zip...", bold=True)

    payload_repo_path = (
        payload_url.replace("https://github.com/", "") if payload_url
        else f"{github_username}/claude-payload"
    )
    secrets_repo_path = f"{github_username}/claude-secrets"
    state_repo_path   = f"{github_username}/claude-state"

    if mode == "A":
        loader_zip = build_loader_zip(
            age_keypair.private_key,
            uuid=account_uuid,
            config_repo=config_repo_url,
        )
    else:
        loader_zip = build_loader_zip(
            age_keypair.private_key,
            github_username=github_username,
            payload_repo=f"https://github.com/{payload_repo_path}",
            secrets_repo=f"https://github.com/{secrets_repo_path}",
            state_repo=f"https://github.com/{state_repo_path}",
        )

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
    )


def print_summary(result: SetupResult, output_dir: str) -> None:
    """Print the post-wizard summary."""
    click.echo()
    click.secho("━" * 60, fg="bright_black")
    click.secho("  Setup complete!", bold=True, fg="green")
    click.secho("━" * 60, fg="bright_black")
    click.echo()

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
    if result.secrets_repo.zip_bytes:
        click.echo(f"    {output_dir}/claude-secrets.zip  (push to GitHub manually)")
    if result.config_repo and result.config_repo.zip_bytes:
        click.echo(f"    {output_dir}/claude-config.zip   (push to GitHub manually)")
    click.echo()

    click.secho("  Next steps", bold=True)
    click.echo("    1. Upload loader.zip to Claude:")
    click.echo("       claude.ai → Customize → Skills → + → Create Skill → Upload Zip")
    click.echo()
    click.echo("    2. Add to Claude's instructions (Profile → Custom Instructions):")
    click.echo()
    click.secho(
        "       At the start of every conversation, before doing anything else,\n"
        "       check the <available_skills> block in your context for a skill\n"
        "       named loader and, if present, immediately read and follow its\n"
        "       SKILL.md without consulting any other files.",
        fg="cyan",
    )
    click.echo()
    click.echo("    3. Start a new conversation — Claude will self-provision.")
    click.echo()

    if not result.payload_url:
        click.secho("  ⚠  Don't forget to fork claude-payload:", fg="yellow")
        click.echo("     https://github.com/0x038b5c/claude-payload/fork")
        click.echo()


def _print_repo_result(repo: RepoOutput, label: str) -> None:
    if repo.via_gh:
        click.secho(f"      ✓ {label} → {repo.url}", fg="green")
    else:
        click.secho(f"      ✓ {label} (saved as zip)", fg="green")
