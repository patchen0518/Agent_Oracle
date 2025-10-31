"""
Database configuration and connection management for Oracle session management.

This module provides SQLite database configuration with SQLModel integration,
including connection management, session dependency injection, and database
initialization utilities.
"""

import os
from typing import Generator
from contextlib import contextmanager
from sqlmodel import SQLModel, create_engine, Session


# Database configuration
def get_database_url() -> str:
    """Get database URL based on environment."""
    # Use test database for testing
    if os.getenv("TESTING") == "true":
        return "sqlite:///./test_oracle_sessions.db"
    return os.getenv("DATABASE_URL", "sqlite:///./oracle_sessions.db")

DATABASE_URL = get_database_url()

# Create SQLite engine with proper configuration
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for development debugging
    connect_args={"check_same_thread": False}  # Required for SQLite with FastAPI
)


def create_db_and_tables() -> None:
    """
    Create database and all tables defined in SQLModel models.
    
    This function should be called during application startup to ensure
    all required tables exist in the database.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI to provide database sessions.
    
    This function creates a new database session for each request and
    ensures proper cleanup after the request is completed.
    
    Yields:
        Session: SQLModel database session
    """
    with Session(engine) as session:
        yield session


@contextmanager
def get_db_session():
    """
    Context manager for database sessions outside of FastAPI dependency injection.
    
    Use this for database operations in services or utilities that are not
    part of the FastAPI request cycle.
    
    Yields:
        Session: SQLModel database session
    """
    with Session(engine) as session:
        yield session


def init_database() -> None:
    """
    Initialize the database by creating all tables.
    
    This is a convenience function that can be called during application
    startup to ensure the database is properly initialized.
    """
    create_db_and_tables()


def cleanup_test_database() -> None:
    """
    Clean up test database by removing the file.
    
    This should only be used in testing environments.
    """
    if os.getenv("TESTING") == "true":
        test_db_path = "./test_oracle_sessions.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)


# Database health check function
def check_database_connection() -> bool:
    """
    Check if the database connection is working properly.
    
    Returns:
        bool: True if database connection is healthy, False otherwise
    """
    try:
        with Session(engine) as session:
            # Simple query to test connection using SQLModel text
            from sqlmodel import text
            result = session.exec(text("SELECT 1")).first()
            return result is not None
    except Exception:
        return False