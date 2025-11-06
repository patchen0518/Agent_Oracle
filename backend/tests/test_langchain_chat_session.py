"""
Unit tests for LangChainChatSession class.

Tests message handling and conversation flow, system instruction processing,
context optimization, and memory management functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.exceptions import LangChainException

from backend.services.langchain_chat_session import LangChainChatSession
from backend.exceptions import (
    AIServiceError,
    LangChainError,
    MessageProcessingError
)


class TestLangChainChatSessionInitialization:
    """Test LangChainChatSession initialization and configuration."""
    
    @pytest.fixture
    def mock_chat_model(self):
        """Create a mock ChatGoogleGenerativeAI."""
        mock_model = Mock()
        mock_model.invoke.return_value = Mock(content="Test response")
        return mock_model
    
    @pytest.fixture
    def mock_context_optimizer(self):
        """Create a mock ContextOptimizer."""
        mock_optimizer = Mock()
        mock_optimizer.calculate_token_usage.return_value = 100
        mock_optimizer.should_optimize_context.return_value = False
        mock_optimizer.optimize_context.return_value = []
        return mock_optimizer
    
    def test_initialization_basic(self, mock_chat_model):
        """Test basic initialization without system instruction."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    session = LangChainChatSession(mock_chat_model, session_id=123)
                    
                    assert session.chat_model == mock_chat_model
                    assert session.session_id == 123
                    assert session.conversation_history == []
                    assert hasattr(session, 'context_optimizer')
                    assert hasattr(session, 'summarization_middleware')
                    assert hasattr(session, 'fallback_manager')
    
    def test_initialization_with_system_instruction(self, mock_chat_model):
        """Test initialization with system instruction."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    session = LangChainChatSession(
                        mock_chat_model, 
                        session_id=123, 
                        system_instruction="You are a helpful assistant."
                    )
                    
                    assert len(session.conversation_history) == 1
                    assert isinstance(session.conversation_history[0], SystemMessage)
                    assert session.conversation_history[0].content == "You are a helpful assistant."
    
    def test_initialization_with_context_optimizer(self, mock_chat_model, mock_context_optimizer):
        """Test initialization with provided context optimizer."""
        with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
            with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                mock_middleware.return_value = Mock()
                mock_fallback.return_value = Mock()
                
                session = LangChainChatSession(
                    mock_chat_model, 
                    session_id=123, 
                    context_optimizer=mock_context_optimizer
                )
                
                assert session.context_optimizer == mock_context_optimizer


class TestLangChainChatSessionMessageHandling:
    """Test message sending and response handling."""
    
    @pytest.fixture
    def chat_session(self, mock_chat_model):
        """Create a LangChainChatSession for testing."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer = Mock()
                    mock_optimizer.calculate_token_usage.return_value = 100
                    mock_optimizer.should_optimize_context.return_value = False
                    mock_optimizer_class.return_value = mock_optimizer
                    
                    mock_middleware_instance = Mock()
                    mock_middleware_instance.process_messages.return_value = []
                    mock_middleware.return_value = mock_middleware_instance
                    
                    mock_fallback_instance = Mock()
                    mock_fallback_instance.execute_with_fallback.side_effect = lambda func, op, **kwargs: func(**kwargs)
                    mock_fallback_instance.is_in_fallback_mode.return_value = False
                    mock_fallback.return_value = mock_fallback_instance
                    
                    session = LangChainChatSession(mock_chat_model, session_id=123)
                    session.context_optimizer = mock_optimizer
                    session.summarization_middleware = mock_middleware_instance
                    session.fallback_manager = mock_fallback_instance
                    
                    return session
    
    def test_send_message_success(self, chat_session, mock_chat_model):
        """Test successful message sending and response."""
        mock_response = Mock()
        mock_response.content = "Hello! How can I help you?"
        mock_chat_model.invoke.return_value = mock_response
        
        with patch('backend.services.langchain_chat_session.langchain_monitor') as mock_monitor:
            mock_monitor.monitor_operation.return_value.__enter__.return_value = "op_id"
            mock_monitor.monitor_operation.return_value.__exit__.return_value = None
            
            result = chat_session.send_message("Hello, AI!")
            
            assert result == "Hello! How can I help you?"
            assert len(chat_session.conversation_history) == 2
            assert isinstance(chat_session.conversation_history[0], HumanMessage)
            assert isinstance(chat_session.conversation_history[1], AIMessage)
            assert chat_session.conversation_history[0].content == "Hello, AI!"
            assert chat_session.conversation_history[1].content == "Hello! How can I help you?"
    
    def test_send_message_stream_success(self, chat_session, mock_chat_model):
        """Test successful streaming message sending."""
        # Mock streaming response
        mock_chunks = [Mock(content="Hello"), Mock(content=" there"), Mock(content="!")]
        mock_chat_model.stream.return_value = iter(mock_chunks)
        
        with patch('backend.services.langchain_chat_session.langchain_monitor') as mock_monitor:
            mock_monitor.monitor_operation.return_value.__enter__.return_value = "op_id"
            mock_monitor.monitor_operation.return_value.__exit__.return_value = None
            
            chunks = list(chat_session.send_message_stream("Hello, AI!"))
            
            assert chunks == ["Hello", " there", "!"]
            assert len(chat_session.conversation_history) == 2
            assert chat_session.conversation_history[1].content == "Hello there!"
    
    def test_send_message_langchain_exception(self, chat_session, mock_chat_model):
        """Test handling of LangChain exceptions during message sending."""
        mock_chat_model.invoke.side_effect = LangChainException("API error")
        
        with patch('backend.services.langchain_chat_session.langchain_monitor') as mock_monitor:
            mock_monitor.monitor_operation.return_value.__enter__.return_value = "op_id"
            mock_monitor.monitor_operation.return_value.__exit__.return_value = None
            
            with pytest.raises(LangChainError):
                chat_session.send_message("Hello, AI!")
    
    def test_send_message_generic_exception(self, chat_session, mock_chat_model):
        """Test handling of generic exceptions during message sending."""
        mock_chat_model.invoke.side_effect = Exception("Generic error")
        
        with patch('backend.services.langchain_chat_session.langchain_monitor') as mock_monitor:
            mock_monitor.monitor_operation.return_value.__enter__.return_value = "op_id"
            mock_monitor.monitor_operation.return_value.__exit__.return_value = None
            
            with pytest.raises(AIServiceError):
                chat_session.send_message("Hello, AI!")


