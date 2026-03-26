"""
Chiffrement symétrique des clés API stockées en base.
Utilise Fernet (AES-128-CBC + HMAC-SHA256) dérivé depuis SECRET_KEY.
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from config import settings


def _fernet() -> Fernet:
    # Dérive une clé Fernet 32 octets depuis SECRET_KEY
    raw = hashlib.sha256(settings.secret_key.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt(value: str) -> str:
    """Chiffre une valeur sensible avant stockage."""
    if not value:
        return value
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Déchiffre une valeur stockée."""
    if not value:
        return value
    try:
        return _fernet().decrypt(value.encode()).decode()
    except Exception:
        # Valeur déjà en clair (migration depuis ancienne version) — retourner telle quelle
        return value
