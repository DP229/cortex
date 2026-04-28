#!/usr/bin/env python3
"""
Cortex Railway Safety Platform - Main Entry Point

Start the Cortex Railway Safety Compliance API server.

Usage:
    python -m cortex.main
    python -m cortex.main --host 0.0.0.0 --port 8080
    python -m cortex.main --init-db
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def setup_environment():
    """Setup environment and configuration"""
    # Load environment variables from .env file
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"✓ Loaded environment from {env_file}")
    else:
        print("⚠ No .env file found, using environment variables")
    
    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE")
    audit_log_file = os.getenv("AUDIT_LOG_FILE")
    
    from cortex.logging_config import setup_logging
    setup_logging(
        log_level=log_level,
        log_file=log_file,
        audit_log_file=audit_log_file,
        json_format=True
    )
    
    print(f"✓ Logging configured (level={log_level})")


def initialize_database():
    """Initialize database with tables and default data"""
    from cortex.database import initialize_database
    
    print("\n=== Initializing Database ===\n")
    
    try:
        initialize_database(create_tables=True, create_data=True)
        print("\n✓ Database initialized successfully")
        return True
    except Exception as e:
        print(f"\n✗ Database initialization failed: {e}")
        return False


def generate_keys():
    """Generate encryption and JWT keys"""
    import secrets
    import base64

    print("\n=== Generating Security Keys ===\n")

    # Generate encryption key
    encryption_key = base64.b64encode(secrets.token_bytes(32)).decode()
    print(f"ENCRYPTION_KEY={encryption_key}")  # Intentionally shown — user must capture and store

    # Generate JWT secret
    jwt_secret = secrets.token_urlsafe(32)
    print(f"JWT_SECRET={jwt_secret}")  # Intentionally shown

    print("\n⚠ WARNING: Store these keys securely!")
    print("Add them to your .env file or environment variables.")
    print("⚠ Never commit these keys to version control.\n")


def run_server(host: str, port: int, reload: bool):
    """Run the FastAPI server"""
    import uvicorn
    
    print(f"\n=== Starting Cortex Railway Safety Platform API ===\n")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Database: {os.getenv('DATABASE_URL', 'sqlite://~/.cortex/cortex.db')}")
    print(f"\nAPI Documentation: http://{host}:{port}/docs")
    print(f"Health Check: http://{host}:{port}/health")
    print(f"\nPress Ctrl+C to stop\n")
    
    uvicorn.run(
        "cortex.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Cortex Railway Safety Platform - EN 50128 Class B Compliant AI Knowledge Base"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to (default: 8080)"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database and exit"
    )
    
    parser.add_argument(
        "--generate-keys",
        action="store_true",
        help="Generate encryption and JWT keys"
    )
    
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration and exit"
    )
    
    args = parser.parse_args()
    
    # Setup environment
    setup_environment()
    
    # Handle commands
    if args.init_db:
        success = initialize_database()
        sys.exit(0 if success else 1)
    
    if args.generate_keys:
        generate_keys()
        sys.exit(0)
    
    if args.check_config:
        print("\n=== Configuration Check ===\n")
        
        # Check required environment variables
        required_vars = [
            ("DATABASE_URL", "postgresql://..."),
            ("ENCRYPTION_KEY", "base64-encoded-32-byte-key"),
            ("JWT_SECRET", "long-random-string"),
        ]
        
        missing = []
        for var, expected in required_vars:
            value = os.getenv(var)
            if value:
                # Mask sensitive values
                if len(value) > 20:
                    masked = value[:10] + "..." + value[-5:]
                else:
                    masked = "***"
                print(f"✓ {var}={masked}")
            else:
                print(f"✗ {var} not set (expected: {expected})")
                missing.append(var)
        
        # Check database connection
        print("\n=== Database Connection ===\n")
        try:
            from cortex.database import get_database_manager
            db = get_database_manager()
            if db.health_check():
                print("✓ Database connection successful")
            else:
                print("✗ Database health check failed")
                missing.append("database_connection")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            missing.append("database_connection")
        
        # Check encryption
        print("\n=== Encryption ===\n")
        try:
            from cortex.security.encryption import EncryptionManager
            encryption_key = os.getenv("ENCRYPTION_KEY")
            if encryption_key:
                # Test encryption
                enc = EncryptionManager(encryption_key.encode() if encryption_key else None)
                test_text = "test"
                encrypted = enc.encrypt(test_text)
                decrypted = enc.decrypt(encrypted)
                
                if decrypted == test_text:
                    print("✓ Encryption working correctly")
                else:
                    print("✗ Encryption/decryption mismatch")
                    missing.append("encryption")
            else:
                print("⚠ ENCRYPTION_KEY not set, using default (not for production)")
        except Exception as e:
            print(f"✗ Encryption check failed: {e}")
            missing.append("encryption")
        
        if missing:
            print(f"\n✗ Configuration check failed. Missing: {', '.join(missing)}")
            sys.exit(1)
        else:
            print("\n✓ Configuration check passed")
            sys.exit(0)
    
    # Run server
    try:
        run_server(args.host, args.port, args.reload)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()