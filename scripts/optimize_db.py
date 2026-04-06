#!/usr/bin/env python3
"""
Database Optimization Script

This script optimizes the database for HIPAA compliance and performance:
- Creates indexes for frequently queried columns
- Analyzes query performance
- Sets up connection pool monitoring
- Vacuum and analyze tables
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cortex.database import get_database_manager
from cortex.models import (
    AuditLog, User, Patient, ConsentRecord,
    SecurityIncident, BreachNotification
)
from sqlalchemy import text
import structlog

logger = structlog.get_logger()


def create_indexes():
    """Create performance indexes"""
    db = get_database_manager()
    
    print("\nCreating performance indexes...")
    
    indexes = [
        # Audit log indexes
        ("idx_audit_log_user_timestamp", "audit_log", ["user_id", "timestamp"]),
        ("idx_audit_log_patient_timestamp", "audit_log", ["patient_id", "timestamp"]),
        ("idx_audit_log_action_timestamp", "audit_log", ["action", "timestamp"]),
        ("idx_audit_log_timestamp_desc", "audit_log", ["timestamp DESC"]),
        
        # User indexes
        ("idx_users_email", "users", ["email"]),
        ("idx_users_role", "users", ["role"]),
        ("idx_users_active", "users", ["is_active"]),
        
        # Patient indexes
        ("idx_patients_mrn", "patients", ["mrn"]),
        ("idx_patients_created", "patients", ["created_at DESC"]),
        
        # Consent indexes
        ("idx_consent_patient_date", "consent_records", ["patient_id", "consent_date DESC"]),
        ("idx_consent_type_date", "consent_records", ["consent_type", "consent_date"]),
        
        # Security incident indexes
        ("idx_incident_status", "security_incidents", ["status", "report_date DESC"]),
        ("idx_incident_severity", "security_incidents", ["severity", "report_date DESC"]),
        
        # Breach notification indexes
        ("idx_breach_status", "breach_notifications", ["notification_status"]),
        ("idx_breach_date", "breach_notifications", ["breach_date DESC"]),
    ]
    
    created = 0
    skipped = 0
    failed = 0
    
    with db.get_session() as session:
        for index_name, table_name, columns in indexes:
            try:
                # Check if index exists
                check_sql = text("""
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = :index_name
                """)
                result = session.execute(check_sql, {"index_name": index_name})
                
                if result.fetchone():
                    print(f"  ✓ Index {index_name} already exists")
                    skipped += 1
                    continue
                
                # Create index
                columns_sql = ", ".join(columns)
                create_sql = text(f"CREATE INDEX {index_name} ON {table_name} ({columns_sql})")
                session.execute(create_sql)
                session.commit()
                
                print(f"  ✓ Created index {index_name}")
                created += 1
                
            except Exception as e:
                print(f"  ✗ Failed to create index {index_name}: {e}")
                session.rollback()
                failed += 1
    
    print(f"\nIndex creation complete:")
    print(f"  Created: {created}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")


def analyze_tables():
    """Analyze tables for query optimization"""
    db = get_database_manager()
    
    print("\nAnalyzing tables for query optimization...")
    
    tables = [
        "users", "sessions", "patients", "consent_records",
        "audit_log", "security_incidents", "breach_notifications",
        "care_teams", "care_notes", "care_tasks"
    ]
    
    with db.get_session() as session:
        for table in tables:
            try:
                session.execute(text(f"ANALYZE {table}"))
                print(f"  ✓ Analyzed {table}")
            except Exception as e:
                print(f"  ✗ Failed to analyze {table}: {e}")
        
        session.commit()
    
    print("\nTable analysis complete")


def vacuum_tables():
    """Vacuum tables to reclaim space"""
    db = get_database_manager()
    
    print("\nVacuuming tables...")
    
    tables = [
        "audit_log", "users", "patients", "consent_records"
    ]
    
    with db.get_session() as session:
        for table in tables:
            try:
                # Note: VACUUM cannot run inside transaction block
                # This would need to be run with autocommit
                print(f"  Note: VACUUM {table} requires autocommit mode")
            except Exception as e:
                print(f"  ✗ Failed to vacuum {table}: {e}")
    
    print("Vacuum requires running with autocommit or separate connection")


def check_query_performance():
    """Check query performance for common queries"""
    db = get_database_manager()
    
    print("\nChecking query performance...")
    
    queries = [
        ("Audit log by user", "EXPLAIN ANALYZE SELECT * FROM audit_log WHERE user_id = '00000000-0000-0000-0000-000000000000' LIMIT 100"),
        ("Audit log by date", "EXPLAIN ANALYZE SELECT * FROM audit_log WHERE timestamp > NOW() - INTERVAL '7 days' LIMIT 100"),
        ("Patient search", "EXPLAIN ANALYZE SELECT * FROM patients WHERE mrn = 'MRN-00000'"),
        ("Consent by patient", "EXPLAIN ANALYZE SELECT * FROM consent_records WHERE patient_id = '00000000-0000-0000-0000-000000000000'"),
    ]
    
    with db.get_session() as session:
        for name, query in queries:
            try:
                result = session.execute(text(query))
                plan = "\n".join([row[0] for row in result])
                
                # Check for index usage
                if "Index Scan" in plan:
                    print(f"  ✓ {name}: Index scan used")
                elif "Seq Scan" in plan:
                    print(f"  ⚠ {name}: Sequential scan (consider adding index)")
                else:
                    print(f"  ℹ {name}: Check execution plan")
                    
            except Exception as e:
                print(f"  ✗ {name}: Query failed - {e}")


def get_table_sizes():
    """Get table sizes"""
    db = get_database_manager()
    
    print("\nTable sizes:")
    
    with db.get_session() as session:
        query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """)
        
        result = session.execute(query)
        
        print(f"  {'Table':<30} {'Total Size':<15} {'Table Size':<15} {'Index Size':<15}")
        print("  " + "-" * 75)
        
        for row in result:
            print(f"  {row[1]:<30} {row[2]:<15} {row[3]:<15} {row[4]:<15}")


