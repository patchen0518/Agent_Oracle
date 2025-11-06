"""
Integration tests for LangChain session service integration.

Tests complete conversation flows with LangChain integration,
memory persistence and restoration across message exchanges,
and API compatibility and response format consistency.
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel

from backend.services.session_chat_service import SessionChatService
from backend.services.session_service import SessionService
from backend.services.langchain_client import LangChainClient
from backend.services.langchain_chat_session import LangChainChatSession
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
def db_session(test_engine):
    """Create a database session for testing."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def mock_langchain_client():
    """Create a mock LangChain client for testing."""
    client = Mock(spec=LangChainClient)
    return client


@pytest.fixture
def mock_langchain_chat_session():
    """Create a mock LangChain chat session for testing."""
    chat_session = Mock(spec=LangChainChatSession)
    chat_session.send_message.return_value = "Mock LangChain response"
    chat_session.send_message_stream.return_value = iter(["Mock", " stream", " response"])
    chat_session.get_conversation_history.return_value = []
    chat_session.get_message_count.return_value = 0
    chat_session.get_optimization_stats.return_value = {
        "optimizer": {"optimizations_performed": 1, "tokens_saved": 50},
        "middleware": {"auto_summarizations": 0}
    }
    return chat_session


@pytest.fixture
def session_chat_service_with_langchain(db_session, mock_langchain_client):
    """Create a SessionChatService with LangChain integration for testing."""
    return SessionChatService(db_session, mock_langchain_client)


@pytest.fixture
async def test_session_model(db_session):
    """Create a test session in the database."""
    session_service = SessionService(db_session)
    session_data = SessionCreate(title="LangChain Integration Test Session")
    return await session_service.create_session(session_data)


