import secrets
import hashlib


def generate_scan_id() -> str:
    """Generate a unique identifier for a scan."""
    return secrets.token_urlsafe(16)


def hash_value(value: str) -> str:
    """Create a SHA-256 hash for a value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_token(token: str, expected_token: str) -> bool:
    """Safely compare two tokens."""
    return secrets.compare_digest(token, expected_token)