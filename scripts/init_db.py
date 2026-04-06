"""
Database Migration Script

Initialize PostgreSQL database for Healthcare Compliance Agent.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --create-tables
    python scripts/init_db.py --seed-data
    python scripts/init_db.py --reset
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.exc import SQLAlchemyError
from cortex.database import get_database_manager, initialize_database
from cortex.models import (
    Base, User, Role, UserRoleMapping, Patient, ConsentRecord,
    AuditLog, CareTeam, CareTeamMember, CareNote, CareTask,
    RetentionPolicy, RetentionSchedule, SecurityIncident, BreachNotification,
    ICD10Code, CPTCode, CodeMapping, RequestMetric,
    initialize_default_data, UserRole
)
from cortex.encryption import EncryptionManager


def create_tables(db):
    """Create all database tables"""
    print("\n=== Creating Database Tables ===\n")
    
    try:
        Base.metadata.create_all(db._engine)
        print("✓ All tables created successfully")
        
        # List tables
        from sqlalchemy import inspect
        inspector = inspect(db._engine)
        tables = inspector.get_table_names()
        
        print(f"\nCreated {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")
        
        return True
    except SQLAlchemyError as e:
        print(f"✗ Error creating tables: {e}")
        return False


def seed_default_data(db):
    """Seed database with default data"""
    print("\n=== Seeding Default Data ===\n")
    
    try:
        with db.get_session() as session:
            # Check if roles already exist
            existing_roles = session.query(Role).count()
            
            if existing_roles > 0:
                print("  Default data already exists, skipping...")
                return True
            
            # Create default roles
            roles_data = [
                Role(
                    name="admin",
                    description="Administrator with full access",
                    permissions=["*"]
                ),
                Role(
                    name="clinician",
                    description="Clinical staff with PHI access",
                    permissions=[
                        "patient:read", "patient:write",
                        "document:read", "document:write", "document:delete",
                        "agent:run",
                        "memory:read", "memory:write"
                    ]
                ),
                Role(
                    name="researcher",
                    description="Research staff with anonymized data access",
                    permissions=[
                        "document:read",
                        "agent:run",
                        "data:anonymized",
                        "memory:read"
                    ]
                ),
                Role(
                    name="auditor",
                    description="Compliance auditor with read-only access",
                    permissions=[
                        "audit:read",
                        "logs:read",
                        "compliance:read"
                    ]
                )
            ]
            
            for role in roles_data:
                session.add(role)
            
            print(f"✓ Created {len(roles_data)} default roles")
            
            # Create default retention policies
            retention_policies = [
                RetentionPolicy(
                    resource_type="patient",
                    retention_years=6,
                    retention_trigger="last_access",
                    delete_after_retention=True,
                    archive_before_delete=True
                ),
                RetentionPolicy(
                    resource_type="document",
                    retention_years=6,
                    retention_trigger="creation",
                    delete_after_retention=True,
                    archive_before_delete=True
                ),
                RetentionPolicy(
                    resource_type="audit_log",
                    retention_years=6,
                    retention_trigger="creation",
                    delete_after_retention=False,
                    archive_before_delete=True
                ),
                RetentionPolicy(
                    resource_type="consent",
                    retention_years=6,
                    retention_trigger="last_access",
                    delete_after_retention=False,
                    archive_before_delete=True
                ),
                RetentionPolicy(
                    resource_type="care_note",
                    retention_years=6,
                    retention_trigger="creation",
                    delete_after_retention=False,
                    archive_before_delete=True
                ),
                RetentionPolicy(
                    resource_type="security_incident",
                    retention_years=6,
                    retention_trigger="creation",
                    delete_after_retention=False,
                    archive_before_delete=True
                )
            ]
            
            for policy in retention_policies:
                session.add(policy)
            
            print(f"✓ Created {len(retention_policies)} retention policies")
            
            session.commit()
            
            return True
    except SQLAlchemyError as e:
        print(f"✗ Error seeding data: {e}")
        return False


def create_admin_user(db):
    """Create default admin user"""
    print("\n=== Creating Admin User ===\n")
    
    try:
        with db.get_session() as session:
            # Check if admin exists
            admin_exists = session.query(User).filter(User.email == "admin@localhost").first()
            
            if admin_exists:
                print("  Admin user already exists")
                return True
            
            # Get encryption manager
            encryption_key = os.getenv("ENCRYPTION_KEY")
            if not encryption_key:
                print("  Warning: ENCRYPTION_KEY not set, using default (not for production)")
                encryption_key = "default-encryption-key-change-in-production"
            
            encryption = EncryptionManager(encryption_key.encode())
            
            # Create admin user
            from datetime import timedelta
            from cortex.security.auth_utils import hash_password
            
            admin = User(
                email="admin@localhost",
                password_hash=hash_password("AdminPass123!"),
                full_name_encrypted=encryption.encrypt("System Administrator")["ciphertext"],
                role=UserRole.ADMIN,
                is_active=True
            )
            
            session.add(admin)
            
            # Assign admin role
            admin_role = session.query(Role).filter(Role.name == "admin").first()
            if admin_role:
                user_role = UserRoleMapping(
                    user_id=admin.id,
                    role_id=admin_role.id
                )
                session.add(user_role)
            
            session.commit()
            
            print("✓ Created admin user:")
            print(f"  Email: admin@localhost")
            print(f"  Password: AdminPass123!")
            print(f"  Role: admin")
            print("\n  ⚠️  Please change the password immediately after first login!")
            
            return True
    except Exception as e:
        print(f"✗ Error creating admin user: {e}")
        return False


def verify_database(db):
    """Verify database integrity"""
    print("\n=== Verifying Database ===\n")
    
    try:
        with db.get_session() as session:
            # Count tables
            tables_count = {}
            
            tables_count["users"] = session.query(User).count()
            tables_count["roles"] = session.query(Role).count()
            tables_count["retention_policies"] = session.query(RetentionPolicy).count()
            
            print("Database Statistics:")
            for table, count in tables_count.items():
                print(f"  {table}: {count} records")
            
            # Test health check
            if db.health_check():
                print("\n✓ Database connection healthy")
            else:
                print("\n✗ Database connection failed")
                return False
            
            # Get pool status
            pool_status = db.get_pool_status()
            print(f"\nConnection Pool:")
            print(f"  Pool size: {pool_status.get('pool_size', 'N/A')}")
            print(f"  Current size: {pool_status.get('current_size', 'N/A')}")
            print(f"  Checked in: {pool_status.get('checked_in', 'N/A')}")
            print(f"  Checked out: {pool_status.get('checked_out', 'N/A')}")
            
            return True
    except Exception as e:
        print(f"✗ Error verifying database: {e}")
        return False


def reset_database(db):
    """Drop and recreate all tables"""
    print("\n=== Resetting Database ===\n")
    print("⚠️  WARNING: This will delete all data!\n")
    
    response = input("Are you sure you want to reset the database? (yes/no): ")
    
    if response.lower() != "yes":
        print("Reset cancelled")
        return False
    
    print("\nDropping all tables...")
    Base.metadata.drop_all(db._engine)
    print("✓ Tables dropped")
    
    print("\nRecreating tables...")
    Base.metadata.create_all(db._engine)
    print("✓ Tables created")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Healthcare Compliance Agent database"
    )
    
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create database tables"
    )
    
    parser.add_argument(
        "--seed-data",
        action="store_true",
        help="Seed default data (roles, policies)"
    )
    
    parser.add_argument(
        "--create-admin",
        action="store_true",
        help="Create default admin user"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (drop and recreate all tables)"
    )
    
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify database integrity"
    )
    
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="PostgreSQL connection URL (overrides DATABASE_URL env var)"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all initialization steps (create tables, seed data, create admin)"
    )
    
    args = parser.parse_args()
    
    # Set database URL if provided
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    
    # Get database manager
    try:
        db = get_database_manager()
        print("✓ Database manager initialized")
    except Exception as e:
        print(f"✗ Failed to initialize database manager: {e}")
        sys.exit(1)
    
    # Run requested operations
    success = True
    
    if args.reset:
        success = reset_database(db) and success
    
    if args.all or args.create_tables:
        success = create_tables(db) and success
    
    if args.all or args.seed_data:
        success = seed_default_data(db) and success
    
    if args.all or args.create_admin:
        success = create_admin_user(db) and success
    
    if args.verify:
        success = verify_database(db) and success
    
    # If no args provided, show help
    if not any([args.reset, args.create_tables, args.seed_data, args.create_admin, args.verify, args.all]):
        parser.print_help()
        sys.exit(0)
    
    # Final status
    if success:
        print("\n" + "="*50)
        print("✓ Database initialization successful")
        print("="*50 + "\n")
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("✗ Database initialization failed")
        print("="*50 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()