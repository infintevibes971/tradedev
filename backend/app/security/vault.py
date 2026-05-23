import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


class KeyVault:
    """Encrypts and decrypts exchange API keys using Fernet symmetric encryption.

    The master encryption key comes from ENCRYPTION_KEY in .env.
    If absent, a new key is generated and logged (dev convenience).
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        key = encryption_key or settings.encryption_key
        if not key:
            key = Fernet.generate_key().decode()
            logger.warning(
                f"No ENCRYPTION_KEY set — generated ephemeral key. "
                f"Set ENCRYPTION_KEY={key} in .env for persistence."
            )
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken:
            raise ValueError(
                "Decryption failed — ENCRYPTION_KEY may have changed or data is corrupted"
            )


vault = KeyVault()
