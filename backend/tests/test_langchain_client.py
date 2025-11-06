"""
Unit tests for LangChain client components.

Tests LangChainClient initialization and session management,
LangChainChatSession message handling and conversation flow,
and system instruction processing and personality configuration.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from backend.services.langchain_client import LangChainClient
from backend.exceptions import (
    ConfigurationError,
    ModelInitializationError,
    LangChainError,
    AIServiceError
)


class TestLangChainClientInitialization:
    """Test LangChainClient initialization and configuration."""
    
    def test_initialization_with_api_key_parameter(self):
        """Test initialization with API key provided as parameter."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            
            client = LangChainClient(api_key="test-key", model="gemini-2.5-flash")
            
            assert client.api_key == "test-key"
            assert client.model == "gemini-2.5-flash"
            assert client.active_sessions == {}
            assert client.session_timeout == 3600
            assert client.max_sessions == 50
            
            mock_chat.assert_called_once_with(
                model="gemini-2.5-flash",
                google_api_key="test-key",
                temperature=0.7,
                convert_system_message_to_human=True
            )
    
    def test_initialization_with_environment_variables(self):
        """Test initialization using environment variables."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY': 'env-key',
            'GEMINI_MODEL': 'gemini-pro'
        }):
            with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
                mock_chat.return_value = Mock()
                
                client = LangChainClient()
                
                assert client.api_key == "env-key"
                assert client.model == "gemini-pro"
                
                mock_chat.assert_called_once_with(
                    model="gemini-pro",
                    google_api_key="env-key",
                    temperature=0.7,
                    convert_system_message_to_human=True
                )
    
    def test_initialization_with_google_api_key_fallback(self):
        """Test initialization falls back to GOOGLE_API_KEY environment variable."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'google-key'}, clear=True):
            with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
                mock_chat.return_value = Mock()
                
                client = LangChainClient()
                
                assert client.api_key == "google-key"
                assert client.model == "gemini-2.5-flash"  # Default model
    
    def test_initialization_no_api_key_raises_error(self):
        """Test initialization without API key raises ConfigurationError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="Google API key is required"):
                LangChainClient()
    
    def test_initialization_chat_model_failure_raises_error(self):
        """Test initialization failure of ChatGoogleGenerativeAI raises ModelInitializationError."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.side_effect = Exception("Model initialization failed")
            
            with pytest.raises(ModelInitializationError, match="Failed to initialize ChatGoogleGenerativeAI"):
                LangChainClient(api_key="test-key")
    
    def test_initialization_statistics_tracking(self):
        """Test that initialization properly sets up statistics tracking."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            
            client = LangChainClient(api_key="test-key")
            
            assert client.sessions_created == 0
            assert client.sessions_cleaned == 0
            assert isinstance(client.last_cleanup, datetime)


class TestLangChainClientSessionManagement:
    """Test session management functionality."""
    
    @pytest.fixture
    def mock_langchain_client(self):
        """Create a mock LangChainClient for testing."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            client = LangChainClient(api_key="test-key")
            return client
    
    @pytest.fixture
    def mock_chat_session(self):
        """Create a mock LangChainChatSession."""
        mock_session = Mock()
        mock_session.send_message.return_value = "Test response"
        mock_session.get_message_count.return_value = 0
        return mock_session
    
    def test_get_or_create_session_new_session(self, mock_langchain_client, mock_chat_session):
        """Test creating a new session when none exists."""
        with patch('backend.services.langchain_client.LangChainChatSession') as mock_session_class:
            with patch('backend.services.langchain_client.ContextOptimizer') as mock_optimizer:
                mock_session_class.return_value = mock_chat_session
                mock_optimizer.return_value = Mock()
                
                result = mock_langchain_client.get_or_create_session(123, "test instruction")
                
                assert result == mock_chat_session
                assert 123 in mock_langchain_client.active_sessions
                assert mock_langchain_client.sessions_created == 1
                
                mock_session_class.assert_called_once()
    
    def test_get_or_create_session_existing_session(self, mock_langchain_client, mock_chat_session):
        """Test retrieving an existing session from cache."""
        # Pre-populate cache
        mock_langchain_client.active_sessions[123] = mock_chat_session
        
        result = mock_langchain_client.get_or_create_session(123, "test instruction")
        
        assert result == mock_chat_session
        assert mock_langchain_client.sessions_created == 0  # No new session created
    
    def test_get_or_create_session_with_recent_messages(self, mock_langchain_client, mock_chat_session):
        """Test creating session with recent message context restoration."""
        recent_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        with patch('backend.services.langchain_client.LangChainChatSession') as mock_session_class:
            with patch('backend.services.langchain_client.ContextOptimizer') as mock_optimizer:
                mock_session_class.return_value = mock_chat_session
                mock_optimizer.return_value = Mock()
                
                result = mock_langchain_client.get_or_create_session(
                    123, "test instruction", recent_messages
                )
                
                assert result == mock_chat_session
                mock_chat_session.restore_context.assert_called_once_with(recent_messages)
    
    def test_remove_session_existing(self, mock_langchain_client, mock_chat_session):
        """Test removing an existing session."""
        mock_langchain_client.active_sessions[123] = mock_chat_session
        
        result = mock_langchain_client.remove_session(123)
        
        assert result is True
        assert 123 not in mock_langchain_client.active_sessions
    
    def test_remove_session_nonexistent(self, mock_langchain_client):
        """Test removing a non-existent session."""
        result = mock_langchain_client.remove_session(999)
        
        assert result is False
    
    def test_get_session_stats(self, mock_langchain_client, mock_chat_session):
        """Test getting session statistics."""
        mock_langchain_client.active_sessions[123] = mock_chat_session
        mock_langchain_client.sessions_created = 5
        mock_langchain_client.sessions_cleaned = 2
        
        stats = mock_langchain_client.get_session_stats()
        
        assert stats["active_sessions"] == 1
        assert stats["sessions_created"] == 5
        assert stats["sessions_cleaned"] == 2
        assert stats["max_sessions"] == 50
    
    def test_create_chat_session_standalone(self, mock_langchain_client):
        """Test creating a standalone chat session."""
        with patch('backend.services.langchain_client.LangChainChatSession') as mock_session_class:
            with patch('backend.services.langchain_client.ContextOptimizer') as mock_optimizer:
                mock_session = Mock()
                mock_session_class.return_value = mock_session
                mock_optimizer.return_value = Mock()
                
                result = mock_langchain_client.create_chat_session("test instruction")
                
                assert result == mock_session
                mock_session_class.assert_called_once()
                # Verify session_id is None for standalone session
                call_args = mock_session_class.call_args
                assert call_args[1]['session_id'] is None
    
    def test_cleanup_sessions_when_max_exceeded(self, mock_langchain_client):
        """Test session cleanup when maximum sessions exceeded."""
        # Fill cache beyond max_sessions
        for i in range(mock_langchain_client.max_sessions + 5):
            mock_langchain_client.active_sessions[i] = Mock()
        
        mock_langchain_client._cleanup_sessions()
        
        assert len(mock_langchain_client.active_sessions) < mock_langchain_client.max_sessions
        assert mock_langchain_client.sessions_cleaned > 0
    
    def test_cleanup_if_needed_triggers_cleanup(self, mock_langchain_client):
        """Test that cleanup is triggered when needed."""
        # Set last cleanup to old time
        mock_langchain_client.last_cleanup = datetime.now() - timedelta(seconds=400)
        
        with patch.object(mock_langchain_client, '_cleanup_sessions') as mock_cleanup:
            mock_langchain_client._cleanup_if_needed()
            mock_cleanup.assert_called_once()


