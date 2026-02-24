"""
Core security functions for Vibe-Quality-Searcharr.

This module provides cryptographic operations following OWASP best practices:
- Password hashing with Argon2id (OWASP recommended)
- Secure token generation using secrets module
- Field-level encryption using Fernet (AES-128-CBC with HMAC)
- Constant-time comparison for security-sensitive operations
"""

import secrets
import string
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from vibe_quality_searcharr.config import settings


class PasswordHashingError(Exception):
    """Exception raised when password hashing operations fail."""

    pass


class EncryptionError(Exception):
    """Exception raised when encryption/decryption operations fail."""

    pass


class PasswordSecurity:
    """
    Secure password hashing using Argon2id with pepper.

    Implements OWASP Password Storage Cheat Sheet recommendations:
    - Argon2id algorithm (winner of Password Hashing Competition)
    - Memory-hard function (128 MiB memory cost)
    - Global pepper stored separately from database
    - Per-user salt (handled automatically by Argon2)
    - Configurable time and parallelism parameters
    """

    def __init__(self) -> None:
        """Initialize password hasher with secure parameters."""
        self._hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,  # 3 iterations
            memory_cost=settings.argon2_memory_cost,  # 128 MiB
            parallelism=settings.argon2_parallelism,  # 8 threads
            hash_len=32,  # 256-bit hash
            salt_len=16,  # 128-bit salt
        )
        self._pepper = settings.get_pepper()

    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2id with pepper.

        The password is peppered before hashing to add an additional layer of security.
        If the database is compromised, the pepper (stored separately) is still required
        to verify passwords.

        Args:
            password: Plain-text password to hash

        Returns:
            str: Argon2id hash string (includes salt and parameters)

        Raises:
            PasswordHashingError: If hashing fails
            ValueError: If password is empty
        """
        if not password:
            raise ValueError("Password cannot be empty")

        try:
            # Add pepper to password before hashing
            peppered_password = password + self._pepper
            return self._hasher.hash(peppered_password)
        except Exception as e:
            raise PasswordHashingError(f"Failed to hash password: {e}") from e

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against an Argon2id hash.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            password: Plain-text password to verify
            password_hash: Argon2id hash to verify against

        Returns:
            bool: True if password matches hash, False otherwise

        Raises:
            PasswordHashingError: If verification process fails
            ValueError: If password or hash is empty
        """
        if not password or not password_hash:
            raise ValueError("Password and hash cannot be empty")

        try:
            # Add pepper before verification
            peppered_password = password + self._pepper
            self._hasher.verify(password_hash, peppered_password)
            return True
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            # Password doesn't match or hash is invalid
            return False
        except Exception as e:
            raise PasswordHashingError(f"Failed to verify password: {e}") from e

    def needs_rehash(self, password_hash: str) -> bool:
        """
        Check if a password hash needs to be updated.

        This should be called after successful authentication to upgrade
        hashes if parameters have changed.

        Args:
            password_hash: Argon2id hash to check

        Returns:
            bool: True if hash should be regenerated with new parameters
        """
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except Exception:
            # If we can't parse the hash, it should be regenerated
            return True


class FieldEncryption:
    """
    Field-level encryption using Fernet (AES-128-CBC + HMAC-SHA256).

    Used for encrypting sensitive data in the database:
    - API keys for Sonarr/Radarr instances
    - Other sensitive configuration values

    Fernet provides authenticated encryption, ensuring data integrity
    and authenticity in addition to confidentiality.
    """

    def __init__(self) -> None:
        """
        Initialize Fernet cipher with key derived from secret key.

        The encryption key is derived from the application secret key
        to avoid requiring a separate encryption key.
        """
        # Derive a Fernet key from the secret key
        # Fernet requires a 32-byte base64-encoded key
        secret_key = settings.get_secret_key()
        # Use the first 32 bytes of the secret key and base64 encode it
        key_bytes = secret_key.encode()[:32].ljust(32, b"0")
        # Fernet requires URL-safe base64 encoding
        import base64

        fernet_key = base64.urlsafe_b64encode(key_bytes)
        self._cipher = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string value.

        Args:
            plaintext: String to encrypt

        Returns:
            str: Base64-encoded encrypted value with authentication tag

        Raises:
            EncryptionError: If encryption fails
            ValueError: If plaintext is empty
        """
        if not plaintext:
            raise ValueError("Plaintext cannot be empty")

        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string value.

        Args:
            ciphertext: Base64-encoded encrypted value

        Returns:
            str: Decrypted plaintext

        Raises:
            EncryptionError: If decryption fails or authentication fails
            ValueError: If ciphertext is empty
        """
        if not ciphertext:
            raise ValueError("Ciphertext cannot be empty")

        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken as e:
            raise EncryptionError("Failed to decrypt data: Invalid token or tampered data") from e
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt data: {e}") from e

    def encrypt_if_needed(self, value: str | None) -> str | None:
        """
        Encrypt a value only if it's not None and not already encrypted.

        Useful for updating fields that may already be encrypted.

        Args:
            value: String to encrypt, or None

        Returns:
            str | None: Encrypted value, or None if input was None
        """
        if value is None:
            return None

        # Check if already encrypted (Fernet tokens start with 'gAAAAA')
        if value.startswith("gAAAAA"):
            return value

        return self.encrypt(value)

    def decrypt_if_needed(self, value: str | None) -> str | None:
        """
        Decrypt a value only if it's not None and appears to be encrypted.

        Args:
            value: String to decrypt, or None

        Returns:
            str | None: Decrypted value, or None if input was None
        """
        if value is None:
            return None

        # Check if encrypted (Fernet tokens start with 'gAAAAA')
        if not value.startswith("gAAAAA"):
            return value

        try:
            return self.decrypt(value)
        except EncryptionError:
            # If decryption fails, return original value
            # This handles legacy data that wasn't encrypted
            return value


