"""Config dataclasses and TOML read/write for claude-config."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import Optional

import tomli_w


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GitAuthorConfig:
    """Git commit author identity."""
    name: str
    email: str


@dataclass
class AccountConfig:
    """Per-account overrides. Only set fields that differ from global defaults."""
    uuid: str
    # Only set when this account uses a different username than the global default
    github_username: Optional[str] = None
    # Only set when this account uses a different payload repo than the global default
    payload_repo: Optional[str] = None
    # Only set to override global signing_enabled
    signing_enabled: Optional[bool] = None


@dataclass
class GlobalConfig:
    """Global defaults that apply to all accounts unless overridden."""
    github_username: str                        # default username for all accounts
    payload_repo: str                           # e.g. "username/claude-payload"
    secrets_repo: str                           # e.g. "username/claude-secrets"
    state_repo: str                             # e.g. "username/claude-state"
    github_token_secret: str = "github-token.age"   # filename in claude-secrets
    signing_key_secret: str = "signing-key.age"     # filename in claude-secrets
    signing_enabled: bool = False
    git_signing_format: str = "gpg"             # "gpg" or "ssh"
    git_author: Optional[GitAuthorConfig] = None    # None = use GitHub noreply
    accounts: dict[str, AccountConfig] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def build_config(
    github_username: str,
    uuid: str,
    signing_enabled: bool,
    git_signing_format: str,
    git_author: Optional[GitAuthorConfig],
) -> GlobalConfig:
    """Build a fresh GlobalConfig for a new setup."""
    return GlobalConfig(
        github_username=github_username,
        payload_repo=f"{github_username}/claude-payload",
        secrets_repo=f"{github_username}/claude-secrets",
        state_repo=f"{github_username}/claude-state",
        signing_enabled=signing_enabled,
        git_signing_format=git_signing_format,
        git_author=git_author,
        accounts={
            uuid: AccountConfig(uuid=uuid),  # no overrides needed for first account
        },
    )


# ---------------------------------------------------------------------------
# TOML serialisation
# ---------------------------------------------------------------------------

def config_to_toml(config: GlobalConfig) -> bytes:
    """Serialise a GlobalConfig to TOML bytes."""
    doc: dict = {
        "global": {
            "github_username": config.github_username,
            "payload_repo": config.payload_repo,
            "secrets_repo": config.secrets_repo,
            "state_repo": config.state_repo,
            "github_token_secret": config.github_token_secret,
            "signing_key_secret": config.signing_key_secret,
            "signing_enabled": config.signing_enabled,
            "git_signing_format": config.git_signing_format,
        },
        "account": {},
    }

    if config.git_author is not None:
        doc["global"]["git_author_name"] = config.git_author.name
        doc["global"]["git_author_email"] = config.git_author.email

    for uuid, acct in config.accounts.items():
        entry: dict = {}
        if acct.github_username is not None:
            entry["github_username"] = acct.github_username
        if acct.payload_repo is not None:
            entry["payload_repo"] = acct.payload_repo
        if acct.signing_enabled is not None:
            entry["signing_enabled"] = acct.signing_enabled
        # Always write uuid so the section is identifiable even if empty
        entry["uuid"] = uuid
        doc["account"][uuid] = entry

    return tomli_w.dumps(doc).encode()


def config_from_toml(data: bytes) -> GlobalConfig:
    """Parse TOML bytes into a GlobalConfig."""
    doc = tomllib.loads(data.decode())
    g = doc.get("global", {})

    git_author: Optional[GitAuthorConfig] = None
    if "git_author_name" in g and "git_author_email" in g:
        git_author = GitAuthorConfig(name=g["git_author_name"], email=g["git_author_email"])

    accounts = {}
    for uuid, acct in doc.get("account", {}).items():
        accounts[uuid] = AccountConfig(
            uuid=uuid,
            github_username=acct.get("github_username"),
            payload_repo=acct.get("payload_repo"),
            signing_enabled=acct.get("signing_enabled"),
        )

    return GlobalConfig(
        github_username=g["github_username"],
        payload_repo=g["payload_repo"],
        secrets_repo=g["secrets_repo"],
        state_repo=g["state_repo"],
        github_token_secret=g.get("github_token_secret", "github-token.age"),
        signing_key_secret=g.get("signing_key_secret", "signing-key.age"),
        signing_enabled=g.get("signing_enabled", False),
        git_signing_format=g.get("git_signing_format", "gpg"),
        git_author=git_author,
        accounts=accounts,
    )


def resolve_account(config: GlobalConfig, uuid: str) -> dict:
    """Resolve effective settings for a given UUID, merging account overrides onto global.

    Returns a dict with all resolved values.
    """
    acct = config.accounts.get(uuid)
    if acct is None:
        raise KeyError(f"No account with UUID {uuid!r} in config")
    return {
        "github_username": acct.github_username or config.github_username,
        "payload_repo": acct.payload_repo or config.payload_repo,
        "secrets_repo": config.secrets_repo,
        "state_repo": config.state_repo,
        "github_token_secret": config.github_token_secret,
        "signing_key_secret": config.signing_key_secret,
        "signing_enabled": acct.signing_enabled if acct.signing_enabled is not None else config.signing_enabled,
        "git_signing_format": config.git_signing_format,
        "git_author": config.git_author,
    }