class TestLangChainClientSystemInstructions:
    """Test system instruction processing and validation."""
    
    @pytest.fixture
    def mock_langchain_client(self):
        """Create a mock LangChainClient for testing."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            client = LangChainClient(api_key="test-key")
            return client
    
    def test_validate_system_instruction_direct_text(self, mock_langchain_client):
        """Test validation of direct system instruction text."""
        instruction = "You are a helpful assistant."
        
        result = mock_langchain_client.validate_system_instruction(instruction)
        
        assert result == instruction
    
    def test_validate_system_instruction_type_name(self, mock_langchain_client):
        """Test validation of system instruction type name."""
        with patch('backend.services.langchain_client.get_system_instruction') as mock_get:
            with patch('backend.services.langchain_client.list_available_instructions') as mock_list:
                mock_list.return_value = {"helpful": "Helpful assistant"}
                mock_get.return_value = "You are a helpful assistant."
                
                result = mock_langchain_client.validate_system_instruction("helpful")
                
                assert result == "You are a helpful assistant."
                mock_get.assert_called_once_with("helpful")
    
    def test_validate_system_instruction_empty(self, mock_langchain_client):
        """Test validation of empty system instruction."""
        result = mock_langchain_client.validate_system_instruction("")
        assert result == ""
        
        result = mock_langchain_client.validate_system_instruction("   ")
        assert result == ""
    
    def test_get_available_instruction_types(self, mock_langchain_client):
        """Test getting available system instruction types."""
        with patch('backend.services.langchain_client.list_available_instructions') as mock_list:
            mock_list.return_value = {
                "helpful": "Helpful assistant",
                "creative": "Creative assistant"
            }
            
            result = mock_langchain_client.get_available_instruction_types()
            
            assert result == {
                "helpful": "Helpful assistant",
                "creative": "Creative assistant"
            }


class TestLangChainClientMemoryDatabaseSync:
    """Test memory-database synchronization functionality."""
    
    @pytest.fixture
    def mock_langchain_client(self):
        """Create a mock LangChainClient for testing."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            client = LangChainClient(api_key="test-key")
            return client
    
    @pytest.fixture
    def mock_chat_session(self):
        """Create a mock LangChainChatSession with memory methods."""
        mock_session = Mock()
        mock_session.clear_history.return_value = None
        mock_session.restore_context.return_value = None
        mock_session.has_system_instruction.return_value = True
        mock_session.get_system_instruction.return_value = "Test instruction"
        mock_session._process_system_instruction.return_value = None
        mock_session.get_message_count.return_value = 5
        return mock_session
    
    def test_sync_session_with_database_success(self, mock_langchain_client, mock_chat_session):
        """Test successful session synchronization with database."""
        mock_langchain_client.active_sessions[123] = mock_chat_session
        recent_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        result = mock_langchain_client.sync_session_with_database(123, recent_messages)
        
        assert result is True
        mock_chat_session.clear_history.assert_called_once()
        mock_chat_session.restore_context.assert_called_once_with(recent_messages)
    
    def test_sync_session_with_database_no_active_session(self, mock_langchain_client):
        """Test synchronization when no active session exists."""
        result = mock_langchain_client.sync_session_with_database(999, [])
        
        assert result is True  # Should succeed gracefully
    
    def test_sync_session_with_database_error_handling(self, mock_langchain_client, mock_chat_session):
        """Test error handling during synchronization."""
        mock_langchain_client.active_sessions[123] = mock_chat_session
        mock_chat_session.clear_history.side_effect = Exception("Sync error")
        
        result = mock_langchain_client.sync_session_with_database(123, [])
        
        assert result is False
    
    def test_get_memory_database_stats(self, mock_langchain_client, mock_chat_session):
        """Test getting memory-database coordination statistics."""
        # Setup mock sessions with different states
        mock_chat_session.get_message_count.return_value = 5
        mock_chat_session.get_optimization_stats.return_value = {
            "optimizer": {
                "optimizations_performed": 3,
                "tokens_saved": 150
            }
        }
        
        mock_langchain_client.active_sessions[123] = mock_chat_session
        mock_langchain_client.active_sessions[456] = Mock()
        mock_langchain_client.active_sessions[456].get_message_count.return_value = 0
        
        stats = mock_langchain_client.get_memory_database_stats()
        
        assert stats["total_active_sessions"] == 2
        assert stats["sessions_with_memory"] == 1
        assert stats["total_memory_messages"] == 5
        assert stats["sessions_with_optimization"] == 1
        assert stats["optimization_stats"]["total_optimizations"] == 3
        assert stats["optimization_stats"]["total_tokens_saved"] == 150


