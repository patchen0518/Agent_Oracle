"""
Unit tests for SessionChatService class.

Tests message sending and response handling within session context,
context optimization and token usage reduction, and integration
with session service and database operations.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel

from backend.services.session_chat_service import SessionChatService
from backend.services.session_service import SessionService
from backend.services.gemini_client import GeminiClient, ChatSession
from backend.models.session_models import (
    Session as SessionModel,
    Message as MessageModel,
    SessionCreate,
    MessageCreate,
    MessagePublic,
    SessionPublic,
    ChatResponse
)


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_db_session(test_engine):
    """Create a test database session."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def mock_gemini_client():
    """Create a mock Gemini client for testing."""
    client = Mock(spec=GeminiClient)
    return client


@pytest.fixture
def mock_chat_session():
    """Create a mock chat session for testing."""
    chat_session = Mock(spec=ChatSession)
    chat_session.send_message.return_value = "This is a mock AI response"
    return chat_session


@pytest.fixture
def session_chat_service(test_db_session, mock_gemini_client):
    """Create a SessionChatService instance for testing."""
    return SessionChatService(test_db_session, mock_gemini_client)


@pytest.fixture
async def test_session(test_db_session):
    """Create a test session in the database."""
    session_service = SessionService(test_db_session)
    session_data = SessionCreate(title="Test Chat Session")
    return await session_service.create_session(session_data)


class TestSessionChatServiceSendMessage:
    """Test message sending and response handling within session context."""
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, session_chat_service, test_session, mock_gemini_client, mock_chat_session):
        """Test successful message sending and AI response."""
        # Setup mock
        mock_gemini_client.create_chat_session.return_value = mock_chat_session
        mock_chat_session.send_message.return_value = "Hello! How can I help you today?"
        
        # Send message
        result = await session_chat_service.send_message(test_session.id, "Hello, AI!")
        
        # Verify result structure
        assert isinstance(result, ChatResponse)
        assert result.user_message.content == "Hello, AI!"
        assert result.user_message.role == "user"
        assert result.user_message.session_id == test_session.id
        assert result.assistant_message.content == "Hello! How can I help you today?"
        assert result.assistant_message.role == "assistant"
        assert result.assistant_message.session_id == test_session.id
        assert result.session.id == test_session.id
        
        # Verify Gemini client was called
        mock_gemini_client.create_chat_session.assert_called_once()
        mock_chat_session.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_nonexistent_session(self, session_chat_service):
        """Test sending message to non-existent session raises ValueError."""
        with pytest.raises(ValueError, match="Session 999 not found"):
            await session_chat_service.send_message(999, "Hello")
    
    @pytest.mark.asyncio
    async def test_send_message_empty_content(self, session_chat_service, test_session):
        """Test sending empty message raises ValueError."""
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            await session_chat_service.send_message(test_session.id, "")
        
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            await session_chat_service.send_message(test_session.id, "   ")
    
    @pytest.mark.asyncio
    async def test_send_message_with_context(self, session_chat_service, test_session, mock_gemini_client, mock_chat_session):
        """Test sending message with existing conversation context."""
        # Setup mock
        mock_gemini_client.create_chat_session.return_value = mock_chat_session
        mock_chat_session.send_message.return_value = "I understand your follow-up question."
        
        # Add some existing messages to the session
        session_service = SessionService(session_chat_service.db)
        await session_service.add_message(MessageCreate(
            session_id=test_session.id,
            role="user",
            content="What is Python?"
        ))
        await session_service.add_message(MessageCreate(
            session_id=test_session.id,
            role="assistant",
            content="Python is a programming language."
        ))
        
        # Send follow-up message
        result = await session_chat_service.send_message(test_session.id, "Can you tell me more?")
        
        # Verify context was included in the API call
        mock_chat_session.send_message.assert_called_once()
        call_args = mock_chat_session.send_message.call_args[0][0]
        assert "Previous conversation:" in call_args
        assert "What is Python?" in call_args
        assert "Python is a programming language." in call_args
        assert "Can you tell me more?" in call_args
    
    @pytest.mark.asyncio
    async def test_send_message_updates_session_metadata(self, session_chat_service, test_session, mock_gemini_client, mock_chat_session):
        """Test that sending message updates session metadata."""
        # Setup mock
        mock_gemini_client.create_chat_session.return_value = mock_chat_session
        mock_chat_session.send_message.return_value = "Response with metadata update"
        
        # Send message
        result = await session_chat_service.send_message(test_session.id, "Test message")
        
        # Verify session metadata was updated
        assert result.session.message_count == 2  # user + assistant message
        assert result.session.updated_at > test_session.updated_at
        
        # Check that session metadata contains tracking info
        session_service = SessionService(session_chat_service.db)
        updated_session = await session_service.get_session(test_session.id)
        assert "last_activity" in updated_session.session_metadata
        assert "total_messages" in updated_session.session_metadata
        assert updated_session.session_metadata["total_messages"] == 2


