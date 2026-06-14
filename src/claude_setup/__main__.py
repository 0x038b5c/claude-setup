"""claude-setup CLI entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .wizard import run_wizard, print_summary


@click.command()
@click.option(
    "--output-dir", "-o",
    default=".",
    show_default=True,
    help="Directory to write loader.zip (and repo zips if gh is unavailable).",
)
def cli(output_dir: str) -> None:
    """Bootstrap the claude loader fleet.

    Generates age + SSH keys, encrypts secrets, creates GitHub repos
    (or zip files), and produces loader.zip ready to upload to Claude.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        result = run_wizard()
    except (KeyboardInterrupt, click.Abort):
        click.echo()
        click.secho("  Aborted.", fg="yellow")
        sys.exit(1)

    # Write loader.zip
    loader_path = out / "loader.zip"
    loader_path.write_bytes(result.loader_zip)

    # Write repo zips if gh wasn't available
    if result.secrets_repo.zip_bytes:
        (out / "claude-secrets.zip").write_bytes(result.secrets_repo.zip_bytes)

    if result.config_repo and result.config_repo.zip_bytes:
        (out / "claude-config.zip").write_bytes(result.config_repo.zip_bytes)

    print_summary(result, str(out))


if __name__ == "__main__":
    cli()
