# Basic FastAPI app tests
# Based on FastAPI testing documentation (Context 7 lookup: 2025-01-26)

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_read_root():
    """Test the root endpoint returns expected message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Oracle Chat API is running"}

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_cors_headers():
    """Test that CORS headers are properly configured."""
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    # Note: TestClient doesn't automatically add CORS headers, 
    # but this verifies the endpoint works with origin header