class TestLangChainChatSessionSystemInstructions:
    """Test system instruction processing and personality configuration."""
    
    @pytest.fixture
    def mock_chat_model(self):
        """Create a mock ChatGoogleGenerativeAI."""
        return Mock()
    
    def test_process_system_instruction_direct_text(self, mock_chat_model):
        """Test processing direct system instruction text."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    session = LangChainChatSession(mock_chat_model, session_id=123)
                    session._process_system_instruction("You are a helpful assistant.")
                    
                    assert len(session.conversation_history) == 1
                    assert isinstance(session.conversation_history[0], SystemMessage)
                    assert session.conversation_history[0].content == "You are a helpful assistant."
    
    def test_process_system_instruction_type_name(self, mock_chat_model):
        """Test processing system instruction type name."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    with patch('backend.services.langchain_chat_session.SYSTEM_INSTRUCTIONS', {"helpful": "instruction"}):
                        with patch('backend.services.langchain_chat_session.get_system_instruction') as mock_get:
                            mock_optimizer_class.return_value = Mock()
                            mock_middleware.return_value = Mock()
                            mock_fallback.return_value = Mock()
                            mock_get.return_value = "You are a helpful assistant."
                            
                            session = LangChainChatSession(mock_chat_model, session_id=123)
                            session._process_system_instruction("helpful")
                            
                            assert len(session.conversation_history) == 1
                            assert isinstance(session.conversation_history[0], SystemMessage)
                            assert session.conversation_history[0].content == "You are a helpful assistant."
                            mock_get.assert_called_once_with("helpful")
    
    def test_process_system_instruction_empty(self, mock_chat_model):
        """Test processing empty system instruction."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    session = LangChainChatSession(mock_chat_model, session_id=123)
                    session._process_system_instruction("")
                    
                    assert len(session.conversation_history) == 0
    
    def test_update_system_instruction(self, mock_chat_model):
        """Test updating system instruction."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    session = LangChainChatSession(
                        mock_chat_model, 
                        session_id=123, 
                        system_instruction="Old instruction"
                    )
                    
                    # Add some conversation messages
                    session.conversation_history.append(HumanMessage(content="Hello"))
                    session.conversation_history.append(AIMessage(content="Hi"))
                    
                    session.update_system_instruction("New instruction")
                    
                    # Should have new system instruction plus conversation messages
                    assert len(session.conversation_history) == 3
                    assert isinstance(session.conversation_history[0], SystemMessage)
                    assert session.conversation_history[0].content == "New instruction"
                    assert session.conversation_history[1].content == "Hello"
                    assert session.conversation_history[2].content == "Hi"
    
    def test_get_system_instruction(self, mock_chat_model):
        """Test getting current system instruction."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    session = LangChainChatSession(
                        mock_chat_model, 
                        session_id=123, 
                        system_instruction="Test instruction"
                    )
                    
                    result = session.get_system_instruction()
                    assert result == "Test instruction"
    
    def test_has_system_instruction(self, mock_chat_model):
        """Test checking if session has system instruction."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    # Session without system instruction
                    session1 = LangChainChatSession(mock_chat_model, session_id=123)
                    assert session1.has_system_instruction() is False
                    
                    # Session with system instruction
                    session2 = LangChainChatSession(
                        mock_chat_model, 
                        session_id=124, 
                        system_instruction="Test instruction"
                    )
                    assert session2.has_system_instruction() is True


