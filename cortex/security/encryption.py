"""
Cortex Security - Encryption Utilities

EN 50128 / IEC 62443 compliant encryption for railway safety data at rest:
- AES-256-GCM for symmetric encryption
- Argon2id for password hashing
- Secure key derivation
- File encryption/decryption

All encryption uses industry-standard algorithms approved for safety-critical systems.
"""

import os
import base64
import hashlib
import secrets
from typing import Dict, Tuple, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = None  # Will be set by logging

# === Password Hashing ===

_password_hasher = PasswordHasher(
    time_cost=3,        # Number of iterations
    memory_cost=65536,  # Memory in KB (64 MB)
    parallelism=4,      # Number of parallel threads
    hash_len=32,        # Hash length
    salt_len=16         # Salt length
)


def hash_password(password: str) -> str:
    """
    Hash password using Argon2id (PH winner)
    
    Argon2id is the recommended algorithm for password hashing:
    - Resistant to GPU attacks
    - Memory-hard algorithm
    - Argon2id preferred over Argon2i for passwords
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    return _password_hasher.hash(password)


def verify_password(hashed_password: str, password: str) -> bool:
    """
    Verify password against hash
    
    Args:
        hashed_password: Previously hashed password
        password: Plain text password to verify
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        _password_hasher.verify(hashed_password, password)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if password hash needs rehashing
    
    Args:
        hashed_password: Previously hashed password
    
    Returns:
        True if rehashing needed (parameters changed)
    """
    return _password_hasher.check_needs_rehash(hashed_password)


# === Symmetric Encryption ===

class EncryptionManager:
    """
    AES-256-GCM encryption manager for sensitive data (EN 50128 Class B)

    Uses AES-256 in GCM (Galois/Counter Mode) for:
    - Confidentiality (encryption)
    - Integrity (authentication)
    - No separate padding needed

    EN 50128 / IEC 62443 compliant:
    - AES-256 is approved for safety-critical systems
    - GCM mode provides authenticated encryption
    - No additional integrity check needed

    Usage:
        # Initialize with master key
        enc = EncryptionManager(master_key_bytes)

        # Encrypt data
        encrypted = enc.encrypt("sensitive data")

        # Decrypt data
        plaintext = enc.decrypt(encrypted)
    """
    
    def __init__(self, master_key: bytes = None):
        """
        Initialize encryption manager
        
        Args:
            master_key: 32-byte master key for encryption
                        If not provided, generates random key
        """
        if master_key is None:
            master_key = secrets.token_bytes(32)
        
        if len(master_key) not in [16, 24, 32]:
            raise ValueError("Master key must be 16, 24, or 32 bytes (128, 192, or 256 bits)")
        
        self.master_key = master_key
        self._aesgcm = AESGCM(master_key)
    
    def encrypt(self, plaintext: str) -> Dict[str, str]:
        """
        Encrypt plaintext string
        
        Args:
            plaintext: Text to encrypt
        
        Returns:
            Dictionary with:
            - ciphertext: Base64 encoded ciphertext
            - nonce: Base64 encoded nonce (IV)
        
        Example:
            encrypted = enc.encrypt("John Doe")
            # Store encrypted["ciphertext"] and encrypted["nonce"]
        """
        # Generate random nonce (96 bits / 12 bytes recommended for GCM)
        nonce = secrets.token_bytes(12)
        
        # Encrypt
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = self._aesgcm.encrypt(nonce, plaintext_bytes, None)
        
        # Return as base64 strings for storage
        return {
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
            "nonce": base64.b64encode(nonce).decode('utf-8')
        }
    
    def decrypt(self, encrypted: Dict[str, str]) -> str:
        """
        Decrypt ciphertext
        
        Args:
            encrypted: Dictionary with ciphertext and nonce
        
        Returns:
            Decrypted plaintext string
        
        Raises:
            ValueError: If decryption fails
        
        Example:
            encrypted = {"ciphertext": "...", "nonce": "..."}
            plaintext = enc.decrypt(encrypted)
        """
        try:
            # Decode base64
            nonce = base64.b64decode(encrypted["nonce"])
            ciphertext = base64.b64decode(encrypted["ciphertext"])
            
            # Decrypt
            plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}") from e
    
    def encrypt_bytes(self, plaintext_bytes: bytes) -> Dict[str, bytes]:
        """
        Encrypt raw bytes
        
        Args:
            plaintext_bytes: Bytes to encrypt
        
        Returns:
            Dictionary with ciphertext and nonce as bytes
        """
        nonce = secrets.token_bytes(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext_bytes, None)
        
        return {
            "ciphertext": ciphertext,
            "nonce": nonce
        }
    
    def decrypt_bytes(self, encrypted: Dict[str, bytes]) -> bytes:
        """
        Decrypt raw bytes
        
        Args:
            encrypted: Dictionary with ciphertext and nonce as bytes
        
        Returns:
            Decrypted bytes
        """
        try:
            nonce = encrypted["nonce"]
            ciphertext = encrypted["ciphertext"]
            
            return self._aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}") from e
    
    def encrypt_file(self, filepath: str, output_path: str = None) -> str:
        """
        Encrypt a file
        
        Args:
            filepath: Path to file to encrypt
            output_path: Output path (default: filepath + '.enc')
        
        Returns:
            Path to encrypted file
        
        Example:
            enc_path = enc.encrypt_file("railway_asset_spec.pdf")
        """
        if output_path is None:
            output_path = filepath + '.enc'
        
        # Read file
        with open(filepath, 'rb') as f:
            plaintext = f.read()
        
        # Encrypt
        encrypted = self.encrypt_bytes(plaintext)
        
        # Write encrypted file
        # Format: [nonce_size:1][nonce][ciphertext]
        with open(output_path, 'wb') as f:
            nonce_size = len(encrypted["nonce"])
            f.write(bytes([nonce_size]))
            f.write(encrypted["nonce"])
            f.write(encrypted["ciphertext"])
        
        return output_path
    
    def decrypt_file(self, filepath: str, output_path: str) -> str:
        """
        Decrypt a file
        
        Args:
            filepath: Path to encrypted file
            output_path: Output path for decrypted file
        
        Returns:
            Path to decrypted file
        """
        # Read encrypted file
        with open(filepath, 'rb') as f:
            nonce_size = f.read(1)[0]
            nonce = f.read(nonce_size)
            ciphertext = f.read()
        
        # Decrypt
        plaintext = self.decrypt_bytes({
            "nonce": nonce,
            "ciphertext": ciphertext
        })
        
        # Write decrypted file
        with open(output_path, 'wb') as f:
            f.write(plaintext)
        
        return output_path
    
    def generate_key(self) -> bytes:
        """
        Generate new random encryption key
        
        Returns:
            32-byte random key
        """
        return secrets.token_bytes(32)


def generate_encryption_key() -> str:
    """
    Generate and encode encryption key for storage
    
    Returns:
        Base64 encoded 32-byte key
    
    Usage:
        key = generate_encryption_key()
        # Store in environment variable: export ENCRYPTION_KEY=...
    """
    return base64.b64encode(secrets.token_bytes(32)).decode('utf-8')


def load_encryption_key(encoded_key: str) -> bytes:
    """
    Load encryption key from base64 encoding
    
    Args:
        encoded_key: Base64 encoded key
    
    Returns:
        32-byte key
    """
    return base64.b64decode(encoded_key)


# === Key Management ===

class KeyManager:
    """
    Secure key management for production
    
    Provides secure key storage and retrieval:
    - Environment variables (development)
    - File with restricted permissions (self-hosted)
    - Key management service (enterprise)
    
    Usage:
        key_manager = KeyManager()
        key = key_manager.get_encryption_key()
    """
    
    def __init__(self, key_file: str = None):
        """
        Initialize key manager
        
        Args:
            key_file: Path to key file (default: ~/.cortex/keys/encryption.key)
        """
        self.key_file = key_file or os.path.expanduser("~/.cortex/keys/encryption.key")
    
    def get_encryption_key(self) -> bytes:
        """
        Get encryption key from secure storage
        
        Priority:
        1. Environment variable ENCRYPTION_KEY
        2. Key file
        3. Generate new key (first run)
        
        Returns:
            32-byte encryption key
        """
        # Try environment variable
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            try:
                return load_encryption_key(env_key)
            except Exception as e:
                logger.warning(f"Failed to load ENCRYPTION_KEY from environment: {e}")
        
        # Try key file
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to load key from file: {e}")
        
        # Generate new key
        logger.info("Generating new encryption key")
        key = secrets.token_bytes(32)
        
        # Save to file
        self._save_key(key)
        
        return key
    
    def _save_key(self, key: bytes):
        """
        Save key to file with restricted permissions
        
        Args:
            key: 32-byte key to save
        """
        # Create directory
        key_dir = os.path.dirname(self.key_file)
        os.makedirs(key_dir, mode=0o700, exist_ok=True)
        
        # Write key with restricted permissions (owner read/write only)
        with open(self.key_file, 'wb') as f:
            f.write(key)
        
        # Set permissions (Unix only)
        if os.name == 'posix':
            os.chmod(self.key_file, 0o600)
        
        logger.info(f"Encryption key saved to {self.key_file}")
    
    def rotate_key(self, new_key: bytes = None) -> bytes:
        """
        Rotate encryption key (for security)
        
        ⚠️ WARNING: This will invalidate all encrypted data!
        
        Args:
            new_key: New key (generated if not provided)
        
        Returns:
            New encryption key
        """
        if new_key is None:
            new_key = secrets.token_bytes(32)
        
        # Save new key
        self._save_key(new_key)
        
        logger.warning("Encryption key rotated - all previous encrypted data is now invalid!")
        
        return new_key


# === Sensitive Data Masking (EN 50128) ===

def mask_sensitive_data(sensitive_value: str, data_type: str) -> str:
    """
    Mask sensitive data for partially redacted display per EN 50128.

    Args:
        sensitive_value: Sensitive value to mask
        data_type: Type of data (ssn, phone, email, mrn, name, etc.)

    Returns:
        Partially masked value

    Examples:
        mask_sensitive_data("123-45-6789", "ssn") -> "***-**-6789"
        mask_sensitive_data("555-123-4567", "phone") -> "***-***-4567"
        mask_sensitive_data("john.doe@email.com", "email") -> "jo***@email.com"
    """
    if data_type == "ssn":
        # SSN: show last 4 digits
        return "***-**-" + sensitive_value[-4:]

    elif data_type == "phone":
        # Phone: show last 4 digits
        return "***-***-" + sensitive_value[-4:]

    elif data_type == "email":
        # Email: show first 2 chars and domain
        parts = sensitive_value.split("@")
        if len(parts) == 2:
            username = parts[0]
            domain = parts[1]
            masked = username[:2] + "***@" + domain
            return masked

    elif data_type == "mrn":
        # MRN: show last 3 digits
        return "***" + sensitive_value[-3:]

    elif data_type == "name":
        # Name: show first letter
        return sensitive_value[0] + "***"

    # Default: full mask
    return "[REDACTED]"


# Backward compatibility alias
mask_phi = mask_sensitive_data


# === Utility Functions ===

def secure_delete(file_path: str, passes: int = 3):
    """
    Securely delete file by overwriting before deletion
    
    Args:
        file_path: Path to file to delete
        passes: Number of overwrite passes (default: 3)
    
    Note: Follows DoD 5220.22-M standard for secure deletion
    """
    if not os.path.exists(file_path):
        return
    
    file_size = os.path.getsize(file_path)
    
    # Overwrite multiple times
    with open(file_path, 'r+b') as f:
        for _ in range(passes):
            f.seek(0)
            f.write(os.urandom(file_size))
            f.flush()
            os.fsync(f.fileno())
    
    # Delete file
    os.remove(file_path)


# === Export ===

__all__ = [
    "hash_password",
    "verify_password",
    "needs_rehash",
    "EncryptionManager",
    "KeyManager",
    "generate_encryption_key",
    "load_encryption_key",
    "mask_phi",
    "mask_sensitive_data",
    "secure_delete",
]