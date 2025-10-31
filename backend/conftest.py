"""
Pytest configuration and fixtures for Oracle Chat API tests.

This module provides shared test fixtures and configuration for all test files.
"""

import os
import pytest
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

# Set testing environment variable
os.environ["TESTING"] = "true"

from backend.main import app
from backend.config.database import get_session, cleanup_test_database
from backend.models.session_models import Session, Message


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment and clean up after all tests."""
    # Setup
    os.environ["TESTING"] = "true"
    
    yield
    
    # Cleanup
    cleanup_test_database()


@pytest.fixture(name="test_engine")
def test_engine_fixture():
    """Create a test database engine using in-memory SQLite."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(name="test_session")
def test_session_fixture(test_engine):
    """Create a test database session."""
    from sqlmodel import SQLModel
    
    # Create all tables
    SQLModel.metadata.create_all(test_engine)
    
    with Session(test_engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(test_session: Session):
    """Create a test client with test database session."""
    def get_test_session():
        return test_session

    app.dependency_overrides[get_session] = get_test_session
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(name="db_session")
def db_session_fixture(test_session):
    """Alias for test_session for backward compatibility."""
    return test_session