class TestLangChainChatSessionConversationHistory:
    """Test conversation history management."""
    
    @pytest.fixture
    def chat_session(self, mock_chat_model):
        """Create a LangChainChatSession for testing."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    return LangChainChatSession(mock_chat_model, session_id=123)
    
    def test_get_conversation_history(self, chat_session):
        """Test getting conversation history as LangChain messages."""
        # Add some messages
        chat_session.conversation_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        
        history = chat_session.get_conversation_history()
        
        assert len(history) == 2
        assert isinstance(history[0], HumanMessage)
        assert isinstance(history[1], AIMessage)
        assert history[0].content == "Hello"
        assert history[1].content == "Hi there!"
        
        # Verify it's a copy
        assert history is not chat_session.conversation_history
    
    def test_get_history_dictionary_format(self, chat_session):
        """Test getting conversation history in dictionary format."""
        # Add messages including system message
        chat_session.conversation_history = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        
        history = chat_session.get_history()
        
        # Should exclude system messages
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi there!"}
    
    def test_clear_history(self, chat_session):
        """Test clearing conversation history while preserving system instructions."""
        # Add messages including system message
        chat_session.conversation_history = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        
        chat_session.clear_history()
        
        # Should keep only system messages
        assert len(chat_session.conversation_history) == 1
        assert isinstance(chat_session.conversation_history[0], SystemMessage)
        assert chat_session.conversation_history[0].content == "You are helpful"
    
    def test_get_message_count(self, chat_session):
        """Test getting message count excluding system messages."""
        # Add messages including system message
        chat_session.conversation_history = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?")
        ]
        
        count = chat_session.get_message_count()
        
        # Should count only user and assistant messages
        assert count == 3


class TestLangChainChatSessionContextRestoration:
    """Test context restoration from database messages."""
    
    @pytest.fixture
    def chat_session(self, mock_chat_model):
        """Create a LangChainChatSession for testing."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer = Mock()
                    mock_optimizer.calculate_token_usage.return_value = 100
                    mock_optimizer.config.messages_to_keep_after_summary = 20
                    mock_optimizer.config.max_tokens_before_summary = 4000
                    mock_optimizer_class.return_value = mock_optimizer
                    
                    mock_middleware_instance = Mock()
                    mock_middleware.return_value = mock_middleware_instance
                    
                    mock_fallback_instance = Mock()
                    mock_fallback_instance.execute_with_fallback.side_effect = lambda func, op, **kwargs: func(**kwargs)
                    mock_fallback.return_value = mock_fallback_instance
                    
                    session = LangChainChatSession(mock_chat_model, session_id=123)
                    session.context_optimizer = mock_optimizer
                    session.fallback_manager = mock_fallback_instance
                    
                    return session
    
    def test_restore_context_success(self, chat_session):
        """Test successful context restoration from database messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        
        with patch.object(chat_session, '_optimize_restored_context') as mock_optimize:
            chat_session.restore_context(messages)
            
            assert len(chat_session.conversation_history) == 3
            assert isinstance(chat_session.conversation_history[0], HumanMessage)
            assert isinstance(chat_session.conversation_history[1], AIMessage)
            assert isinstance(chat_session.conversation_history[2], HumanMessage)
            mock_optimize.assert_called_once()
    
    def test_restore_context_empty_messages(self, chat_session):
        """Test context restoration with empty message list."""
        chat_session.restore_context([])
        
        assert len(chat_session.conversation_history) == 0
    
    def test_convert_database_message_to_langchain(self, chat_session):
        """Test converting database messages to LangChain format."""
        # Test user message
        user_msg = {"role": "user", "content": "Hello"}
        result = chat_session._convert_database_message_to_langchain(user_msg)
        assert isinstance(result, HumanMessage)
        assert result.content == "Hello"
        
        # Test assistant message
        assistant_msg = {"role": "assistant", "content": "Hi there!"}
        result = chat_session._convert_database_message_to_langchain(assistant_msg)
        assert isinstance(result, AIMessage)
        assert result.content == "Hi there!"
        
        # Test system message
        system_msg = {"role": "system", "content": "You are helpful"}
        result = chat_session._convert_database_message_to_langchain(system_msg)
        assert isinstance(result, SystemMessage)
        assert result.content == "You are helpful"
        
        # Test unknown role
        unknown_msg = {"role": "unknown", "content": "Test"}
        result = chat_session._convert_database_message_to_langchain(unknown_msg)
        assert result is None
        
        # Test empty content
        empty_msg = {"role": "user", "content": ""}
        result = chat_session._convert_database_message_to_langchain(empty_msg)
        assert result is None
    
    def test_select_messages_for_restoration(self, chat_session):
        """Test intelligent message selection for restoration."""
        # Create many messages
        messages = []
        for i in range(30):
            messages.append({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}"
            })
        
        selected = chat_session._select_messages_for_restoration(messages)
        
        # Should select recent messages within limits
        assert len(selected) <= chat_session.context_optimizer.config.messages_to_keep_after_summary
        assert selected[-1]["content"] == "Message 29"  # Most recent message


class TestLangChainChatSessionOptimizationAndFallback:
    """Test context optimization and fallback functionality."""
    
    @pytest.fixture
    def chat_session(self, mock_chat_model):
        """Create a LangChainChatSession for testing."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer = Mock()
                    mock_optimizer.get_optimization_stats.return_value = {"optimizations": 5}
                    mock_optimizer_class.return_value = mock_optimizer
                    
                    mock_middleware_instance = Mock()
                    mock_middleware_instance.get_middleware_stats.return_value = {"summaries": 2}
                    mock_middleware.return_value = mock_middleware_instance
                    
                    mock_fallback_instance = Mock()
                    mock_fallback_instance.get_fallback_status.return_value = {"fallback_count": 1}
                    mock_fallback_instance.is_in_fallback_mode.return_value = False
                    mock_fallback.return_value = mock_fallback_instance
                    
                    session = LangChainChatSession(mock_chat_model, session_id=123)
                    session.context_optimizer = mock_optimizer
                    session.summarization_middleware = mock_middleware_instance
                    session.fallback_manager = mock_fallback_instance
                    
                    return session
    
    def test_get_optimization_stats(self, chat_session):
        """Test getting optimization statistics."""
        stats = chat_session.get_optimization_stats()
        
        assert stats["session_id"] == 123
        assert stats["conversation_length"] == 0
        assert stats["optimizer"]["optimizations"] == 5
        assert stats["middleware"]["summaries"] == 2
    
    def test_get_fallback_status(self, chat_session):
        """Test getting fallback status."""
        status = chat_session.get_fallback_status()
        
        assert status["fallback_count"] == 1
    
    def test_is_in_fallback_mode(self, chat_session):
        """Test checking fallback mode status."""
        assert chat_session.is_in_fallback_mode() is False
    
    def test_get_memory_health_status(self, chat_session):
        """Test getting comprehensive memory health status."""
        health = chat_session.get_memory_health_status()
        
        assert health["session_id"] == 123
        assert health["memory_health"] == "healthy"
        assert health["last_optimization_successful"] is True
        assert "fallback_status" in health
        assert "optimization_stats" in health
    
    def test_force_context_optimization(self, chat_session):
        """Test forcing context optimization."""
        # Add some messages
        chat_session.conversation_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        
        chat_session.context_optimizer.optimize_context.return_value = [
            HumanMessage(content="Hello")
        ]
        
        result = chat_session.force_context_optimization()
        
        assert len(result) == 1
        assert result[0].content == "Hello"
        chat_session.context_optimizer.optimize_context.assert_called_once()
    
    def test_reset_optimization_stats(self, chat_session):
        """Test resetting optimization statistics."""
        chat_session.reset_optimization_stats()
        
        chat_session.context_optimizer.reset_stats.assert_called_once()
        chat_session.summarization_middleware.reset_stats.assert_called_once()
    
    def test_reset_fallback_state(self, chat_session):
        """Test resetting fallback state."""
        chat_session.reset_fallback_state()
        
        chat_session.fallback_manager.reset_fallback_manager.assert_called_once()


