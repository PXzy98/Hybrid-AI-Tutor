"""Encrypted API keys of model connections (task Z6; course-structure.md 6.3).

Keys are encrypted with Fernet using `SETTINGS_ENCRYPTION_KEY` (a Fernet key, see .env.example), kept in
`.env` or a Docker secret.
The app refuses to start when encrypted keys exist and the key is missing or wrong.
"""
from cryptography.fernet import Fernet, InvalidToken


class MissingEncryptionKey(RuntimeError):
    pass


def _fernet(key: str | None) -> Fernet:
    if not key:
        raise MissingEncryptionKey("set SETTINGS_ENCRYPTION_KEY to store or use API keys of model "
                                   "connections")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as e:
        raise MissingEncryptionKey("SETTINGS_ENCRYPTION_KEY is not a valid Fernet key") from e


def encrypt(secret: str, key: str | None) -> str:
    return _fernet(key).encrypt(secret.encode()).decode()


def decrypt(token: str, key: str | None) -> str:
    try:
        return _fernet(key).decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise MissingEncryptionKey("SETTINGS_ENCRYPTION_KEY does not match the stored API keys") from e


def last4(secret: str) -> str:
    return secret[-4:] if len(secret) >= 8 else "****"