class TestLangChainClientErrorHandling:
    """Test error handling and exception mapping."""
    
    def test_session_creation_langchain_exception(self):
        """Test handling of LangChain exceptions during session creation."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            client = LangChainClient(api_key="test-key")
            
            with patch('backend.services.langchain_client.LangChainChatSession') as mock_session_class:
                from langchain_core.exceptions import LangChainException
                mock_session_class.side_effect = LangChainException("LangChain error")
                
                with pytest.raises(LangChainError):
                    client.get_or_create_session(123, "test instruction")
    
    def test_session_creation_generic_exception(self):
        """Test handling of generic exceptions during session creation."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            client = LangChainClient(api_key="test-key")
            
            with patch('backend.services.langchain_client.LangChainChatSession') as mock_session_class:
                mock_session_class.side_effect = Exception("Generic error")
                
                with pytest.raises(AIServiceError):
                    client.get_or_create_session(123, "test instruction")
    
    def test_standalone_session_creation_error(self):
        """Test error handling in standalone session creation."""
        with patch('backend.services.langchain_client.ChatGoogleGenerativeAI') as mock_chat:
            mock_chat.return_value = Mock()
            client = LangChainClient(api_key="test-key")
            
            with patch('backend.services.langchain_client.LangChainChatSession') as mock_session_class:
                mock_session_class.side_effect = Exception("Session creation failed")
                
                with pytest.raises(AIServiceError):
                    client.create_chat_session("test instruction")