class TestLangChainChatSessionTokenUsage:
    """Test token usage and detailed metrics."""
    
    @pytest.fixture
    def chat_session(self, mock_chat_model):
        """Create a LangChainChatSession for testing."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer = Mock()
                    mock_optimizer.calculate_detailed_token_usage.return_value = {
                        "total_tokens": 150,
                        "message_breakdown": []
                    }
                    mock_optimizer_class.return_value = mock_optimizer
                    
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    session = LangChainChatSession(mock_chat_model, session_id=123)
                    session.context_optimizer = mock_optimizer
                    
                    return session
    
    def test_get_token_usage_details(self, chat_session):
        """Test getting detailed token usage information."""
        details = chat_session.get_token_usage_details()
        
        assert details["total_tokens"] == 150
        assert "message_breakdown" in details
        chat_session.context_optimizer.calculate_detailed_token_usage.assert_called_once()


class TestLangChainChatSessionErrorHandling:
    """Test error handling in various scenarios."""
    
    @pytest.fixture
    def chat_session(self, mock_chat_model):
        """Create a LangChainChatSession for testing."""
        with patch('backend.services.langchain_chat_session.ContextOptimizer') as mock_optimizer_class:
            with patch('backend.services.langchain_chat_session.SummarizationMiddleware') as mock_middleware:
                with patch('backend.services.langchain_chat_session.MemoryFallbackManager') as mock_fallback:
                    mock_optimizer_class.return_value = Mock()
                    mock_middleware.return_value = Mock()
                    mock_fallback.return_value = Mock()
                    
                    return LangChainChatSession(mock_chat_model, session_id=123)
    
    def test_convert_database_message_error_handling(self, chat_session):
        """Test error handling in message conversion."""
        # Test malformed message
        malformed_msg = {"invalid": "structure"}
        result = chat_session._convert_database_message_to_langchain(malformed_msg)
        assert result is None
        
        # Test message with exception during processing
        with patch.object(chat_session, 'logger') as mock_logger:
            problematic_msg = {"role": "user", "content": None}  # None content should cause issues
            result = chat_session._convert_database_message_to_langchain(problematic_msg)
            assert result is None
            mock_logger.warning.assert_called()
    
    def test_restore_context_error_handling(self, chat_session):
        """Test error handling during context restoration."""
        # Mock fallback manager to simulate failure
        chat_session.fallback_manager.execute_with_fallback.return_value = False
        
        with patch.object(chat_session, 'logger') as mock_logger:
            chat_session.restore_context([{"role": "user", "content": "test"}])
            mock_logger.warning.assert_called()
    
    def test_optimize_restored_context_error_handling(self, chat_session):
        """Test error handling during context optimization after restoration."""
        # Add some messages
        chat_session.conversation_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        
        # Mock context optimizer to raise exception
        chat_session.context_optimizer.should_optimize_context.side_effect = Exception("Optimization error")
        
        with patch.object(chat_session, 'logger') as mock_logger:
            chat_session._optimize_restored_context()
            mock_logger.warning.assert_called()