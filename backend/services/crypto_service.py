import base64
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken
from backend.config import settings

logger = logging.getLogger(__name__)


def _get_fernet_instance() -> Fernet:
    """Derives a valid 32-byte urlsafe base64 Fernet key from configured ENCRYPTION_KEY."""
    raw_key = settings.ENCRYPTION_KEY.strip()
    try:
        # Check if already a valid 32-byte urlsafe base64 key
        decoded = base64.urlsafe_b64decode(raw_key)
        if len(decoded) == 32:
            return Fernet(raw_key.encode("utf-8"))
    except Exception:
        pass

    # Deterministically derive 32-byte key via SHA-256
    derived_bytes = hashlib.sha256(raw_key.encode("utf-8")).digest()
    b64_key = base64.urlsafe_b64encode(derived_bytes)
    return Fernet(b64_key)


_fernet = _get_fernet_instance()


def encrypt_secret(plain_text: str | None) -> str | None:
    """Encrypts a plaintext secret (API key, OAuth token) for safe database storage."""
    if plain_text is None:
        return None
    if not plain_text.strip():
        return ""
    try:
        encrypted_bytes = _fernet.encrypt(plain_text.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    except Exception as e:
        logger.error("Failed to encrypt secret: %s", e)
        raise ValueError("Encryption failed") from e


def decrypt_secret(cipher_text: str | None) -> str | None:
    """Decrypts an encrypted ciphertext secret at runtime."""
    if cipher_text is None:
        return None
    if not cipher_text.strip():
        return ""
    try:
        decrypted_bytes = _fernet.decrypt(cipher_text.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        logger.error("Invalid decryption token or mismatching ENCRYPTION_KEY")
        raise ValueError("Failed to decrypt secret: invalid token")
    except Exception as e:
        logger.error("Decryption error: %s", e)
        raise ValueError("Decryption failed") from e


def mask_secret(secret: str | None, visible_suffix_len: int = 4) -> str:
    """Masks an API key or token for frontend display (e.g. 'gsk_••••••••1234')."""
    if not secret:
        return ""
    clean = secret.strip()
    if len(clean) <= visible_suffix_len + 2:
        return "••••" + clean[-2:] if len(clean) >= 2 else "••••"
    prefix = clean[:3] if len(clean) > 8 else ""
    suffix = clean[-visible_suffix_len:]
    return f"{prefix}••••••••{suffix}"


class CryptoService:
    @staticmethod
    def encrypt(text: str | None) -> str | None:
        return encrypt_secret(text)

    @staticmethod
    def decrypt(cipher: str | None) -> str | None:
        return decrypt_secret(cipher)

    @staticmethod
    def mask(secret: str | None, visible_suffix_len: int = 4) -> str:
        return mask_secret(secret, visible_suffix_len)


crypto_service = CryptoService()
