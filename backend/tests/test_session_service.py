"""
Unit tests for SessionService class.

Tests all CRUD operations for sessions, message management within sessions,
and error handling for invalid session operations.
"""

import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel

from backend.services.session_service import SessionService
from backend.models.session_models import (
    Session as SessionModel,
    Message as MessageModel,
    SessionCreate,
    SessionUpdate,
    SessionPublic,
    MessageCreate,
    MessagePublic
)


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_service(test_session):
    """Create a SessionService instance for testing."""
    return SessionService(test_session)


class TestSessionServiceCRUD:
    """Test CRUD operations for sessions."""
    
    @pytest.mark.asyncio
    async def test_create_session_with_title(self, session_service):
        """Test creating a session with a provided title."""
        session_data = SessionCreate(title="Test Session")
        result = await session_service.create_session(session_data)
        
        assert isinstance(result, SessionPublic)
        assert result.title == "Test Session"
        assert result.model_used == "gemini-2.0-flash-exp"
        assert result.message_count == 0
        assert result.id is not None
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.updated_at, datetime)
    
    @pytest.mark.asyncio
    async def test_create_session_without_title(self, session_service):
        """Test creating a session without title generates default title."""
        session_data = SessionCreate(title="")
        result = await session_service.create_session(session_data)
        
        assert isinstance(result, SessionPublic)
        assert result.title.startswith("Chat Session")
        assert result.model_used == "gemini-2.0-flash-exp"
        assert result.message_count == 0
    
    @pytest.mark.asyncio
    async def test_create_session_with_custom_model(self, session_service):
        """Test creating a session with custom model."""
        session_data = SessionCreate(
            title="Custom Model Session",
            model_used="gemini-1.5-pro"
        )
        result = await session_service.create_session(session_data)
        
        assert result.title == "Custom Model Session"
        assert result.model_used == "gemini-1.5-pro"
    
    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self, session_service):
        """Test creating a session with custom metadata."""
        metadata = {"topic": "testing", "priority": "high"}
        session_data = SessionCreate(
            title="Metadata Session",
            session_metadata=metadata
        )
        result = await session_service.create_session(session_data)
        
        assert result.title == "Metadata Session"
        assert result.session_metadata == metadata
    
    @pytest.mark.asyncio
    async def test_get_session_existing(self, session_service):
        """Test retrieving an existing session."""
        # Create a session first
        session_data = SessionCreate(title="Get Test Session")
        created = await session_service.create_session(session_data)
        
        # Retrieve the session
        result = await session_service.get_session(created.id)
        
        assert result is not None
        assert result.id == created.id
        assert result.title == "Get Test Session"
    
    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self, session_service):
        """Test retrieving a non-existent session returns None."""
        result = await session_service.get_session(999)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_session_invalid_id(self, session_service):
        """Test retrieving session with invalid ID raises ValueError."""
        with pytest.raises(ValueError, match="Session ID must be a positive integer"):
            await session_service.get_session(0)
        
        with pytest.raises(ValueError, match="Session ID must be a positive integer"):
            await session_service.get_session(-1)
    
    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, session_service):
        """Test listing sessions when none exist."""
        result = await session_service.list_sessions()
        assert result == []
    
    @pytest.mark.asyncio
    async def test_list_sessions_with_data(self, session_service):
        """Test listing sessions with proper ordering."""
        # Create multiple sessions
        session1 = await session_service.create_session(SessionCreate(title="Session 1"))
        session2 = await session_service.create_session(SessionCreate(title="Session 2"))
        session3 = await session_service.create_session(SessionCreate(title="Session 3"))
        
        # List sessions
        result = await session_service.list_sessions()
        
        assert len(result) == 3
        # Should be ordered by updated_at desc (newest first)
        assert result[0].id == session3.id
        assert result[1].id == session2.id
        assert result[2].id == session1.id
    
    @pytest.mark.asyncio
    async def test_list_sessions_with_pagination(self, session_service):
        """Test listing sessions with limit and offset."""
        # Create multiple sessions
        for i in range(5):
            await session_service.create_session(SessionCreate(title=f"Session {i}"))
        
        # Test limit
        result = await session_service.list_sessions(limit=3)
        assert len(result) == 3
        
        # Test offset
        result = await session_service.list_sessions(limit=2, offset=2)
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_list_sessions_invalid_parameters(self, session_service):
        """Test listing sessions with invalid parameters."""
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            await session_service.list_sessions(limit=0)
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            await session_service.list_sessions(limit=101)
        
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            await session_service.list_sessions(offset=-1)
    
    @pytest.mark.asyncio
    async def test_update_session_title(self, session_service):
        """Test updating session title."""
        # Create a session
        session_data = SessionCreate(title="Original Title")
        created = await session_service.create_session(session_data)
        
        # Update title
        updates = SessionUpdate(title="Updated Title")
        result = await session_service.update_session(created.id, updates)
        
        assert result is not None
        assert result.title == "Updated Title"
        assert result.id == created.id
        # updated_at should be newer
        assert result.updated_at > created.updated_at
    
    @pytest.mark.asyncio
    async def test_update_session_metadata(self, session_service):
        """Test updating session metadata."""
        # Create a session
        session_data = SessionCreate(title="Metadata Test")
        created = await session_service.create_session(session_data)
        
        # Update metadata
        new_metadata = {"updated": True, "version": 2}
        updates = SessionUpdate(session_metadata=new_metadata)
        result = await session_service.update_session(created.id, updates)
        
        assert result is not None
        assert result.session_metadata == new_metadata
        assert result.title == "Metadata Test"  # Title unchanged
    
    @pytest.mark.asyncio
    async def test_update_session_nonexistent(self, session_service):
        """Test updating a non-existent session returns None."""
        updates = SessionUpdate(title="New Title")
        result = await session_service.update_session(999, updates)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_session_invalid_id(self, session_service):
        """Test updating session with invalid ID raises ValueError."""
        updates = SessionUpdate(title="New Title")
        
        with pytest.raises(ValueError, match="Session ID must be a positive integer"):
            await session_service.update_session(0, updates)
    
    @pytest.mark.asyncio
    async def test_update_session_no_changes(self, session_service):
        """Test updating session with no changes returns current session."""
        # Create a session
        session_data = SessionCreate(title="No Changes Test")
        created = await session_service.create_session(session_data)
        
        # Update with no changes
        updates = SessionUpdate()
        result = await session_service.update_session(created.id, updates)
        
        assert result is not None
        assert result.title == "No Changes Test"
        assert result.id == created.id
    
    @pytest.mark.asyncio
    async def test_delete_session_existing(self, session_service):
        """Test deleting an existing session."""
        # Create a session
        session_data = SessionCreate(title="Delete Test")
        created = await session_service.create_session(session_data)
        
        # Delete the session
        result = await session_service.delete_session(created.id)
        assert result is True
        
        # Verify session is deleted
        retrieved = await session_service.get_session(created.id)
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_delete_session_nonexistent(self, session_service):
        """Test deleting a non-existent session returns False."""
        result = await session_service.delete_session(999)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_session_invalid_id(self, session_service):
        """Test deleting session with invalid ID raises ValueError."""
        with pytest.raises(ValueError, match="Session ID must be a positive integer"):
            await session_service.delete_session(0)