class TestSessionChatServiceContextOptimization:
    """Test context optimization and token usage reduction."""
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_empty_session(self, session_chat_service, test_session):
        """Test getting context from session with no messages."""
        context = await session_chat_service.get_conversation_context(test_session.id)
        assert context == []
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_with_messages(self, session_chat_service, test_session):
        """Test getting context from session with messages."""
        # Add messages to session
        session_service = SessionService(session_chat_service.db)
        msg1 = await session_service.add_message(MessageCreate(
            session_id=test_session.id,
            role="user",
            content="First message"
        ))
        msg2 = await session_service.add_message(MessageCreate(
            session_id=test_session.id,
            role="assistant",
            content="First response"
        ))
        
        # Get context
        context = await session_chat_service.get_conversation_context(test_session.id)
        
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "First message"
        assert context[1]["role"] == "assistant"
        assert context[1]["content"] == "First response"
        assert "timestamp" in context[0]
        assert "id" in context[0]
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_nonexistent_session(self, session_chat_service):
        """Test getting context from non-existent session raises error."""
        with pytest.raises(ValueError, match="Session 999 not found"):
            await session_chat_service.get_conversation_context(999)
    
    def test_optimize_context_empty_messages(self, session_chat_service):
        """Test context optimization with empty message list."""
        result = session_chat_service._optimize_context([])
        assert result == []
    
    def test_optimize_context_few_messages(self, session_chat_service):
        """Test context optimization with fewer messages than minimum."""
        messages = [
            {"id": 1, "role": "user", "content": "Hello", "timestamp": "2025-01-01T00:00:00"},
            {"id": 2, "role": "assistant", "content": "Hi", "timestamp": "2025-01-01T00:01:00"}
        ]
        
        result = session_chat_service._optimize_context(messages)
        assert result == messages
    
    def test_optimize_context_within_limit(self, session_chat_service):
        """Test context optimization with messages within limit."""
        messages = []
        for i in range(10):  # Less than max_context_messages (20)
            messages.append({
                "id": i + 1,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
                "timestamp": f"2025-01-01T00:{i:02d}:00"
            })
        
        result = session_chat_service._optimize_context(messages)
        assert result == messages
    
    def test_optimize_context_exceeds_limit(self, session_chat_service):
        """Test context optimization with messages exceeding limit."""
        messages = []
        for i in range(30):  # More than max_context_messages (20)
            messages.append({
                "id": i + 1,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
                "timestamp": f"2025-01-01T00:{i:02d}:00"
            })
        
        result = session_chat_service._optimize_context(messages)
        
        # Should return only the most recent messages
        assert len(result) == session_chat_service.max_context_messages
        assert result[0]["content"] == "Message 10"  # Most recent 20 messages
        assert result[-1]["content"] == "Message 29"
    
    def test_apply_recency_optimization(self, session_chat_service):
        """Test recency-based optimization."""
        messages = []
        for i in range(30):
            messages.append({
                "id": i + 1,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
                "timestamp": f"2025-01-01T00:{i:02d}:00"
            })
        
        result = session_chat_service._apply_recency_optimization(messages)
        
        assert len(result) == session_chat_service.max_context_messages
        assert result[0]["content"] == "Message 10"  # Last 20 messages
        assert result[-1]["content"] == "Message 29"
    
    def test_ensure_conversation_pairs_starts_with_assistant(self, session_chat_service):
        """Test ensuring conversation pairs when starting with assistant message."""
        all_messages = [
            {"id": 1, "role": "user", "content": "Question", "timestamp": "2025-01-01T00:00:00"},
            {"id": 2, "role": "assistant", "content": "Answer", "timestamp": "2025-01-01T00:01:00"},
            {"id": 3, "role": "user", "content": "Follow-up", "timestamp": "2025-01-01T00:02:00"}
        ]
        
        # Simulate optimization that starts with assistant message
        optimized = [all_messages[1], all_messages[2]]  # Starts with assistant
        
        result = session_chat_service._ensure_conversation_pairs(optimized, all_messages)
        
        # Should replace first message with preceding user message
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Question"
        assert result[1]["content"] == "Follow-up"
    
    def test_apply_content_filtering_short_messages(self, session_chat_service):
        """Test content filtering removes very short messages when over minimum."""
        messages = []
        # Add enough messages to exceed minimum
        for i in range(10):
            content = "ok" if i % 3 == 0 else f"This is a longer message {i}"
            messages.append({
                "id": i + 1,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": content,
                "timestamp": f"2025-01-01T00:{i:02d}:00"
            })
        
        result = session_chat_service._apply_content_filtering(messages)
        
        # Should filter out very short messages
        short_messages = [msg for msg in result if len(msg["content"]) < 10]
        assert len(short_messages) < len([msg for msg in messages if len(msg["content"]) < 10])
    
    def test_apply_content_filtering_duplicate_content(self, session_chat_service):
        """Test content filtering removes duplicate content."""
        messages = []
        
        # Add enough messages to exceed minimum first
        for i in range(6):
            messages.append({
                "id": i + 1,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Initial message {i}",
                "timestamp": f"2025-01-01T00:{i:02d}:00"
            })
        
        # Now add duplicates that should be filtered
        messages.extend([
            {"id": 7, "role": "user", "content": "Hello there", "timestamp": "2025-01-01T00:06:00"},
            {"id": 8, "role": "assistant", "content": "Hi", "timestamp": "2025-01-01T00:07:00"},
            {"id": 9, "role": "user", "content": "Hello there", "timestamp": "2025-01-01T00:08:00"},  # Duplicate
            {"id": 10, "role": "assistant", "content": "Hi again", "timestamp": "2025-01-01T00:09:00"},
        ])
        
        result = session_chat_service._apply_content_filtering(messages)
        
        # Should have removed the duplicate "Hello there"
        hello_count = len([msg for msg in result if msg["content"] == "Hello there"])
        assert hello_count == 1
    
    def test_calculate_token_savings_no_optimization(self, session_chat_service):
        """Test token savings calculation when no optimization is needed."""
        savings = session_chat_service._calculate_token_savings(10)  # Less than max_context_messages
        
        assert savings["messages_saved"] == 0
        assert savings["estimated_tokens_saved"] == 0
        assert savings["optimization_percentage"] == 0
    
    def test_calculate_token_savings_with_optimization(self, session_chat_service):
        """Test token savings calculation when optimization occurs."""
        total_messages = 50
        savings = session_chat_service._calculate_token_savings(total_messages)
        
        expected_saved = total_messages - session_chat_service.max_context_messages
        expected_tokens = expected_saved * session_chat_service.token_estimate_per_message
        expected_percentage = (expected_saved / total_messages) * 100
        
        assert savings["messages_saved"] == expected_saved
        assert savings["estimated_tokens_saved"] == expected_tokens
        assert savings["optimization_percentage"] == round(expected_percentage, 2)