def get_connection_pool_stats():
    """Get connection pool statistics"""
    db = get_database_manager()
    
    print("\nConnection pool statistics:")
    
    # Get pool from engine
    pool = db.engine.pool
    
    print(f"  Pool size: {pool.size()}")
    print(f"  Checked out: {pool.checkedout()}")
    print(f"  Overflow: {pool.overflow()}")
    print(f"  Checked in: {pool.checkedin()}")
    
    # Get connection info
    query = text("""
        SELECT 
            count(*) as total_connections,
            state,
            usename
        FROM pg_stat_activity
        WHERE datname = current_database()
        GROUP BY state, usename
    """)
    
    try:
        with db.get_session() as session:
            result = session.execute(query)
            
            print("\nActive database connections:")
            for row in result:
                print(f"  {row[2]}: {row[0]} ({row[1]})")
    except Exception as e:
        print(f"  Could not retrieve connection stats: {e}")


def optimize_connection_pool():
    """Optimize connection pool configuration"""
    print("\nConnection pool optimization:")
    
    recommended_settings = """
    Recommended connection pool settings for production:
    
    - pool_size: 20-50 (depending on CPU cores)
    - max_overflow: 10-20
    - pool_timeout: 30 seconds
    - pool_recycle: 3600 seconds (1 hour)
    - pool_pre_ping: True (health check)
    - echo_pool: False (set True for debugging)
    
    For PostgreSQL, also consider:
    - statement_timeout: 30000ms (30 seconds)
    - idle_in_transaction_session_timeout: 60000ms (60 seconds)
    """
    
    print(recommended_settings)


def run_optimization():
    """Run all optimizations"""
    print("=" * 80)
    print("DATABASE OPTIMIZATION")
    print("=" * 80)
    
    try:
        create_indexes()
    except Exception as e:
        logger.error(f"Index creation failed: {e}")
    
    try:
        analyze_tables()
    except Exception as e:
        logger.error(f"Table analysis failed: {e}")
    
    try:
        check_query_performance()
    except Exception as e:
        logger.error(f"Performance check failed: {e}")
    
    try:
        get_table_sizes()
    except Exception as e:
        logger.error(f"Table size query failed: {e}")
    
    try:
        get_connection_pool_stats()
    except Exception as e:
        logger.error(f"Connection pool stats failed: {e}")
    
    optimize_connection_pool()
    
    print("\n" + "=" * 80)
    print("OPTIMIZATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_optimization()