class TestSessionServiceMessages:
    """Test message management within sessions."""
    
    @pytest.mark.asyncio
    async def test_add_message_to_session(self, session_service):
        """Test adding a message to an existing session."""
        # Create a session
        session_data = SessionCreate(title="Message Test Session")
        session = await session_service.create_session(session_data)
        
        # Add a message
        message_data = MessageCreate(
            session_id=session.id,
            role="user",
            content="Hello, this is a test message"
        )
        result = await session_service.add_message(message_data)
        
        assert isinstance(result, MessagePublic)
        assert result.session_id == session.id
        assert result.role == "user"
        assert result.content == "Hello, this is a test message"
        assert result.id is not None
        assert isinstance(result.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_add_message_updates_session_count(self, session_service):
        """Test that adding messages updates session message count."""
        # Create a session
        session_data = SessionCreate(title="Count Test Session")
        session = await session_service.create_session(session_data)
        assert session.message_count == 0
        
        # Add first message
        message1 = MessageCreate(
            session_id=session.id,
            role="user",
            content="First message"
        )
        await session_service.add_message(message1)
        
        # Check updated session
        updated_session = await session_service.get_session(session.id)
        assert updated_session.message_count == 1
        
        # Add second message
        message2 = MessageCreate(
            session_id=session.id,
            role="assistant",
            content="Second message"
        )
        await session_service.add_message(message2)
        
        # Check updated session again
        updated_session = await session_service.get_session(session.id)
        assert updated_session.message_count == 2
    
    @pytest.mark.asyncio
    async def test_add_message_to_nonexistent_session(self, session_service):
        """Test adding message to non-existent session raises ValueError."""
        message_data = MessageCreate(
            session_id=999,
            role="user",
            content="This should fail"
        )
        
        with pytest.raises(ValueError, match="Session 999 not found"):
            await session_service.add_message(message_data)
    
    @pytest.mark.asyncio
    async def test_get_session_messages_empty(self, session_service):
        """Test getting messages from session with no messages."""
        # Create a session
        session_data = SessionCreate(title="Empty Messages Test")
        session = await session_service.create_session(session_data)
        
        # Get messages
        result = await session_service.get_session_messages(session.id)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_session_messages_with_data(self, session_service):
        """Test getting messages from session with proper ordering."""
        # Create a session
        session_data = SessionCreate(title="Messages Test")
        session = await session_service.create_session(session_data)
        
        # Add messages
        message1 = MessageCreate(
            session_id=session.id,
            role="user",
            content="First message"
        )
        msg1_result = await session_service.add_message(message1)
        
        message2 = MessageCreate(
            session_id=session.id,
            role="assistant",
            content="Second message"
        )
        msg2_result = await session_service.add_message(message2)
        
        # Get messages
        result = await session_service.get_session_messages(session.id)
        
        assert len(result) == 2
        # Should be ordered by timestamp asc (oldest first)
        assert result[0].id == msg1_result.id
        assert result[0].content == "First message"
        assert result[1].id == msg2_result.id
        assert result[1].content == "Second message"
    
    @pytest.mark.asyncio
    async def test_get_session_messages_with_pagination(self, session_service):
        """Test getting messages with limit and offset."""
        # Create a session
        session_data = SessionCreate(title="Pagination Test")
        session = await session_service.create_session(session_data)
        
        # Add multiple messages
        for i in range(5):
            message = MessageCreate(
                session_id=session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}"
            )
            await session_service.add_message(message)
        
        # Test limit
        result = await session_service.get_session_messages(session.id, limit=3)
        assert len(result) == 3
        
        # Test offset
        result = await session_service.get_session_messages(session.id, limit=2, offset=2)
        assert len(result) == 2
        assert result[0].content == "Message 2"
    
    @pytest.mark.asyncio
    async def test_get_session_messages_nonexistent_session(self, session_service):
        """Test getting messages from non-existent session raises ValueError."""
        with pytest.raises(ValueError, match="Session 999 not found"):
            await session_service.get_session_messages(999)
    
    @pytest.mark.asyncio
    async def test_get_session_messages_invalid_parameters(self, session_service):
        """Test getting messages with invalid parameters."""
        # Create a session
        session_data = SessionCreate(title="Invalid Params Test")
        session = await session_service.create_session(session_data)
        
        with pytest.raises(ValueError, match="Session ID must be a positive integer"):
            await session_service.get_session_messages(0)
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 1000"):
            await session_service.get_session_messages(session.id, limit=0)
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 1000"):
            await session_service.get_session_messages(session.id, limit=1001)
        
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            await session_service.get_session_messages(session.id, offset=-1)
    
    @pytest.mark.asyncio
    async def test_get_message_count(self, session_service):
        """Test getting message count for a session."""
        # Create a session
        session_data = SessionCreate(title="Count Test")
        session = await session_service.create_session(session_data)
        
        # Initially no messages
        count = await session_service.get_message_count(session.id)
        assert count == 0
        
        # Add messages
        for i in range(3):
            message = MessageCreate(
                session_id=session.id,
                role="user",
                content=f"Message {i}"
            )
            await session_service.add_message(message)
        
        # Check count
        count = await session_service.get_message_count(session.id)
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_get_message_count_invalid_id(self, session_service):
        """Test getting message count with invalid session ID."""
        with pytest.raises(ValueError, match="Session ID must be a positive integer"):
            await session_service.get_message_count(0)