class TestSessionChatServiceIntegration:
    """Test integration with session service and database operations."""
    
    @pytest.mark.asyncio
    async def test_integration_with_session_service(self, session_chat_service, test_session, mock_gemini_client, mock_chat_session):
        """Test integration between SessionChatService and SessionService."""
        # Setup mock
        mock_gemini_client.create_chat_session.return_value = mock_chat_session
        mock_chat_session.send_message.return_value = "Integration test response"
        
        # Send message
        result = await session_chat_service.send_message(test_session.id, "Integration test")
        
        # Verify messages were stored in database
        session_service = SessionService(session_chat_service.db)
        messages = await session_service.get_session_messages(test_session.id)
        
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Integration test"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Integration test response"
        
        # Verify session was updated
        updated_session = await session_service.get_session(test_session.id)
        assert updated_session.message_count == 2
    
    @pytest.mark.asyncio
    async def test_database_transaction_rollback_on_error(self, session_chat_service, test_session, mock_gemini_client):
        """Test that database transactions are rolled back on errors."""
        # Setup mock to raise an error
        mock_gemini_client.create_chat_session.side_effect = Exception("API Error")
        
        # Attempt to send message (should fail)
        with pytest.raises(RuntimeError, match="Failed to send message"):
            await session_chat_service.send_message(test_session.id, "This should fail")
        
        # Verify no messages were stored in database
        session_service = SessionService(session_chat_service.db)
        messages = await session_service.get_session_messages(test_session.id)
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_message_metadata_storage(self, session_chat_service, test_session, mock_gemini_client, mock_chat_session):
        """Test that message metadata is properly stored."""
        # Setup mock
        mock_gemini_client.create_chat_session.return_value = mock_chat_session
        mock_chat_session.send_message.return_value = "Response with metadata"
        
        # Send message
        result = await session_chat_service.send_message(test_session.id, "Test metadata")
        
        # Verify user message metadata
        assert "timestamp" in result.user_message.message_metadata
        
        # Verify assistant message metadata
        assert "timestamp" in result.assistant_message.message_metadata
        assert "model_used" in result.assistant_message.message_metadata
        assert "context_messages_count" in result.assistant_message.message_metadata
        assert result.assistant_message.message_metadata["model_used"] == test_session.model_used
    
    @pytest.mark.asyncio
    async def test_session_metadata_update_failure_handling(self, session_chat_service, test_session, mock_gemini_client, mock_chat_session):
        """Test that session metadata update failures don't break chat operations."""
        # Setup mock
        mock_gemini_client.create_chat_session.return_value = mock_chat_session
        mock_chat_session.send_message.return_value = "Response despite metadata error"
        
        # Mock session service to fail on metadata update
        with patch.object(session_chat_service.session_service, 'update_session', side_effect=Exception("Metadata update failed")):
            # Send message should still succeed
            result = await session_chat_service.send_message(test_session.id, "Test resilience")
            
            # Verify chat operation completed successfully
            assert result.user_message.content == "Test resilience"
            assert result.assistant_message.content == "Response despite metadata error"
    
    @pytest.mark.asyncio
    async def test_context_optimization_with_real_database(self, session_chat_service, test_session):
        """Test context optimization with real database operations."""
        # Add many messages to test optimization
        session_service = SessionService(session_chat_service.db)
        
        for i in range(25):  # More than max_context_messages
            await session_service.add_message(MessageCreate(
                session_id=test_session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message number {i}"
            ))
        
        # Get optimized context
        context = await session_chat_service.get_conversation_context(test_session.id)
        
        # Should be optimized to max_context_messages
        assert len(context) <= session_chat_service.max_context_messages
        
        # Should contain the most recent messages
        assert "Message number 24" in context[-1]["content"]
        
        # Should maintain conversation flow
        user_messages = [msg for msg in context if msg["role"] == "user"]
        assistant_messages = [msg for msg in context if msg["role"] == "assistant"]
        assert len(user_messages) > 0
        assert len(assistant_messages) > 0


