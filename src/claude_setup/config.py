"""Config dataclasses and TOML read/write for claude-config."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tomli_w


@dataclass
class AccountConfig:
    uuid: str
    github_username: str
    payload_repo: Optional[str] = None       # overrides global if set
    signing_enabled: Optional[bool] = None   # overrides global if set
    github_token_secret: str = "github-token.age"
    signing_key_secret: str = "signing-key.age"


@dataclass
class GlobalConfig:
    payload_repo: str
    secrets_repo: str
    state_repo: str
    signing_enabled: bool = False
    accounts: dict[str, AccountConfig] = field(default_factory=dict)


def build_config(
    github_username: str,
    uuid: str,
    signing_enabled: bool,
) -> GlobalConfig:
    """Build a fresh GlobalConfig for a new setup."""
    return GlobalConfig(
        payload_repo=f"{github_username}/claude-payload",
        secrets_repo=f"{github_username}/claude-secrets",
        state_repo=f"{github_username}/claude-state",
        signing_enabled=signing_enabled,
        accounts={
            uuid: AccountConfig(
                uuid=uuid,
                github_username=github_username,
                signing_enabled=signing_enabled if signing_enabled else None,
            )
        },
    )


def config_to_toml(config: GlobalConfig) -> bytes:
    """Serialise a GlobalConfig to TOML bytes."""
    doc: dict = {
        "global": {
            "payload_repo": config.payload_repo,
            "secrets_repo": config.secrets_repo,
            "state_repo": config.state_repo,
            "signing_enabled": config.signing_enabled,
        },
        "account": {},
    }
    for uuid, acct in config.accounts.items():
        entry: dict = {"github_username": acct.github_username}
        if acct.payload_repo is not None:
            entry["payload_repo"] = acct.payload_repo
        if acct.signing_enabled is not None:
            entry["signing_enabled"] = acct.signing_enabled
        if acct.github_token_secret != "github-token.age":
            entry["github_token_secret"] = acct.github_token_secret
        if acct.signing_key_secret != "signing-key.age":
            entry["signing_key_secret"] = acct.signing_key_secret
        doc["account"][uuid] = entry

    return tomli_w.dumps(doc).encode()


def config_from_toml(data: bytes) -> GlobalConfig:
    """Parse TOML bytes into a GlobalConfig."""
    doc = tomllib.loads(data.decode())
    g = doc.get("global", {})
    accounts = {}
    for uuid, acct in doc.get("account", {}).items():
        accounts[uuid] = AccountConfig(
            uuid=uuid,
            github_username=acct["github_username"],
            payload_repo=acct.get("payload_repo"),
            signing_enabled=acct.get("signing_enabled"),
            github_token_secret=acct.get("github_token_secret", "github-token.age"),
            signing_key_secret=acct.get("signing_key_secret", "signing-key.age"),
        )
    return GlobalConfig(
        payload_repo=g["payload_repo"],
        secrets_repo=g["secrets_repo"],
        state_repo=g["state_repo"],
        signing_enabled=g.get("signing_enabled", False),
        accounts=accounts,
    )


def resolve_account(config: GlobalConfig, uuid: str) -> tuple[str, str, str, str]:
    """Resolve effective (github_username, payload_repo, secrets_repo, state_repo)
    for a given UUID, merging account overrides onto global defaults."""
    acct = config.accounts.get(uuid)
    if acct is None:
        raise KeyError(f"No account with UUID {uuid!r} in config")
    payload_repo = acct.payload_repo or config.payload_repo
    return (
        acct.github_username,
        payload_repo,
        config.secrets_repo,
        config.state_repo,
    )
