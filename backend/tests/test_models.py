"""
Tests for Pydantic models validation.

Based on testing standards and Pydantic v2 documentation
(Context 7 lookup: 2025-01-26).
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ServiceErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)


class TestChatMessage:
    """Test ChatMessage model validation."""
    
    def test_valid_user_message(self):
        """Test creating a valid user message."""
        message = ChatMessage(role="user", parts="Hello, how are you?")
        assert message.role == "user"
        assert message.parts == "Hello, how are you?"
    
    def test_valid_model_message(self):
        """Test creating a valid model message."""
        message = ChatMessage(role="model", parts="I'm doing well, thank you!")
        assert message.role == "model"
        assert message.parts == "I'm doing well, thank you!"
    
    def test_invalid_role(self):
        """Test that invalid roles are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessage(role="invalid", parts="Hello")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "literal_error" in errors[0]["type"]
    
    def test_empty_parts(self):
        """Test that empty message parts are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessage(role="user", parts="")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "string_too_short" in errors[0]["type"]


class TestChatRequest:
    """Test ChatRequest model validation."""
    
    def test_valid_request_without_history(self):
        """Test creating a valid request without history."""
        request = ChatRequest(message="Hello")
        assert request.message == "Hello"
        assert request.history == []
    
    def test_valid_request_with_history(self):
        """Test creating a valid request with conversation history."""
        history = [
            ChatMessage(role="user", parts="Hi"),
            ChatMessage(role="model", parts="Hello!")
        ]
        request = ChatRequest(message="How are you?", history=history)
        assert request.message == "How are you?"
        assert len(request.history) == 2
        assert request.history[0].role == "user"
        assert request.history[1].role == "model"
    
    def test_empty_message(self):
        """Test that empty messages are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "string_too_short" in errors[0]["type"]
    
    def test_message_too_long(self):
        """Test that overly long messages are rejected."""
        long_message = "x" * 4001  # Exceeds max_length of 4000
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message=long_message)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "string_too_long" in errors[0]["type"]


class TestChatResponse:
    """Test ChatResponse model validation."""
    
    def test_valid_response(self):
        """Test creating a valid response."""
        response = ChatResponse(response="This is my response")
        assert response.response == "This is my response"
        assert isinstance(response.timestamp, datetime)
    
    def test_response_with_custom_timestamp(self):
        """Test creating a response with custom timestamp."""
        custom_time = datetime(2025, 1, 26, 12, 0, 0)
        response = ChatResponse(response="Hello", timestamp=custom_time)
        assert response.response == "Hello"
        assert response.timestamp == custom_time


class TestErrorModels:
    """Test error response models."""
    
    def test_error_response(self):
        """Test basic error response."""
        error = ErrorResponse(detail="Something went wrong")
        assert error.detail == "Something went wrong"
        assert error.error_code is None
    
    def test_error_response_with_code(self):
        """Test error response with error code."""
        error = ErrorResponse(
            detail="Invalid input", 
            error_code="INVALID_INPUT"
        )
        assert error.detail == "Invalid input"
        assert error.error_code == "INVALID_INPUT"
    
    def test_service_error_response(self):
        """Test service error response."""
        error = ServiceErrorResponse(
            detail="Gemini API unavailable",
            service="gemini",
            error_code="SERVICE_UNAVAILABLE",
            retry_after=30
        )
        assert error.detail == "Gemini API unavailable"
        assert error.service == "gemini"
        assert error.error_code == "SERVICE_UNAVAILABLE"
        assert error.retry_after == 30
    
    def test_validation_error_detail(self):
        """Test validation error detail structure."""
        detail = ValidationErrorDetail(
            loc=["body", "message"],
            msg="field required",
            type="value_error.missing",
            input=None
        )
        assert detail.loc == ["body", "message"]
        assert detail.msg == "field required"
        assert detail.type == "value_error.missing"
        assert detail.input is None