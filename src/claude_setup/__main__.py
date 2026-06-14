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
    help="Directory to write loader.zip and any local repo directories.",
)
def cli(output_dir: str) -> None:
    """Bootstrap the claude loader fleet.

    Generates age + SSH keys, encrypts secrets, creates GitHub repos
    (or initialized local git directories), and produces loader.zip
    ready to upload to Claude.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        result = run_wizard(output_dir=out)
    except (KeyboardInterrupt, click.Abort):
        click.echo()
        click.secho("  Aborted.", fg="yellow")
        sys.exit(1)

    # Write loader.zip (the only zip output)
    loader_path = out / "loader.zip"
    loader_path.write_bytes(result.loader_zip)

    print_summary(result, str(out))


if __name__ == "__main__":
    cli()
