"""
Cortex Security Package

HIPAA-compliant security features:
- Authentication (JWT)
- Authorization (RBAC)
- Encryption (AES-256)
- PHI Protection
"""

from cortex.security.encryption import (
    EncryptionManager,
    KeyManager,
    hash_password,
    verify_password,
    generate_encryption_key,
    load_encryption_key,
    mask_phi,
    secure_delete,
)

from cortex.security.auth import (
    AuthManager,
    AuthenticationError,
    AccountLockedError,
    TokenExpiredError,
    get_auth_manager,
    get_current_user,
    get_current_active_user,
)

__all__ = [
    # Encryption
    "EncryptionManager",
    "KeyManager",
    "hash_password",
    "verify_password",
    "generate_encryption_key",
    "load_encryption_key",
    "mask_phi",
    "secure_delete",
    # Authentication
    "AuthManager",
    "AuthenticationError",
    "AccountLockedError",
    "TokenExpiredError",
    "get_auth_manager",
    "get_current_user",
    "get_current_active_user",
]