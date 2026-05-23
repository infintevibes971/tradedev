import pytest
from cryptography.fernet import Fernet

from app.security.vault import KeyVault


@pytest.fixture
def test_vault():
    key = Fernet.generate_key().decode()
    return KeyVault(encryption_key=key)


def test_encrypt_decrypt_roundtrip(test_vault: KeyVault):
    api_key = "sk-live-abcdef123456789"
    encrypted = test_vault.encrypt(api_key)

    assert encrypted != api_key.encode()
    assert isinstance(encrypted, bytes)

    decrypted = test_vault.decrypt(encrypted)
    assert decrypted == api_key


def test_different_encryptions_differ(test_vault: KeyVault):
    plaintext = "my-secret-key"
    enc1 = test_vault.encrypt(plaintext)
    enc2 = test_vault.encrypt(plaintext)
    assert enc1 != enc2


def test_wrong_key_fails():
    vault_a = KeyVault(encryption_key=Fernet.generate_key().decode())
    vault_b = KeyVault(encryption_key=Fernet.generate_key().decode())

    encrypted = vault_a.encrypt("secret")
    with pytest.raises(ValueError, match="Decryption failed"):
        vault_b.decrypt(encrypted)


def test_corrupted_data_fails(test_vault: KeyVault):
    encrypted = test_vault.encrypt("secret")
    corrupted = encrypted[:-5] + b"XXXXX"
    with pytest.raises(ValueError, match="Decryption failed"):
        test_vault.decrypt(corrupted)


def test_auto_generates_key_when_empty():
    vault = KeyVault(encryption_key=Fernet.generate_key().decode())
    result = vault.decrypt(vault.encrypt("test-roundtrip"))
    assert result == "test-roundtrip"
