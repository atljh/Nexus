"""Tests for utils.encryption — password encryption/decryption."""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.encryption import PasswordEncryption


def _make_service(tmp_path: Path = None) -> PasswordEncryption:
    """Create PasswordEncryption with a temp key file."""
    if tmp_path is None:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
    key_file = tmp_path / "test_encryption.key"
    return PasswordEncryption(key_file=key_file)


class TestEncryptDecrypt:
    """Tests for basic encrypt/decrypt cycle."""

    def test_encrypt_decrypt_roundtrip(self):
        svc = _make_service()
        plaintext = "my_secret_password"
        encrypted = svc.encrypt(plaintext)
        decrypted = svc.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_returns_different_from_plaintext(self):
        svc = _make_service()
        plaintext = "password123"
        encrypted = svc.encrypt(plaintext)
        assert encrypted != plaintext

    def test_empty_string_encrypt(self):
        svc = _make_service()
        assert svc.encrypt("") == ""

    def test_empty_string_decrypt(self):
        svc = _make_service()
        assert svc.decrypt("") == ""

    def test_unicode_roundtrip(self):
        svc = _make_service()
        plaintext = "пароль_🔐_密码"
        encrypted = svc.encrypt(plaintext)
        assert svc.decrypt(encrypted) == plaintext

    def test_long_string(self):
        svc = _make_service()
        plaintext = "a" * 10000
        encrypted = svc.encrypt(plaintext)
        assert svc.decrypt(encrypted) == plaintext

    def test_decrypt_invalid_raises(self):
        svc = _make_service()
        import pytest
        with pytest.raises(ValueError, match="Failed to decrypt"):
            svc.decrypt("definitely_not_encrypted_data_but_long_enough_aaaaaa")


class TestIsEncrypted:
    """Tests for is_encrypted()."""

    def test_encrypted_value(self):
        svc = _make_service()
        encrypted = svc.encrypt("hello")
        assert svc.is_encrypted(encrypted) is True

    def test_plain_value(self):
        svc = _make_service()
        assert svc.is_encrypted("just_plain_text") is False

    def test_empty_value(self):
        svc = _make_service()
        assert svc.is_encrypted("") is False


class TestEncryptIfNeeded:
    """Tests for encrypt_if_needed()."""

    def test_encrypts_plain(self):
        svc = _make_service()
        result = svc.encrypt_if_needed("plain")
        assert result != "plain"
        assert svc.decrypt(result) == "plain"

    def test_skips_already_encrypted(self):
        svc = _make_service()
        encrypted = svc.encrypt("data")
        result = svc.encrypt_if_needed(encrypted)
        # Should not double-encrypt
        assert svc.decrypt(result) == "data"

    def test_empty_returns_empty(self):
        svc = _make_service()
        assert svc.encrypt_if_needed("") == ""


class TestDecryptSafe:
    """Tests for decrypt_safe()."""

    def test_decrypts_encrypted(self):
        svc = _make_service()
        encrypted = svc.encrypt("secret")
        assert svc.decrypt_safe(encrypted) == "secret"

    def test_returns_plain_as_is(self):
        svc = _make_service()
        assert svc.decrypt_safe("not_encrypted") == "not_encrypted"

    def test_empty_returns_empty(self):
        svc = _make_service()
        assert svc.decrypt_safe("") == ""

    def test_none_returns_none(self):
        svc = _make_service()
        assert svc.decrypt_safe(None) is None


class TestKeyPersistence:
    """Tests for key file management."""

    def test_key_file_created(self):
        tmp = Path(tempfile.mkdtemp())
        key_file = tmp / "test.key"
        svc = PasswordEncryption(key_file=key_file)
        svc.encrypt("trigger_key_creation")
        assert key_file.exists()

    def test_key_reuse_across_instances(self):
        tmp = Path(tempfile.mkdtemp())
        key_file = tmp / "shared.key"

        svc1 = PasswordEncryption(key_file=key_file)
        encrypted = svc1.encrypt("shared_secret")

        svc2 = PasswordEncryption(key_file=key_file)
        assert svc2.decrypt(encrypted) == "shared_secret"

    def test_key_file_permissions(self):
        tmp = Path(tempfile.mkdtemp())
        key_file = tmp / "perm.key"
        svc = PasswordEncryption(key_file=key_file)
        svc.encrypt("x")
        mode = oct(key_file.stat().st_mode)[-3:]
        assert mode == "600"
