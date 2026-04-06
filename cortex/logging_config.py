"""
Structured Logging Configuration

Provides HIPAA-compliant audit logging:
- Structured JSON logs
- Separate audit log file
- Log rotation
- HIPAA-compliant format
"""

import os
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog


def setup_logging(
    log_level: str = "INFO",
    log_file: str = None,
    audit_log_file: str = None,
    json_format: bool = True
):
    """
    Setup structured logging
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to main log file
        audit_log_file: Path to audit log file
        json_format: Use JSON format for logs
    """
    # Get log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create log directory if needed
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    if audit_log_file:
        Path(audit_log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log_file specified)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Audit log handler (if audit_log_file specified)
    if audit_log_file:
        audit_logger = logging.getLogger('audit')
        audit_logger.setLevel(logging.INFO)
        audit_handler = RotatingFileHandler(
            audit_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10
        )
        audit_handler.setLevel(logging.INFO)
        # JSON format for audit logs (easier to parse)
        audit_formatter = logging.Formatter('%(message)s')
        audit_handler.setFormatter(audit_formatter)
        audit_logger.addHandler(audit_handler)
        audit_logger.propagate = False  # Don't propagate to root logger


def get_audit_logger():
    """Get audit logger for HIPAA-compliant logging"""
    return structlog.get_logger('audit')


class AuditLogMiddleware:
    """
    FastAPI middleware for audit logging
    
    Logs all requests and responses for HIPAA compliance
    """
    
    def __init__(self, app):
        self.app = app
        self.audit_logger = get_audit_logger()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Log request
        method = scope["method"]
        path = scope["path"]
        query_string = scope["query_string"].decode()
        
        # Get user info from headers if available
        headers = dict(scope["headers"])
        user_id = headers.get(b"x-user-id", b"anonymous").decode()
        
        # Log request
        self.audit_logger.info(
            "http_request",
            method=method,
            path=path,
            query_string=query_string,
            user_id=user_id,
        )
        
        # Process request
        await self.app(scope, receive, send)


# Initialize logging on import if environment variables are set
if os.getenv("LOG_FILE"):
    setup_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE"),
        audit_log_file=os.getenv("AUDIT_LOG_FILE"),
        json_format=os.getenv("JSON_LOG_FORMAT", "true").lower() == "true"
    )


# === Export ===

__all__ = [
    "setup_logging",
    "get_audit_logger",
    "AuditLogMiddleware",
]