class TokenGenerator:
    """
    Cryptographically secure token generation.

    Uses the secrets module for generating tokens suitable for:
    - Session tokens
    - API keys
    - Password reset tokens
    - TOTP backup codes
    - Refresh token JTI (JWT ID)
    """

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Generate a cryptographically secure URL-safe token.

        Args:
            length: Number of bytes in the token (default: 32)

        Returns:
            str: URL-safe base64-encoded token

        Raises:
            ValueError: If length is less than 16
        """
        if length < 16:
            raise ValueError("Token length must be at least 16 bytes")

        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_api_key(length: int = 64) -> str:
        """
        Generate a secure API key.

        Args:
            length: Number of characters in the key (default: 64)

        Returns:
            str: Alphanumeric API key

        Raises:
            ValueError: If length is less than 32
        """
        if length < 32:
            raise ValueError("API key length must be at least 32 characters")

        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_numeric_code(length: int = 6) -> str:
        """
        Generate a secure numeric code.

        Useful for TOTP backup codes or verification codes.

        Args:
            length: Number of digits (default: 6)

        Returns:
            str: Numeric code

        Raises:
            ValueError: If length is less than 4
        """
        if length < 4:
            raise ValueError("Code length must be at least 4 digits")

        return "".join(secrets.choice(string.digits) for _ in range(length))

    @staticmethod
    def generate_hex_token(length: int = 32) -> str:
        """
        Generate a cryptographically secure hex token.

        Args:
            length: Number of bytes in the token (default: 32)

        Returns:
            str: Hexadecimal token

        Raises:
            ValueError: If length is less than 16
        """
        if length < 16:
            raise ValueError("Token length must be at least 16 bytes")

        return secrets.token_hex(length)


class SecureComparison:
    """
    Constant-time comparison functions to prevent timing attacks.

    Use these functions when comparing security-sensitive values like:
    - Tokens
    - API keys
    - Password reset codes
    """

    @staticmethod
    def compare_digest(a: str | bytes, b: str | bytes) -> bool:
        """
        Compare two strings or bytes in constant time.

        This prevents timing attacks where an attacker could determine
        the correct value by measuring comparison time.

        Args:
            a: First value to compare
            b: Second value to compare

        Returns:
            bool: True if values are equal, False otherwise

        Raises:
            TypeError: If types don't match
        """
        # Ensure both values are the same type
        if isinstance(a, str) and isinstance(b, str):
            a_bytes = a.encode()
            b_bytes = b.encode()
        elif isinstance(a, bytes) and isinstance(b, bytes):
            a_bytes = a
            b_bytes = b
        else:
            raise TypeError("Both values must be of the same type (str or bytes)")

        return secrets.compare_digest(a_bytes, b_bytes)


# Global instances for easy import
password_security = PasswordSecurity()
field_encryption = FieldEncryption()
token_generator = TokenGenerator()
secure_comparison = SecureComparison()


# Convenience functions
def hash_password(password: str) -> str:
    """Hash a password using Argon2id with pepper."""
    return password_security.hash_password(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a hash."""
    return password_security.verify_password(password, password_hash)


def encrypt_field(plaintext: str) -> str:
    """Encrypt a field value using Fernet."""
    return field_encryption.encrypt(plaintext)


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a field value using Fernet."""
    return field_encryption.decrypt(ciphertext)


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure token."""
    return token_generator.generate_token(length)


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time."""
    return secure_comparison.compare_digest(a, b)


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt an API key from the database.

    This is a convenience function for decrypting API keys stored
    in Instance records.

    Args:
        encrypted_api_key: Encrypted API key from database

    Returns:
        str: Decrypted API key

    Raises:
        EncryptionError: If decryption fails
    """
    return decrypt_field(encrypted_api_key)
