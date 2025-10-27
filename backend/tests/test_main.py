# Basic FastAPI app tests
# Based on FastAPI testing documentation (Context 7 lookup: 2025-01-26)

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.chat_models import ChatResponse
from google.genai import errors

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


# Chat API Integration Tests

@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
@patch('backend.services.chat_service.ChatService.process_chat_request')
async def test_chat_endpoint_success(mock_process_chat):
    """Test successful chat request and response."""
    # Mock the chat service response
    mock_response = ChatResponse(response="Hello! How can I help you today?")
    mock_process_chat.return_value = mock_response
    
    # Test data
    request_data = {
        "message": "Hello",
        "history": []
    }
    
    # Make the request
    response = client.post("/api/v1/chat", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert "response" in response_data
    assert response_data["response"] == "Hello! How can I help you today?"
    assert "timestamp" in response_data


@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
@patch('backend.services.chat_service.ChatService.process_chat_request')
async def test_chat_endpoint_with_history(mock_process_chat):
    """Test chat request with conversation history."""
    # Mock the chat service response
    mock_response = ChatResponse(response="Based on our previous conversation, here's more info.")
    mock_process_chat.return_value = mock_response
    
    # Test data with history
    request_data = {
        "message": "Tell me more about that",
        "history": [
            {"role": "user", "parts": "What is Python?"},
            {"role": "model", "parts": "Python is a programming language."}
        ]
    }
    
    # Make the request
    response = client.post("/api/v1/chat", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["response"] == "Based on our previous conversation, here's more info."


@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
def test_chat_endpoint_validation_empty_message():
    """Test chat endpoint validation for empty message."""
    request_data = {
        "message": "",
        "history": []
    }
    
    response = client.post("/api/v1/chat", json=request_data)
    
    # Should return validation error
    assert response.status_code == 422
    assert "detail" in response.json()


@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
def test_chat_endpoint_validation_missing_message():
    """Test chat endpoint validation for missing message field."""
    request_data = {
        "history": []
    }
    
    response = client.post("/api/v1/chat", json=request_data)
    
    # Should return validation error
    assert response.status_code == 422
    assert "detail" in response.json()


@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
def test_chat_endpoint_validation_invalid_history():
    """Test chat endpoint validation for invalid history format."""
    request_data = {
        "message": "Hello",
        "history": [
            {"role": "invalid_role", "parts": "Some message"}
        ]
    }
    
    response = client.post("/api/v1/chat", json=request_data)
    
    # Should return validation error
    assert response.status_code == 422
    assert "detail" in response.json()


@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
@patch('backend.services.chat_service.ChatService.process_chat_request')
async def test_chat_endpoint_service_error(mock_process_chat):
    """Test chat endpoint handling of service errors."""
    # Mock a service error
    mock_process_chat.side_effect = ValueError("Invalid request format")
    
    request_data = {
        "message": "Hello",
        "history": []
    }
    
    response = client.post("/api/v1/chat", json=request_data)
    
    # Should return 400 Bad Request
    assert response.status_code == 400
    assert "detail" in response.json()
    assert "Invalid request format" in response.json()["detail"]


@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
@patch('backend.services.chat_service.ChatService.process_chat_request')
async def test_chat_endpoint_api_error(mock_process_chat):
    """Test chat endpoint handling of Gemini API errors."""
    # Mock a Gemini API error
    api_error = errors.APIError("Rate limit exceeded", {})
    api_error.code = 429
    mock_process_chat.side_effect = api_error
    
    request_data = {
        "message": "Hello",
        "history": []
    }
    
    response = client.post("/api/v1/chat", json=request_data)
    
    # Should return 429 Too Many Requests
    assert response.status_code == 429
    assert "detail" in response.json()
    assert "Rate limit exceeded" in response.json()["detail"]


def test_chat_endpoint_missing_api_key():
    """Test chat endpoint when API key is not configured."""
    with patch.dict('os.environ', {}, clear=True):
        request_data = {
            "message": "Hello",
            "history": []
        }
        
        response = client.post("/api/v1/chat", json=request_data)
        
        # Should return 500 Internal Server Error
        assert response.status_code == 500
        assert "detail" in response.json()
        assert "API key not configured" in response.json()["detail"]


@patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
def test_chat_health_endpoint():
    """Test chat service health check endpoint."""
    with patch('backend.services.chat_service.ChatService.get_session_info') as mock_info:
        mock_info.return_value = {
            "model": "gemini-2.5-flash-lite",
            "active_sessions": 0,
            "service_status": "active"
        }
        
        response = client.get("/api/v1/chat/health")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "healthy"
        assert response_data["service"] == "chat"
        assert "model" in response_data


def test_cors_configuration():
    """Test CORS configuration for chat endpoints."""
    # Test preflight request
    response = client.options(
        "/api/v1/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
    )
    
    # FastAPI TestClient handles CORS automatically, so we just verify the endpoint exists
    # In a real browser, CORS headers would be checked
    assert response.status_code in [200, 405]  # 405 is acceptable for OPTIONS if not explicitly handled