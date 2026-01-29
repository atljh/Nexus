"""
Password encryption utilities for secure storage of sensitive data.
Uses Fernet symmetric encryption with auto-generated keys stored locally.
"""
import os
import base64
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class PasswordEncryption:
    """
    Handles encryption/decryption of sensitive data using Fernet.
    Key is derived from a machine-specific seed stored in app data directory.
    """

    def __init__(self, key_file: Optional[Path] = None):
        """
        Initialize encryption service.

        Args:
            key_file: Path to store the encryption key.
                     Defaults to ~/.Nexus/encryption.key
        """
        if key_file is None:
            app_dir = Path.home() / ".Nexus"
            app_dir.mkdir(parents=True, exist_ok=True)
            key_file = app_dir / "encryption.key"

        self.key_file = key_file
        self._cipher: Optional[Fernet] = None

    def _get_or_create_key(self) -> bytes:
        """Get existing key or create a new one."""
        if self.key_file.exists():
            return self.key_file.read_bytes()

        # Generate a new key
        key = Fernet.generate_key()
        self.key_file.write_bytes(key)
        # Restrict file permissions (owner read/write only)
        os.chmod(self.key_file, 0o600)
        return key

    @property
    def cipher(self) -> Fernet:
        """Lazy-load the Fernet cipher."""
        if self._cipher is None:
            key = self._get_or_create_key()
            self._cipher = Fernet(key)
        return self._cipher

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""

        encrypted = self.cipher.encrypt(plaintext.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted string (base64-encoded)

        Returns:
            Decrypted plaintext string

        Raises:
            ValueError: If decryption fails (invalid token or corrupted data)
        """
        if not ciphertext:
            return ""

        try:
            decrypted = self.cipher.decrypt(ciphertext.encode('utf-8'))
            return decrypted.decode('utf-8')
        except InvalidToken:
            raise ValueError("Failed to decrypt: invalid or corrupted data")

    def is_encrypted(self, value: str) -> bool:
        """
        Check if a string appears to be encrypted (Fernet format).

        Args:
            value: String to check

        Returns:
            True if the string looks like Fernet-encrypted data
        """
        if not value:
            return False

        # Fernet tokens are base64-encoded and start with 'gAAAAA'
        try:
            decoded = base64.urlsafe_b64decode(value.encode('utf-8'))
            # Fernet tokens are at least 57 bytes (version + timestamp + IV + ciphertext + HMAC)
            return len(decoded) >= 57 and decoded[0] == 0x80
        except Exception:
            return False

    def encrypt_if_needed(self, value: str) -> str:
        """
        Encrypt a value only if it's not already encrypted.

        Args:
            value: String to potentially encrypt

        Returns:
            Encrypted string
        """
        if not value or self.is_encrypted(value):
            return value
        return self.encrypt(value)

    def decrypt_safe(self, value: str) -> str:
        """
        Decrypt a value, returning the original if decryption fails.
        Useful during migration from unencrypted to encrypted storage.

        Args:
            value: String to decrypt

        Returns:
            Decrypted string, or original if decryption fails
        """
        if not value:
            return value

        if not self.is_encrypted(value):
            # Value is not encrypted, return as-is
            return value

        try:
            return self.decrypt(value)
        except ValueError:
            # Decryption failed, return original
            return value


# Global singleton instance
encryption_service = PasswordEncryption()
