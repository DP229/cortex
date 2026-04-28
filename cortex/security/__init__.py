"""
Cortex Security Package - IEC 62443 / EN 50128 Class B Compliant

Railway safety compliant security features:
- Authentication (JWT)
- Authorization (RBAC)
- Encryption (AES-256-GCM)
- Railway Data Minimization
- IAM Gateway (Ollama protection)
- Immutable Audit Logging (Merkle tree)
- PII masking for logs
"""

from cortex.security.encryption import (
    EncryptionManager,
    KeyManager,
    hash_password,
    verify_password,
    generate_encryption_key,
    load_encryption_key,
    mask_phi,
    mask_sensitive_data,
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

from cortex.security.iam_gateway import (
    IAMGateway,
    IAMAction,
    IAMRequest,
    IAMPolicy,
    OllamaProxy,
    get_iam_gateway,
    get_ollama_proxy,
)

from cortex.security.immutable_audit import (
    ImmutableAuditLogger,
    AuditLogEntry,
    SecurityEventType,
    OTelAuditLogger,
    get_audit_logger,
    log_security_event,
)

from cortex.security.data_minimization import (
    DataMinimizer,
    DataMinimizationConfig,
    DataCategory,
    MaskedValue,
    SafeLogger,
    get_data_minimizer,
    get_safe_logger,
    mask_for_logging,
    mask_dict_for_logging,
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
    # IAM Gateway
    "IAMGateway",
    "IAMAction",
    "IAMRequest",
    "IAMPolicy",
    "OllamaProxy",
    "get_iam_gateway",
    "get_ollama_proxy",
    # Immutable Audit
    "ImmutableAuditLogger",
    "AuditLogEntry",
    "SecurityEventType",
    "OTelAuditLogger",
    "get_audit_logger",
    "log_security_event",
    # Data Minimization
    "DataMinimizer",
    "DataMinimizationConfig",
    "DataCategory",
    "MaskedValue",
    "SafeLogger",
    "get_data_minimizer",
    "get_safe_logger",
    "mask_for_logging",
    "mask_dict_for_logging",
]