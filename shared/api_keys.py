import secrets
import bcrypt


def generate_api_key() -> str:
    """Returns plaintext key — shown once to user."""
    return "soc_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()


def verify_api_key(key: str, hashed: str) -> bool:
    return bcrypt.checkpw(key.encode(), hashed.encode())


def get_key_prefix(key: str) -> str:
    """First 12 chars used for lookup — avoids full-table bcrypt scan."""
    return key[:12]