class TestLangChainSessionIntegration:
    """Test complete conversation flows with LangChain integration."""
    
    @pytest.mark.asyncio
    async def test_complete_conversation_flow_with_langchain(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test complete conversation flow using LangChain integration."""
        # Setup LangChain client mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.side_effect = [
            "Hello! I'm powered by LangChain.",
            "Python is a programming language with LangChain integration.",
            "LangChain provides advanced memory management."
        ]
        
        # Simulate a multi-turn conversation
        conversations = [
            ("Hello, are you using LangChain?", "Hello! I'm powered by LangChain."),
            ("What is Python?", "Python is a programming language with LangChain integration."),
            ("Tell me about memory management", "LangChain provides advanced memory management.")
        ]
        
        responses = []
        for user_message, expected_ai_response in conversations:
            response = await session_chat_service_with_langchain.send_message(
                test_session_model.id, 
                user_message
            )
            responses.append(response)
            
            # Verify response structure
            assert isinstance(response, ChatResponse)
            assert response.user_message.content == user_message
            assert response.assistant_message.content == expected_ai_response
            assert response.session.id == test_session_model.id
        
        # Verify LangChain client was used for all messages
        assert mock_langchain_client.get_or_create_session.call_count == 3
        assert mock_langchain_chat_session.send_message.call_count == 3
        
        # Verify all messages were stored in database
        session_service = SessionService(session_chat_service_with_langchain.db)
        messages = await session_service.get_session_messages(test_session_model.id)
        
        assert len(messages) == 6  # 3 user + 3 assistant messages
        
        # Verify message order and content
        for i, (user_msg, ai_msg) in enumerate(conversations):
            user_db_msg = messages[i * 2]
            ai_db_msg = messages[i * 2 + 1]
            
            assert user_db_msg.role == "user"
            assert user_db_msg.content == user_msg
            assert ai_db_msg.role == "assistant"
            assert ai_db_msg.content == ai_msg
    
    @pytest.mark.asyncio
    async def test_streaming_conversation_with_langchain(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test streaming conversation with LangChain integration."""
        # Setup streaming mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message_stream.return_value = iter([
            "LangChain", " streaming", " response", " works", " great!"
        ])
        
        # Test streaming response
        chunks = []
        async for chunk in session_chat_service_with_langchain.send_message_stream(
            test_session_model.id, 
            "Test streaming with LangChain"
        ):
            chunks.append(chunk)
        
        # Verify streaming chunks
        expected_chunks = ["LangChain", " streaming", " response", " works", " great!"]
        assert chunks == expected_chunks
        
        # Verify complete message was stored
        session_service = SessionService(session_chat_service_with_langchain.db)
        messages = await session_service.get_session_messages(test_session_model.id)
        
        assert len(messages) == 2  # user + assistant
        assert messages[0].content == "Test streaming with LangChain"
        assert messages[1].content == "LangChain streaming response works great!"
    
    @pytest.mark.asyncio
    async def test_langchain_session_with_system_instructions(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test LangChain session with system instructions."""
        # Setup mock with system instruction
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "I'm a helpful LangChain assistant."
        
        # Update session with system instruction
        session_service = SessionService(session_chat_service_with_langchain.db)
        await session_service.update_session(
            test_session_model.id, 
            {"system_instruction": "You are a helpful programming assistant using LangChain."}
        )
        
        # Send message
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Hello"
        )
        
        # Verify LangChain client was called with system instruction
        mock_langchain_client.get_or_create_session.assert_called()
        call_args = mock_langchain_client.get_or_create_session.call_args
        assert "You are a helpful programming assistant using LangChain." in str(call_args)
        
        # Verify response
        assert response.assistant_message.content == "I'm a helpful LangChain assistant."
    
    @pytest.mark.asyncio
    async def test_langchain_error_handling_and_fallback(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client
    ):
        """Test error handling and fallback when LangChain operations fail."""
        # Setup LangChain client to fail
        mock_langchain_client.get_or_create_session.side_effect = Exception("LangChain error")
        
        # Mock fallback to regular client
        with patch.object(session_chat_service_with_langchain, '_create_fallback_chat_session') as mock_fallback:
            mock_fallback_session = Mock()
            mock_fallback_session.send_message.return_value = "Fallback response"
            mock_fallback.return_value = mock_fallback_session
            
            # Send message (should use fallback)
            response = await session_chat_service_with_langchain.send_message(
                test_session_model.id, 
                "Test fallback"
            )
            
            # Verify fallback was used
            mock_fallback.assert_called_once()
            assert response.assistant_message.content == "Fallback response"
            
            # Verify message was still stored
            session_service = SessionService(session_chat_service_with_langchain.db)
            messages = await session_service.get_session_messages(test_session_model.id)
            assert len(messages) == 2


class TestMemoryPersistenceAndRestoration:
    """Test memory persistence and restoration across message exchanges."""
    
    @pytest.mark.asyncio
    async def test_memory_restoration_from_database(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test memory restoration from existing database messages."""
        # Add existing messages to database
        session_service = SessionService(session_chat_service_with_langchain.db)
        
        existing_messages = [
            MessageCreate(session_id=test_session_model.id, role="user", content="Previous question 1"),
            MessageCreate(session_id=test_session_model.id, role="assistant", content="Previous answer 1"),
            MessageCreate(session_id=test_session_model.id, role="user", content="Previous question 2"),
            MessageCreate(session_id=test_session_model.id, role="assistant", content="Previous answer 2"),
        ]
        
        for msg_data in existing_messages:
            await session_service.add_message(msg_data)
        
        # Setup LangChain mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "New response with context"
        
        # Send new message
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "New question"
        )
        
        # Verify LangChain client was called with recent messages for context restoration
        mock_langchain_client.get_or_create_session.assert_called()
        call_args = mock_langchain_client.get_or_create_session.call_args
        
        # Should have been called with recent messages
        assert len(call_args[1]['recent_messages']) > 0
        
        # Verify the recent messages contain the existing conversation
        recent_messages = call_args[1]['recent_messages']
        assert any("Previous question" in str(msg) for msg in recent_messages)
        assert any("Previous answer" in str(msg) for msg in recent_messages)
        
        # Verify new response
        assert response.assistant_message.content == "New response with context"
    
    @pytest.mark.asyncio
    async def test_memory_persistence_across_sessions(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test that memory persists correctly across multiple session interactions."""
        # Setup LangChain mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.side_effect = [
            "I remember this conversation",
            "Building on our previous discussion",
            "Continuing from where we left off"
        ]
        
        # First conversation
        await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Let's start a conversation about Python"
        )
        
        # Second message (should have context from first)
        await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Tell me more about it"
        )
        
        # Third message (should have context from both previous)
        await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Can you elaborate further?"
        )
        
        # Verify all messages were stored
        session_service = SessionService(session_chat_service_with_langchain.db)
        messages = await session_service.get_session_messages(test_session_model.id)
        
        assert len(messages) == 6  # 3 user + 3 assistant messages
        
        # Verify conversation continuity in database
        conversation_flow = [
            ("Let's start a conversation about Python", "I remember this conversation"),
            ("Tell me more about it", "Building on our previous discussion"),
            ("Can you elaborate further?", "Continuing from where we left off")
        ]
        
        for i, (user_msg, ai_msg) in enumerate(conversation_flow):
            assert messages[i * 2].content == user_msg
            assert messages[i * 2 + 1].content == ai_msg
    
    @pytest.mark.asyncio
    async def test_memory_optimization_integration(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test integration with memory optimization features."""
        # Setup LangChain mock with optimization stats
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "Optimized response"
        mock_langchain_chat_session.get_optimization_stats.return_value = {
            "optimizer": {
                "optimizations_performed": 2,
                "tokens_saved": 150,
                "relevance_calculations": 10
            },
            "middleware": {
                "auto_summarizations": 1,
                "middleware_invocations": 5
            }
        }
        
        # Add many messages to trigger optimization
        session_service = SessionService(session_chat_service_with_langchain.db)
        for i in range(15):
            await session_service.add_message(MessageCreate(
                session_id=test_session_model.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i} with some content to build up context"
            ))
        
        # Send new message
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "New message after optimization"
        )
        
        # Verify optimization stats are available
        stats = mock_langchain_chat_session.get_optimization_stats()
        assert stats["optimizer"]["optimizations_performed"] > 0
        assert stats["optimizer"]["tokens_saved"] > 0
        
        # Verify response includes optimization metadata
        assert response.assistant_message.content == "Optimized response"
    
    @pytest.mark.asyncio
    async def test_cross_session_isolation(
        self, 
        session_chat_service_with_langchain, 
        db_session, 
        mock_langchain_client
    ):
        """Test that memory is properly isolated between different sessions."""
        # Create two separate sessions
        session_service = SessionService(db_session)
        session1 = await session_service.create_session(SessionCreate(title="Session 1"))
        session2 = await session_service.create_session(SessionCreate(title="Session 2"))
        
        # Setup separate LangChain chat sessions
        mock_chat_session1 = Mock(spec=LangChainChatSession)
        mock_chat_session2 = Mock(spec=LangChainChatSession)
        
        mock_chat_session1.send_message.return_value = "Response from session 1"
        mock_chat_session2.send_message.return_value = "Response from session 2"
        
        # Mock client to return different sessions based on session_id
        def get_session_mock(session_id, system_instruction=None, recent_messages=None):
            if session_id == session1.id:
                return mock_chat_session1
            elif session_id == session2.id:
                return mock_chat_session2
            else:
                raise ValueError(f"Unexpected session_id: {session_id}")
        
        mock_langchain_client.get_or_create_session.side_effect = get_session_mock
        
        # Send messages to both sessions
        response1 = await session_chat_service_with_langchain.send_message(
            session1.id, 
            "Message to session 1"
        )
        
        response2 = await session_chat_service_with_langchain.send_message(
            session2.id, 
            "Message to session 2"
        )
        
        # Verify responses are session-specific
        assert response1.assistant_message.content == "Response from session 1"
        assert response2.assistant_message.content == "Response from session 2"
        assert response1.session.id == session1.id
        assert response2.session.id == session2.id
        
        # Verify database isolation
        messages1 = await session_service.get_session_messages(session1.id)
        messages2 = await session_service.get_session_messages(session2.id)
        
        assert len(messages1) == 2  # user + assistant for session 1
        assert len(messages2) == 2  # user + assistant for session 2
        
        # Verify content isolation
        session1_contents = [msg.content for msg in messages1]
        session2_contents = [msg.content for msg in messages2]
        
        assert "Message to session 1" in session1_contents
        assert "Response from session 1" in session1_contents
        assert "Message to session 2" not in session1_contents
        
        assert "Message to session 2" in session2_contents
        assert "Response from session 2" in session2_contents
        assert "Message to session 1" not in session2_contents


