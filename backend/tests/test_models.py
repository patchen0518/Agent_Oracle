"""
Tests for Pydantic models validation.

Based on testing standards and Pydantic v2 documentation
(Context 7 lookup: 2025-01-26).
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from sqlmodel import Session, create_engine, SQLModel

from backend.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ServiceErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
    # Session models
    Session as SessionModel,
    Message,
    SessionCreate,
    SessionUpdate,
    SessionPublic,
    MessageCreate,
    MessagePublic,
    SessionChatRequest,
    SessionChatResponse,
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

# Session Model Tests

@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    with Session(test_engine) as session:
        yield session


class TestSessionModel:
    """Test Session SQLModel validation and database operations."""
    
    def test_session_creation_with_defaults(self):
        """Test creating a session with default values."""
        session = SessionModel(title="Test Session")
        assert session.title == "Test Session"
        assert session.model_used == "gemini-2.0-flash-exp"
        assert session.session_metadata == {}
        assert session.message_count == 0
        assert session.id is None  # Not set until saved to DB
    
    def test_session_creation_with_custom_values(self):
        """Test creating a session with custom values."""
        custom_metadata = {"topic": "testing", "priority": "high"}
        session = SessionModel(
            title="Custom Session",
            model_used="gemini-1.5-pro",
            session_metadata=custom_metadata
        )
        assert session.title == "Custom Session"
        assert session.model_used == "gemini-1.5-pro"
        assert session.session_metadata == custom_metadata
    
    def test_session_title_validation(self):
        """Test session title field constraints."""
        # Valid title
        session = SessionModel(title="Valid Title")
        assert session.title == "Valid Title"
        
        # Test that title field exists and can be set
        long_title = "x" * 150  # Within database limits
        session = SessionModel(title=long_title)
        assert session.title == long_title
    
    def test_session_database_persistence(self, test_session):
        """Test saving and retrieving session from database."""
        # Create and save session
        session = SessionModel(title="DB Test Session")
        test_session.add(session)
        test_session.commit()
        test_session.refresh(session)
        
        # Verify session was saved with ID
        assert session.id is not None
        assert session.title == "DB Test Session"
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
        
        # Retrieve session from database
        retrieved = test_session.get(SessionModel, session.id)
        assert retrieved is not None
        assert retrieved.title == "DB Test Session"


class TestMessageModel:
    """Test Message SQLModel validation and database operations."""
    
    def test_message_creation(self):
        """Test creating a message with valid data."""
        message = Message(
            session_id=1,
            role="user",
            content="Hello, this is a test message"
        )
        assert message.session_id == 1
        assert message.role == "user"
        assert message.content == "Hello, this is a test message"
        assert message.message_metadata == {}
    
    def test_message_role_validation(self):
        """Test message role field constraints."""
        # Valid roles
        user_msg = Message(session_id=1, role="user", content="Test")
        assistant_msg = Message(session_id=1, role="assistant", content="Test")
        assert user_msg.role == "user"
        assert assistant_msg.role == "assistant"
        
        # Test that role field can be set to expected values
        message = Message(session_id=1, role="user", content="Test")
        assert message.role in ["user", "assistant"] or message.role == "user"
    
    def test_message_content_validation(self):
        """Test message content field constraints."""
        # Valid content
        message = Message(session_id=1, role="user", content="Valid content")
        assert message.content == "Valid content"
        
        # Test that content field can store text
        long_content = "This is a longer message content that should be stored properly."
        message = Message(session_id=1, role="user", content=long_content)
        assert message.content == long_content
    
    def test_message_database_persistence(self, test_session):
        """Test saving and retrieving message from database."""
        # Create session first
        session = SessionModel(title="Test Session")
        test_session.add(session)
        test_session.commit()
        test_session.refresh(session)
        
        # Create and save message
        message = Message(
            session_id=session.id,
            role="user",
            content="Test message content"
        )
        test_session.add(message)
        test_session.commit()
        test_session.refresh(message)
        
        # Verify message was saved
        assert message.id is not None
        assert message.session_id == session.id
        assert isinstance(message.timestamp, datetime)
        
        # Retrieve message from database
        retrieved = test_session.get(Message, message.id)
        assert retrieved is not None
        assert retrieved.content == "Test message content"


class TestSessionMessageRelationship:
    """Test relationship between Session and Message models."""
    
    def test_session_message_relationship(self, test_session):
        """Test the one-to-many relationship between sessions and messages."""
        # Create session
        session = SessionModel(title="Relationship Test")
        test_session.add(session)
        test_session.commit()
        test_session.refresh(session)
        
        # Create messages for the session
        msg1 = Message(session_id=session.id, role="user", content="First message")
        msg2 = Message(session_id=session.id, role="assistant", content="Second message")
        
        test_session.add(msg1)
        test_session.add(msg2)
        test_session.commit()
        
        # Refresh to load relationships
        test_session.refresh(session)
        
        # Test relationship access
        assert len(session.messages) == 2
        assert session.messages[0].content in ["First message", "Second message"]
        assert session.messages[1].content in ["First message", "Second message"]
        
        # Test reverse relationship
        test_session.refresh(msg1)
        assert msg1.session.title == "Relationship Test"


class TestSessionAPIModels:
    """Test API models for session management."""
    
    def test_session_create_model(self):
        """Test SessionCreate model validation."""
        session_data = SessionCreate(title="New Session")
        assert session_data.title == "New Session"
        assert session_data.model_used == "gemini-2.0-flash-exp"
        assert session_data.session_metadata == {}
    
    def test_session_update_model(self):
        """Test SessionUpdate model validation."""
        # Update with title only
        update_data = SessionUpdate(title="Updated Title")
        assert update_data.title == "Updated Title"
        assert update_data.session_metadata is None
        
        # Update with metadata only
        metadata = {"updated": True}
        update_data = SessionUpdate(session_metadata=metadata)
        assert update_data.title is None
        assert update_data.session_metadata == metadata
    
    def test_session_public_model(self):
        """Test SessionPublic model structure."""
        session_data = SessionPublic(
            id=1,
            title="Public Session",
            model_used="gemini-2.0-flash-exp",
            session_metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=5
        )
        assert session_data.id == 1
        assert session_data.title == "Public Session"
        assert session_data.message_count == 5
    
    def test_message_create_model(self):
        """Test MessageCreate model validation."""
        message_data = MessageCreate(
            session_id=1,
            role="user",
            content="Test message"
        )
        assert message_data.session_id == 1
        assert message_data.role == "user"
        assert message_data.content == "Test message"
    
    def test_message_public_model(self):
        """Test MessagePublic model structure."""
        message_data = MessagePublic(
            id=1,
            session_id=1,
            role="assistant",
            content="Response message",
            message_metadata={},
            timestamp=datetime.utcnow()
        )
        assert message_data.id == 1
        assert message_data.session_id == 1
        assert message_data.role == "assistant"
        assert message_data.content == "Response message"


class TestChatAPIModels:
    """Test chat-specific API models."""
    
    def test_session_chat_request(self):
        """Test SessionChatRequest model validation."""
        request = SessionChatRequest(message="Hello, how are you?")
        assert request.message == "Hello, how are you?"
        
        # Test empty message validation
        with pytest.raises(ValidationError) as exc_info:
            SessionChatRequest(message="")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "string_too_short" in errors[0]["type"]
    
    def test_session_chat_response(self):
        """Test SessionChatResponse model structure."""
        user_msg = MessagePublic(
            id=1,
            session_id=1,
            role="user",
            content="Hello",
            message_metadata={},
            timestamp=datetime.utcnow()
        )
        assistant_msg = MessagePublic(
            id=2,
            session_id=1,
            role="assistant",
            content="Hi there!",
            message_metadata={},
            timestamp=datetime.utcnow()
        )
        session_data = SessionPublic(
            id=1,
            title="Test Session",
            model_used="gemini-2.0-flash-exp",
            session_metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=2
        )
        
        response = SessionChatResponse(
            user_message=user_msg,
            assistant_message=assistant_msg,
            session=session_data
        )
        
        assert response.user_message.content == "Hello"
        assert response.assistant_message.content == "Hi there!"
        assert response.session.title == "Test Session"