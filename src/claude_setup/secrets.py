"""Age encryption helpers for secrets."""

from pyrage import encrypt, x25519


def encrypt_secret(plaintext: bytes, age_public_key: str) -> bytes:
    """Encrypt plaintext to age_public_key, returning armored age ciphertext.

    Args:
        plaintext: Raw bytes to encrypt (e.g. a GitHub PAT or SSH private key).
        age_public_key: age public key string (age1...).

    Returns:
        Armored age ciphertext as bytes (-----BEGIN AGE ENCRYPTED FILE-----...).
    """
    recipient = x25519.Recipient.from_str(age_public_key)
    return encrypt(plaintext, [recipient], armored=True)


def encrypt_string(plaintext: str, age_public_key: str) -> bytes:
    """Convenience wrapper — encrypt a string secret."""
    return encrypt_secret(plaintext.encode(), age_public_key)
