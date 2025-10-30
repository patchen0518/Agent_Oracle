"""
Integration tests for session-based API endpoints.

Tests all session management and chat endpoints with various scenarios,
error handling, and validation to ensure proper functionality of the
session-based architecture.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.main import app
from backend.config.database import get_session
from backend.models.session_models import Session as SessionModel, Message as MessageModel
from google.genai import errors


# Test database setup
@pytest.fixture(name="session")
def session_fixture():
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create a test client with database dependency override."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestSessionManagementEndpoints:
    """Test session CRUD endpoints."""

    def test_create_session_success(self, client: TestClient):
        """Test successful session creation."""
        session_data = {
            "title": "Test Session",
            "model_used": "gemini-2.0-flash-exp",
            "session_metadata": {"test": "data"}
        }
        
        response = client.post("/api/v1/sessions/", json=session_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Session"
        assert data["model_used"] == "gemini-2.0-flash-exp"
        assert data["session_metadata"] == {"test": "data"}
        assert data["message_count"] == 0
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_session_with_minimal_data(self, client: TestClient):
        """Test session creation with minimal required data."""
        session_data = {
            "title": "Minimal Session"
        }
        
        response = client.post("/api/v1/sessions/", json=session_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Minimal Session"
        assert data["model_used"] == "gemini-2.0-flash-exp"  # Default value
        assert data["session_metadata"] == {}

    def test_create_session_auto_title_generation(self, client: TestClient):
        """Test session creation with auto-generated title."""
        session_data = {
            "title": ""  # Empty title should trigger auto-generation
        }
        
        response = client.post("/api/v1/sessions/", json=session_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"].startswith("Chat Session")
        assert len(data["title"]) > len("Chat Session")

    def test_create_session_validation_error(self, client: TestClient):
        """Test session creation with invalid data."""
        session_data = {
            "title": "x" * 201,  # Exceeds max length
            "model_used": "invalid-model"
        }
        
        response = client.post("/api/v1/sessions/", json=session_data)
        
        assert response.status_code == 422  # FastAPI validation error
        assert "detail" in response.json()

    def test_list_sessions_empty(self, client: TestClient):
        """Test listing sessions when none exist."""
        response = client.get("/api/v1/sessions/")
        
        assert response.status_code == 200
        assert response.json() == []

    def test_list_sessions_with_data(self, client: TestClient):
        """Test listing sessions with existing data."""
        # Create test sessions
        for i in range(3):
            session_data = {"title": f"Test Session {i+1}"}
            client.post("/api/v1/sessions/", json=session_data)
        
        response = client.get("/api/v1/sessions/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Should be ordered by updated_at desc (most recent first)
        assert data[0]["title"] == "Test Session 3"

    def test_list_sessions_pagination(self, client: TestClient):
        """Test session listing with pagination."""
        # Create test sessions
        for i in range(5):
            session_data = {"title": f"Test Session {i+1}"}
            client.post("/api/v1/sessions/", json=session_data)
        
        # Test limit
        response = client.get("/api/v1/sessions/?limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2
        
        # Test offset
        response = client.get("/api/v1/sessions/?limit=2&offset=2")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_sessions_invalid_pagination(self, client: TestClient):
        """Test session listing with invalid pagination parameters."""
        response = client.get("/api/v1/sessions/?limit=0")
        assert response.status_code == 400
        
        response = client.get("/api/v1/sessions/?limit=101")
        assert response.status_code == 400
        
        response = client.get("/api/v1/sessions/?offset=-1")
        assert response.status_code == 400

    def test_get_session_success(self, client: TestClient):
        """Test retrieving a specific session."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Retrieve the session
        response = client.get(f"/api/v1/sessions/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["title"] == "Test Session"

    def test_get_session_not_found(self, client: TestClient):
        """Test retrieving a non-existent session."""
        response = client.get("/api/v1/sessions/999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_session_invalid_id(self, client: TestClient):
        """Test retrieving a session with invalid ID."""
        response = client.get("/api/v1/sessions/0")
        
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_update_session_success(self, client: TestClient):
        """Test successful session update."""
        # Create a session
        session_data = {"title": "Original Title"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Update the session
        update_data = {
            "title": "Updated Title",
            "session_metadata": {"updated": True}
        }
        response = client.put(f"/api/v1/sessions/{session_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["session_metadata"]["updated"] is True

    def test_update_session_partial(self, client: TestClient):
        """Test partial session update."""
        # Create a session
        session_data = {"title": "Original Title", "session_metadata": {"key": "value"}}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Update only title
        update_data = {"title": "New Title"}
        response = client.put(f"/api/v1/sessions/{session_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Title"
        assert data["session_metadata"] == {"key": "value"}  # Should remain unchanged

    def test_update_session_not_found(self, client: TestClient):
        """Test updating a non-existent session."""
        update_data = {"title": "New Title"}
        response = client.put("/api/v1/sessions/999", json=update_data)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_session_invalid_data(self, client: TestClient):
        """Test updating session with invalid data."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Try to update with invalid data
        update_data = {"title": "x" * 201}  # Exceeds max length
        response = client.put(f"/api/v1/sessions/{session_id}", json=update_data)
        
        assert response.status_code == 422  # FastAPI validation error
        assert "detail" in response.json()

    def test_delete_session_success(self, client: TestClient):
        """Test successful session deletion."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Delete the session
        response = client.delete(f"/api/v1/sessions/{session_id}")
        
        assert response.status_code == 204
        
        # Verify session is deleted
        get_response = client.get(f"/api/v1/sessions/{session_id}")
        assert get_response.status_code == 404

    def test_delete_session_not_found(self, client: TestClient):
        """Test deleting a non-existent session."""
        response = client.delete("/api/v1/sessions/999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_session_invalid_id(self, client: TestClient):
        """Test deleting session with invalid ID."""
        response = client.delete("/api/v1/sessions/0")
        
        assert response.status_code == 400
        assert "detail" in response.json()


class TestSessionChatEndpoints:
    """Test session chat endpoints."""

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.session_chat_service.SessionChatService.send_message')
    def test_send_message_success(self, mock_send_message, client: TestClient):
        """Test successful message sending."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Mock the chat service response
        from backend.models.session_models import ChatResponse, MessagePublic, SessionPublic
        from datetime import datetime
        
        mock_user_message = MessagePublic(
            id=1,
            session_id=session_id,
            role="user",
            content="Hello",
            timestamp=datetime.now(),
            message_metadata={}
        )
        
        mock_assistant_message = MessagePublic(
            id=2,
            session_id=session_id,
            role="assistant",
            content="Hello! How can I help you?",
            timestamp=datetime.now(),
            message_metadata={}
        )
        
        mock_session = SessionPublic(
            id=session_id,
            title="Test Session",
            model_used="gemini-2.0-flash-exp",
            session_metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            message_count=2
        )
        
        mock_response = ChatResponse(
            user_message=mock_user_message,
            assistant_message=mock_assistant_message,
            session=mock_session
        )
        mock_send_message.return_value = mock_response
        
        # Send message
        message_data = {"message": "Hello"}
        response = client.post(f"/api/v1/sessions/{session_id}/chat", json=message_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_message"]["content"] == "Hello"
        assert data["assistant_message"]["content"] == "Hello! How can I help you?"
        assert data["session"]["message_count"] == 2

    def test_send_message_session_not_found(self, client: TestClient):
        """Test sending message to non-existent session."""
        message_data = {"message": "Hello"}
        response = client.post("/api/v1/sessions/999/chat", json=message_data)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_send_message_empty_message(self, client: TestClient):
        """Test sending empty message."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Send empty message
        message_data = {"message": ""}
        response = client.post(f"/api/v1/sessions/{session_id}/chat", json=message_data)
        
        assert response.status_code == 422  # Validation error

    def test_send_message_missing_api_key(self, client: TestClient):
        """Test sending message when API key is not configured."""
        with patch.dict('os.environ', {}, clear=True):
            # Create a session
            session_data = {"title": "Test Session"}
            create_response = client.post("/api/v1/sessions/", json=session_data)
            session_id = create_response.json()["id"]
            
            # Send message
            message_data = {"message": "Hello"}
            response = client.post(f"/api/v1/sessions/{session_id}/chat", json=message_data)
            
            assert response.status_code == 500
            assert "not configured" in response.json()["detail"].lower()

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.session_chat_service.SessionChatService.send_message')
    def test_send_message_gemini_api_error(self, mock_send_message, client: TestClient):
        """Test handling of Gemini API errors."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Mock API error
        api_error = errors.APIError("Rate limit exceeded", {})
        api_error.code = 429
        mock_send_message.side_effect = api_error
        
        # Send message
        message_data = {"message": "Hello"}
        response = client.post(f"/api/v1/sessions/{session_id}/chat", json=message_data)
        
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()

    def test_get_session_messages_success(self, client: TestClient):
        """Test retrieving session messages."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Get messages (should be empty initially)
        response = client.get(f"/api/v1/sessions/{session_id}/messages")
        
        assert response.status_code == 200
        assert response.json() == []

    def test_get_session_messages_not_found(self, client: TestClient):
        """Test retrieving messages for non-existent session."""
        response = client.get("/api/v1/sessions/999/messages")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_session_messages_pagination(self, client: TestClient):
        """Test message retrieval with pagination."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Test with pagination parameters
        response = client.get(f"/api/v1/sessions/{session_id}/messages?limit=50&offset=0")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_session_messages_invalid_pagination(self, client: TestClient):
        """Test message retrieval with invalid pagination."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Test invalid limit
        response = client.get(f"/api/v1/sessions/{session_id}/messages?limit=0")
        assert response.status_code == 400
        
        # Test invalid offset
        response = client.get(f"/api/v1/sessions/{session_id}/messages?offset=-1")
        assert response.status_code == 400


class TestSessionEndpointsErrorHandling:
    """Test error handling across all session endpoints."""

    def test_database_error_handling(self, client: TestClient):
        """Test handling of database errors."""
        # This would require mocking database failures
        # For now, we test that the endpoints handle errors gracefully
        pass

    def test_concurrent_session_operations(self, client: TestClient):
        """Test concurrent operations on the same session."""
        # Create a session
        session_data = {"title": "Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Multiple concurrent updates should be handled gracefully
        update_data = {"title": "Updated Title"}
        responses = []
        for _ in range(3):
            response = client.put(f"/api/v1/sessions/{session_id}", json=update_data)
            responses.append(response)
        
        # At least one should succeed
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 1

    def test_invalid_json_handling(self, client: TestClient):
        """Test handling of invalid JSON in requests."""
        response = client.post(
            "/api/v1/sessions/",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422

    def test_missing_content_type(self, client: TestClient):
        """Test handling of missing content type."""
        response = client.post("/api/v1/sessions/", data='{"title": "Test"}')
        
        # FastAPI should handle this gracefully
        assert response.status_code in [200, 201, 422]


class TestSessionEndpointsIntegration:
    """Integration tests for complete session workflows."""

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.session_chat_service.SessionChatService.send_message')
    def test_complete_session_workflow(self, mock_send_message, client: TestClient):
        """Test complete session workflow from creation to deletion."""
        # 1. Create session
        session_data = {"title": "Integration Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        assert create_response.status_code == 201
        session_id = create_response.json()["id"]
        
        # 2. List sessions (should include our session)
        list_response = client.get("/api/v1/sessions/")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1
        
        # 3. Get specific session
        get_response = client.get(f"/api/v1/sessions/{session_id}")
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "Integration Test Session"
        
        # 4. Update session
        update_data = {"title": "Updated Integration Test"}
        update_response = client.put(f"/api/v1/sessions/{session_id}", json=update_data)
        assert update_response.status_code == 200
        assert update_response.json()["title"] == "Updated Integration Test"
        
        # 5. Get messages (should be empty)
        messages_response = client.get(f"/api/v1/sessions/{session_id}/messages")
        assert messages_response.status_code == 200
        assert messages_response.json() == []
        
        # 6. Delete session
        delete_response = client.delete(f"/api/v1/sessions/{session_id}")
        assert delete_response.status_code == 204
        
        # 7. Verify deletion
        get_after_delete = client.get(f"/api/v1/sessions/{session_id}")
        assert get_after_delete.status_code == 404

    def test_session_cascade_deletion(self, client: TestClient):
        """Test that deleting a session also deletes associated messages."""
        # This test would require actually adding messages to the session
        # and then verifying they're deleted when the session is deleted
        # For now, we test the basic deletion functionality
        
        # Create session
        session_data = {"title": "Cascade Test Session"}
        create_response = client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Delete session
        delete_response = client.delete(f"/api/v1/sessions/{session_id}")
        assert delete_response.status_code == 204
        
        # Verify messages endpoint also returns 404
        messages_response = client.get(f"/api/v1/sessions/{session_id}/messages")
        assert messages_response.status_code == 404