class TestSessionServiceCascadeDelete:
    """Test cascade deletion of messages when session is deleted."""
    
    @pytest.mark.asyncio
    async def test_delete_session_cascades_to_messages(self, session_service):
        """Test that deleting a session also deletes its messages."""
        # Create a session
        session_data = SessionCreate(title="Cascade Test")
        session = await session_service.create_session(session_data)
        
        # Add messages
        for i in range(3):
            message = MessageCreate(
                session_id=session.id,
                role="user",
                content=f"Message {i}"
            )
            await session_service.add_message(message)
        
        # Verify messages exist
        messages = await session_service.get_session_messages(session.id)
        assert len(messages) == 3
        
        # Delete session
        result = await session_service.delete_session(session.id)
        assert result is True
        
        # Verify session is deleted
        deleted_session = await session_service.get_session(session.id)
        assert deleted_session is None
        
        # Verify messages are also deleted (this would raise an error since session doesn't exist)
        with pytest.raises(ValueError, match=f"Session {session.id} not found"):
            await session_service.get_session_messages(session.id)


class TestSessionServiceErrorHandling:
    """Test error handling for various edge cases."""
    
    @pytest.mark.asyncio
    async def test_add_message_with_metadata(self, session_service):
        """Test adding message with custom metadata."""
        # Create a session
        session_data = SessionCreate(title="Metadata Message Test")
        session = await session_service.create_session(session_data)
        
        # Add message with metadata
        metadata = {"source": "test", "priority": "high"}
        message_data = MessageCreate(
            session_id=session.id,
            role="user",
            content="Message with metadata",
            message_metadata=metadata
        )
        result = await session_service.add_message(message_data)
        
        assert result.message_metadata == metadata
    
    @pytest.mark.asyncio
    async def test_session_title_generation(self, session_service):
        """Test automatic session title generation."""
        # Create session with empty title
        session_data = SessionCreate(title="")
        result = await session_service.create_session(session_data)
        
        assert result.title.startswith("Chat Session")
        assert len(result.title) > len("Chat Session")
        
        # Create session with whitespace-only title
        session_data = SessionCreate(title="   ")
        result = await session_service.create_session(session_data)
        
        assert result.title.startswith("Chat Session")
    
    @pytest.mark.asyncio
    async def test_message_content_trimming(self, session_service):
        """Test that message content is trimmed of whitespace."""
        # Create a session
        session_data = SessionCreate(title="Trim Test")
        session = await session_service.create_session(session_data)
        
        # Add message with extra whitespace
        message_data = MessageCreate(
            session_id=session.id,
            role="user",
            content="  Message with whitespace  "
        )
        result = await session_service.add_message(message_data)
        
        assert result.content == "Message with whitespace"