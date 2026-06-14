"""Key generation: age keypair and optional SSH signing key."""

from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from pyrage import x25519


@dataclass
class AgeKeypair:
    private_key: str  # AGE-SECRET-KEY-1...
    public_key: str   # age1...


@dataclass
class SSHKeypair:
    private_pem: bytes  # -----BEGIN OPENSSH PRIVATE KEY-----
    public_ssh: bytes   # ssh-ed25519 AAAA...


def generate_age_keypair() -> AgeKeypair:
    """Generate a new X25519 age keypair."""
    identity = x25519.Identity.generate()
    return AgeKeypair(
        private_key=str(identity),
        public_key=str(identity.to_public()),
    )


def generate_ssh_keypair() -> SSHKeypair:
    """Generate a new Ed25519 SSH keypair suitable for git commit signing."""
    key = Ed25519PrivateKey.generate()
    private_pem = key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.OpenSSH,
        encryption_algorithm=NoEncryption(),
    )
    public_ssh = key.public_key().public_bytes(
        encoding=Encoding.OpenSSH,
        format=PublicFormat.OpenSSH,
    )
    return SSHKeypair(private_pem=private_pem, public_ssh=public_ssh)
