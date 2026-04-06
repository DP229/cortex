"""
Cortex Database - PostgreSQL Connection Pool Manager

Provides robust database connection management:
- Connection pooling for performance
- Automatic reconnection on failure
- Transaction management
- Context managers for safe connection handling
- Health checks and monitoring
"""

import os
import logging
from typing import Optional, ContextManager
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

from cortex.models import Base, create_all_tables, initialize_default_data

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    PostgreSQL database manager with connection pooling
    
    Features:
    - Connection pooling (configurable pool size)
    - Automatic reconnection
    - Transaction management
    - Health checks
    - Thread-safe sessions
    
    Usage:
        db = DatabaseManager(database_url)
        
        # Using context manager
        with db.get_session() as session:
            user = session.query(User).first()
        
        # Using connection
        with db.get_connection() as conn:
            result = conn.execute("SELECT 1")
    """
    
    def __init__(
        self,
        database_url: str = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False
    ):
        """
        Initialize database manager
        
        Args:
            database_url: PostgreSQL connection URL
            pool_size: Number of connections to keep in pool
            max_overflow: Max additional connections when pool is full
            pool_timeout: Seconds to wait for connection from pool
            pool_recycle: Recycle connections after N seconds
            echo: Echo SQL statements to logs (for debugging)
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://healthcare:password@localhost:5432/healthcare"
        )
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.echo = echo
        
        self._engine = None
        self._session_factory = None
        self._scoped_session = None
        
        # Initialize
        self._initialize()
    
    def _initialize(self):
        """Initialize engine and session factory"""
        
        logger.info(f"Initializing database connection pool (size={self.pool_size})")
        
        # Create engine with pooling
        self._engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,  # Check connection health before using
            echo=self.echo
        )
        
        # Add event listeners for connection management
        self._add_event_listeners()
        
        # Create session factory
        self._session_factory = sessionmaker(bind=self._engine)
        
        # Create scoped session for thread safety
        self._scoped_session = scoped_session(self._session_factory)
        
        logger.info("Database connection pool initialized successfully")
    
    def _add_event_listeners(self):
        """Add SQLAlchemy event listeners"""
        
        @event.listens_for(self._engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """Log new connections"""
            logger.debug(f"Database connection created: {id(dbapi_connection)}")
        
        @event.listens_for(self._engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log connection checkout"""
            logger.debug(f"Connection checkout: {id(dbapi_connection)}")
        
        @event.listens_for(self._engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log connection checkin"""
            logger.debug(f"Connection checkin: {id(dbapi_connection)}")
        
        @event.listens_for(self._engine, "close")
        def receive_close(dbapi_connection, connection_record):
            """Log connection close"""
            logger.debug(f"Connection closed: {id(dbapi_connection)}")
    
    def create_tables(self):
        """Create all tables in database"""
        try:
            create_all_tables(self._engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def initialize_data(self):
        """Initialize default data (roles, retention policies)"""
        with self.get_session() as session:
            try:
                initialize_default_data(session)
                logger.info("Default data initialized successfully")
            except SQLAlchemyError as e:
                logger.error(f"Failed to initialize data: {e}")
                session.rollback()
                raise
    
    @contextmanager
    def get_session(self) -> ContextManager[Session]:
        """
        Get database session with automatic cleanup
        
        Usage:
            with db.get_session() as session:
                user = session.query(User).first()
        """
        session = None
        try:
            session = self._session_factory()
            yield session
            session.commit()
        except SQLAlchemyError as e:
            if session:
                session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if session:
                session.close()
    
    @contextmanager
    def get_connection(self):
        """
        Get raw database connection
        
        Usage:
            with db.get_connection() as conn:
                result = conn.execute("SELECT 1")
        """
        conn = None
        try:
            conn = self._engine.connect()
            yield conn
        except SQLAlchemyError as e:
            logger.error(f"Connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def health_check(self) -> bool:
        """
        Check database connection health
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            with self.get_connection() as conn:
                result = conn.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def get_pool_status(self) -> dict:
        """
        Get connection pool status
        
        Returns:
            Dictionary with pool status
        """
        try:
            pool = self._engine.pool
            return {
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "current_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow_count": pool.overflow(),
                "is_full": pool.overflow() >= self.max_overflow,
            }
        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            return {}
    
    def close(self):
        """Close all connections and cleanup"""
        try:
            if self._scoped_session:
                self._scoped_session.remove()
            
            if self._engine:
                self._engine.dispose()
            
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# === Global database instance ===

_db_instance: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """
    Get global database manager instance
    
    Returns:
        DatabaseManager instance
    """
    global _db_instance
    
    if _db_instance is None:
        _db_instance = DatabaseManager()
    
    return _db_instance


def get_session() -> ContextManager[Session]:
    """
    Convenience function to get database session
    
    Usage:
        with get_session() as session:
            user = session.query(User).first()
    
    Returns:
        Context manager yielding Session
    """
    db = get_database_manager()
    return db.get_session()


# === Initialization function ===

def initialize_database(create_tables: bool = True, create_data: bool = True):
    """
    Initialize database for Healthcare Compliance Agent
    
    Args:
        create_tables: Create tables if they don't exist
        create_data: Create default data (roles, policies)
    
    Usage:
        from cortex.database import initialize_database
        initialize_database()
    """
    db = get_database_manager()
    
    if create_tables:
        db.create_tables()
    
    if create_data:
        db.initialize_data()
    
    logger.info("Database initialization complete")
    
    return db


# === Export ===

__all__ = [
    "DatabaseManager",
    "get_database_manager",
    "get_session",
    "initialize_database",
]