class TestSessionChatServiceErrorHandling:
    """Test error handling for various edge cases."""
    
    @pytest.mark.asyncio
    async def test_gemini_api_error_handling(self, session_chat_service, test_session, mock_gemini_client):
        """Test handling of Gemini API errors."""
        # Setup mock to raise API error
        mock_gemini_client.create_chat_session.side_effect = Exception("Gemini API unavailable")
        
        # Should raise RuntimeError with descriptive message
        with pytest.raises(RuntimeError, match="Failed to send message"):
            await session_chat_service.send_message(test_session.id, "This should fail")
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, session_chat_service, mock_gemini_client, mock_chat_session):
        """Test handling of database errors."""
        # Setup mock
        mock_gemini_client.create_chat_session.return_value = mock_chat_session
        mock_chat_session.send_message.return_value = "Response"
        
        # Mock database session to fail
        with patch.object(session_chat_service.session_service, 'get_session', side_effect=Exception("Database error")):
            with pytest.raises(RuntimeError, match="Failed to send message"):
                await session_chat_service.send_message(1, "Test message")
    
    @pytest.mark.asyncio
    async def test_context_retrieval_error_handling(self, session_chat_service, test_session):
        """Test handling of context retrieval errors."""
        # Mock session service to fail on message retrieval
        with patch.object(session_chat_service.session_service, 'get_session_messages', side_effect=Exception("Context error")):
            with pytest.raises(RuntimeError, match="Failed to get conversation context"):
                await session_chat_service.get_conversation_context(test_session.id)
    
    def test_update_session_metadata_error_resilience(self, session_chat_service):
        """Test that metadata update errors are handled gracefully."""
        # This should not raise an exception, just print a warning
        import asyncio
        
        async def test_metadata_update():
            await session_chat_service._update_session_metadata(999, 5)  # Non-existent session
        
        # Should complete without raising an exception
        asyncio.run(test_metadata_update())