"""
Chiffrement des données sensibles au repos. La clé maîtresse est
protégée par la DPAPI de Windows (liée au compte utilisateur Windows).
"""
from pathlib import Path
from cryptography.fernet import Fernet

try:
    import win32crypt
    HAS_DPAPI = True
except Exception:
    HAS_DPAPI = False

KEY_FILE = Path("sentinel.key")


def _protect(data: bytes) -> bytes:
    if HAS_DPAPI:
        return win32crypt.CryptProtectData(data, "SentinelKey", None, None, None, 0)
    return data


def _unprotect(data: bytes) -> bytes:
    if HAS_DPAPI:
        return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
    return data


def load_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return _unprotect(KEY_FILE.read_bytes())
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(_protect(key))
    return key


_fernet = Fernet(load_or_create_key())


def encrypt(text: str) -> str:
    return _fernet.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