class TestAPICompatibilityAndResponseFormat:
    """Test API compatibility and response format consistency."""
    
    @pytest.mark.asyncio
    async def test_response_format_consistency_with_langchain(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test that LangChain integration maintains consistent response format."""
        # Setup LangChain mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "LangChain response"
        
        # Send message
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Test message"
        )
        
        # Verify response structure matches expected ChatResponse format
        assert isinstance(response, ChatResponse)
        
        # Verify user message structure
        assert isinstance(response.user_message, MessagePublic)
        assert response.user_message.content == "Test message"
        assert response.user_message.role == "user"
        assert response.user_message.session_id == test_session_model.id
        assert isinstance(response.user_message.created_at, datetime)
        
        # Verify assistant message structure
        assert isinstance(response.assistant_message, MessagePublic)
        assert response.assistant_message.content == "LangChain response"
        assert response.assistant_message.role == "assistant"
        assert response.assistant_message.session_id == test_session_model.id
        assert isinstance(response.assistant_message.created_at, datetime)
        
        # Verify session structure
        assert isinstance(response.session, SessionPublic)
        assert response.session.id == test_session_model.id
        assert response.session.message_count == 2  # user + assistant
        
        # Verify message metadata contains LangChain-specific information
        assert "timestamp" in response.assistant_message.message_metadata
        assert "model_used" in response.assistant_message.message_metadata
    
    @pytest.mark.asyncio
    async def test_streaming_response_format_consistency(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test that streaming responses maintain format consistency."""
        # Setup streaming mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message_stream.return_value = iter([
            "Streaming", " LangChain", " response"
        ])
        
        # Collect streaming chunks
        chunks = []
        async for chunk in session_chat_service_with_langchain.send_message_stream(
            test_session_model.id, 
            "Test streaming"
        ):
            chunks.append(chunk)
        
        # Verify chunks are strings
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert chunks == ["Streaming", " LangChain", " response"]
        
        # Verify complete message was stored correctly
        session_service = SessionService(session_chat_service_with_langchain.db)
        messages = await session_service.get_session_messages(test_session_model.id)
        
        assert len(messages) == 2
        assert messages[1].content == "Streaming LangChain response"
        assert messages[1].role == "assistant"
    
    @pytest.mark.asyncio
    async def test_error_response_format_consistency(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client
    ):
        """Test that error responses maintain format consistency."""
        # Setup LangChain client to fail
        mock_langchain_client.get_or_create_session.side_effect = Exception("LangChain integration error")
        
        # Test error handling
        with pytest.raises(RuntimeError, match="Failed to send message"):
            await session_chat_service_with_langchain.send_message(
                test_session_model.id, 
                "This should fail"
            )
        
        # Verify no partial messages were stored
        session_service = SessionService(session_chat_service_with_langchain.db)
        messages = await session_service.get_session_messages(test_session_model.id)
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_metadata_consistency_with_langchain(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test that message metadata is consistent with LangChain integration."""
        # Setup LangChain mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "Response with metadata"
        
        # Send message
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Test metadata"
        )
        
        # Verify user message metadata
        user_metadata = response.user_message.message_metadata
        assert "timestamp" in user_metadata
        assert isinstance(user_metadata["timestamp"], str)
        
        # Verify assistant message metadata
        assistant_metadata = response.assistant_message.message_metadata
        assert "timestamp" in assistant_metadata
        assert "model_used" in assistant_metadata
        assert "context_messages_count" in assistant_metadata
        
        # Verify LangChain-specific metadata
        assert assistant_metadata["model_used"] == test_session_model.model_used
        assert isinstance(assistant_metadata["context_messages_count"], int)
    
    @pytest.mark.asyncio
    async def test_session_metadata_updates_with_langchain(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test that session metadata is properly updated with LangChain integration."""
        # Setup LangChain mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "Response for metadata test"
        
        # Record initial session state
        initial_updated_at = test_session_model.updated_at
        initial_message_count = test_session_model.message_count
        
        # Send message
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Test session metadata"
        )
        
        # Verify session metadata was updated
        assert response.session.message_count == initial_message_count + 2  # user + assistant
        assert response.session.updated_at > initial_updated_at
        
        # Verify session metadata in database
        session_service = SessionService(session_chat_service_with_langchain.db)
        updated_session = await session_service.get_session(test_session_model.id)
        
        assert "last_activity" in updated_session.session_metadata
        assert "total_messages" in updated_session.session_metadata
        assert updated_session.session_metadata["total_messages"] == 2
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_with_existing_sessions(
        self, 
        session_chat_service_with_langchain, 
        db_session, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test backward compatibility with existing sessions created before LangChain integration."""
        # Create a session that simulates pre-LangChain format
        session_service = SessionService(db_session)
        legacy_session = await session_service.create_session(SessionCreate(
            title="Legacy Session",
            model_used="gemini-2.5-flash",  # Pre-LangChain model
            system_instruction="Legacy system instruction"
        ))
        
        # Add some legacy messages
        await session_service.add_message(MessageCreate(
            session_id=legacy_session.id,
            role="user",
            content="Legacy user message"
        ))
        await session_service.add_message(MessageCreate(
            session_id=legacy_session.id,
            role="assistant",
            content="Legacy assistant message"
        ))
        
        # Setup LangChain mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "New LangChain response"
        
        # Send new message to legacy session
        response = await session_chat_service_with_langchain.send_message(
            legacy_session.id, 
            "New message to legacy session"
        )
        
        # Verify LangChain integration works with legacy session
        assert response.assistant_message.content == "New LangChain response"
        
        # Verify legacy messages were provided as context
        mock_langchain_client.get_or_create_session.assert_called()
        call_args = mock_langchain_client.get_or_create_session.call_args
        recent_messages = call_args[1]['recent_messages']
        
        # Should include legacy messages in context
        assert len(recent_messages) >= 2
        assert any("Legacy user message" in str(msg) for msg in recent_messages)
        assert any("Legacy assistant message" in str(msg) for msg in recent_messages)
        
        # Verify all messages are now in database
        all_messages = await session_service.get_session_messages(legacy_session.id)
        assert len(all_messages) == 4  # 2 legacy + 2 new messages


class TestLangChainIntegrationPerformance:
    """Test performance aspects of LangChain integration."""
    
    @pytest.mark.asyncio
    async def test_context_optimization_performance(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test that context optimization improves performance."""
        # Setup LangChain mock with optimization stats
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "Optimized response"
        mock_langchain_chat_session.get_optimization_stats.return_value = {
            "optimizer": {
                "optimizations_performed": 3,
                "tokens_saved": 250,
                "relevance_calculations": 15
            },
            "middleware": {
                "auto_summarizations": 1,
                "middleware_invocations": 8,
                "summarization_rate": 0.125
            }
        }
        
        # Add many messages to create optimization opportunity
        session_service = SessionService(session_chat_service_with_langchain.db)
        for i in range(25):
            await session_service.add_message(MessageCreate(
                session_id=test_session_model.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Performance test message {i} with substantial content to test optimization"
            ))
        
        # Send message that should trigger optimization
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Test optimization performance"
        )
        
        # Verify optimization occurred
        stats = mock_langchain_chat_session.get_optimization_stats()
        assert stats["optimizer"]["optimizations_performed"] > 0
        assert stats["optimizer"]["tokens_saved"] > 0
        
        # Verify response quality maintained
        assert response.assistant_message.content == "Optimized response"
        assert response.session.message_count == 27  # 25 existing + 2 new
    
    @pytest.mark.asyncio
    async def test_memory_efficiency_with_large_conversations(
        self, 
        session_chat_service_with_langchain, 
        test_session_model, 
        mock_langchain_client, 
        mock_langchain_chat_session
    ):
        """Test memory efficiency with large conversation histories."""
        # Setup LangChain mock
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_chat_session
        mock_langchain_chat_session.send_message.return_value = "Efficient response"
        
        # Create large conversation history
        session_service = SessionService(session_chat_service_with_langchain.db)
        for i in range(50):
            await session_service.add_message(MessageCreate(
                session_id=test_session_model.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Large conversation message {i} " * 20  # Make messages substantial
            ))
        
        # Send new message
        response = await session_chat_service_with_langchain.send_message(
            test_session_model.id, 
            "Test with large history"
        )
        
        # Verify LangChain client was called with optimized context
        mock_langchain_client.get_or_create_session.assert_called()
        call_args = mock_langchain_client.get_or_create_session.call_args
        recent_messages = call_args[1]['recent_messages']
        
        # Should have limited the context size for efficiency
        assert len(recent_messages) < 50  # Should be optimized
        assert len(recent_messages) > 0   # But not empty
        
        # Verify response quality maintained
        assert response.assistant_message.content == "Efficient response"
    
    @pytest.mark.asyncio
    async def test_concurrent_session_handling(
        self, 
        session_chat_service_with_langchain, 
        db_session, 
        mock_langchain_client
    ):
        """Test handling of concurrent sessions with LangChain integration."""
        import asyncio
        
        # Create multiple sessions
        session_service = SessionService(db_session)
        sessions = []
        for i in range(5):
            session = await session_service.create_session(SessionCreate(
                title=f"Concurrent Session {i}"
            ))
            sessions.append(session)
        
        # Setup LangChain mock to return session-specific responses
        def create_mock_session(session_id):
            mock_session = Mock(spec=LangChainChatSession)
            mock_session.send_message.return_value = f"Response for session {session_id}"
            return mock_session
        
        mock_langchain_client.get_or_create_session.side_effect = lambda sid, **kwargs: create_mock_session(sid)
        
        # Send concurrent messages to all sessions
        async def send_message_to_session(session):
            return await session_chat_service_with_langchain.send_message(
                session.id, 
                f"Concurrent message to session {session.id}"
            )
        
        # Execute concurrent requests
        tasks = [send_message_to_session(session) for session in sessions]
        responses = await asyncio.gather(*tasks)
        
        # Verify all responses are correct and session-specific
        assert len(responses) == 5
        for i, response in enumerate(responses):
            expected_content = f"Response for session {sessions[i].id}"
            assert response.assistant_message.content == expected_content
            assert response.session.id == sessions[i].id
        
        # Verify all messages were stored correctly
        for session in sessions:
            messages = await session_service.get_session_messages(session.id)
            assert len(messages) == 2  # user + assistant
            assert f"Concurrent message to session {session.id}" in messages[0].content