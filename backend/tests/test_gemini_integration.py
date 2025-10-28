"""
Unit tests for Gemini API integration services.

Based on testing standards and pytest best practices.
Tests GeminiClient and ChatService with mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from google.genai import errors
import os

from backend.services.gemini_client import GeminiClient, ChatSession
from backend.services.chat_service import ChatService
from backend.models.chat_models import ChatMessage, ChatRequest, ChatResponse


class TestGeminiClient:
    """Test GeminiClient functionality with mocked API responses."""
    
    def test_init_with_api_key(self):
        """Test client initialization with explicit API key."""
        with patch('backend.services.gemini_client.genai.Client') as mock_client:
            client = GeminiClient(api_key="test-key")
            assert client.model == "gemini-2.5-flash-lite"
            mock_client.assert_called_once_with(api_key="test-key")
    
    def test_init_with_env_var(self):
        """Test client initialization using environment variable."""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'env-key'}):
            with patch('backend.services.gemini_client.genai.Client') as mock_client:
                client = GeminiClient()
                mock_client.assert_called_once_with(api_key="env-key")
    
    def test_init_no_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                GeminiClient()
            assert "Gemini API key is required" in str(exc_info.value)
    
    def test_init_client_failure_raises_error(self):
        """Test that client initialization failure is handled."""
        with patch('backend.services.gemini_client.genai.Client', side_effect=Exception("Client error")):
            with pytest.raises(ValueError) as exc_info:
                GeminiClient(api_key="test-key")
            assert "Failed to initialize Gemini client" in str(exc_info.value)
    
    def test_create_chat_session_success(self):
        """Test successful chat session creation."""
        mock_client = Mock()
        mock_chat = Mock()
        mock_client.chats.create.return_value = mock_chat
        
        with patch('backend.services.gemini_client.genai.Client', return_value=mock_client):
            client = GeminiClient(api_key="test-key")
            session = client.create_chat_session()
            
            assert isinstance(session, ChatSession)
            mock_client.chats.create.assert_called_once()
    
    def test_create_chat_session_with_system_instruction(self):
        """Test chat session creation with system instruction."""
        mock_client = Mock()
        mock_chat = Mock()
        mock_client.chats.create.return_value = mock_chat
        
        with patch('backend.services.gemini_client.genai.Client', return_value=mock_client):
            with patch('backend.services.gemini_client.types') as mock_types:
                client = GeminiClient(api_key="test-key")
                session = client.create_chat_session("You are a helpful assistant")
                
                mock_types.GenerateContentConfig.assert_called_once()
                mock_client.chats.create.assert_called_once()
    
    def test_create_chat_session_api_error(self):
        """Test chat session creation with API error."""
        mock_client = Mock()
        api_error = errors.APIError("API Error", {})
        api_error.code = 404
        mock_client.chats.create.side_effect = api_error
        
        with patch('backend.services.gemini_client.genai.Client', return_value=mock_client):
            client = GeminiClient(api_key="test-key")
            
            with pytest.raises(errors.APIError):
                client.create_chat_session()
    
    def test_handle_api_error_with_known_codes(self):
        """Test API error handling with known error codes."""
        client = GeminiClient(api_key="test-key")
        
        # Test 404 error
        error_404 = errors.APIError("Not found", {})
        error_404.code = 404
        enhanced_error = client._handle_api_error(error_404)
        assert "Model not found" in str(enhanced_error)
        
        # Test 429 error
        error_429 = errors.APIError("Rate limited", {})
        error_429.code = 429
        enhanced_error = client._handle_api_error(error_429)
        assert "Rate limit exceeded" in str(enhanced_error)


class TestChatSession:
    """Test ChatSession functionality with mocked responses."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_chat = Mock()
        self.session = ChatSession(self.mock_chat)
    
    def test_send_message_success(self):
        """Test successful message sending."""
        mock_response = Mock()
        mock_response.text = "Hello! How can I help you?"
        self.mock_chat.send_message.return_value = mock_response
        
        response = self.session.send_message("Hello")
        
        assert response == "Hello! How can I help you?"
        self.mock_chat.send_message.assert_called_once_with("Hello")
    
    def test_send_message_api_error(self):
        """Test message sending with API error."""
        api_error = errors.APIError("API Error", {})
        api_error.code = 500
        self.mock_chat.send_message.side_effect = api_error
        
        with pytest.raises(errors.APIError):
            self.session.send_message("Hello")
    
    def test_send_message_stream_success(self):
        """Test successful streaming message."""
        mock_chunks = [Mock(), Mock(), Mock()]
        mock_chunks[0].text = "Hello"
        mock_chunks[1].text = " there"
        mock_chunks[2].text = "!"
        
        self.mock_chat.send_message_stream.return_value = iter(mock_chunks)
        
        chunks = list(self.session.send_message_stream("Hello"))
        
        assert chunks == ["Hello", " there", "!"]
        self.mock_chat.send_message_stream.assert_called_once_with("Hello")
    
    def test_send_message_stream_api_error(self):
        """Test streaming message with API error."""
        api_error = errors.APIError("Stream error", {})
        api_error.code = 500
        self.mock_chat.send_message_stream.side_effect = api_error
        
        with pytest.raises(errors.APIError):
            list(self.session.send_message_stream("Hello"))
    
    def test_get_history_success(self):
        """Test successful history retrieval."""
        mock_message1 = Mock()
        mock_message1.role = "user"
        mock_message1.parts = [Mock()]
        mock_message1.parts[0].text = "Hello"
        
        mock_message2 = Mock()
        mock_message2.role = "model"
        mock_message2.parts = [Mock()]
        mock_message2.parts[0].text = "Hi there!"
        
        self.mock_chat.get_history.return_value = [mock_message1, mock_message2]
        
        history = self.session.get_history()
        
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].parts == "Hello"
        assert history[1].role == "model"
        assert history[1].parts == "Hi there!"
    
    def test_get_history_failure_returns_empty(self):
        """Test that history retrieval failure returns empty list."""
        self.mock_chat.get_history.side_effect = Exception("History error")
        
        history = self.session.get_history()
        
        assert history == []


class TestChatService:
    """Test ChatService business logic with mocked dependencies."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('backend.services.chat_service.GeminiClient'):
            self.service = ChatService(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_process_chat_request_success(self):
        """Test successful chat request processing."""
        # Mock the chat session and response
        mock_session = Mock()
        mock_session.send_message.return_value = "Hello! How can I help you?"
        
        with patch.object(self.service, '_create_or_get_session', return_value=mock_session):
            request = ChatRequest(message="Hello", history=[])
            response = await self.service.process_chat_request(request)
            
            assert isinstance(response, ChatResponse)
            assert response.response == "Hello! How can I help you?"
    
    @pytest.mark.asyncio
    async def test_process_chat_request_with_history(self):
        """Test chat request processing with conversation history."""
        mock_session = Mock()
        mock_session.send_message.return_value = "Based on our previous conversation..."
        
        history = [
            ChatMessage(role="user", parts="Hi"),
            ChatMessage(role="model", parts="Hello!")
        ]
        
        with patch.object(self.service, '_create_or_get_session', return_value=mock_session):
            request = ChatRequest(message="Continue our chat", history=history)
            response = await self.service.process_chat_request(request)
            
            assert response.response == "Based on our previous conversation..."
    
    @pytest.mark.asyncio
    async def test_process_chat_request_api_error(self):
        """Test chat request processing with API error."""
        mock_session = Mock()
        api_error = errors.APIError("Gemini API error", {})
        mock_session.send_message.side_effect = api_error
        
        with patch.object(self.service, '_create_or_get_session', return_value=mock_session):
            request = ChatRequest(message="Hello", history=[])
            
            with pytest.raises(errors.APIError) as exc_info:
                await self.service.process_chat_request(request)
            
            assert "Chat processing failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_chat_request_stream_success(self):
        """Test successful streaming chat request processing."""
        mock_session = Mock()
        mock_session.send_message_stream.return_value = iter(["Hello", " there", "!"])
        
        with patch.object(self.service, '_create_or_get_session', return_value=mock_session):
            request = ChatRequest(message="Hello", history=[])
            
            chunks = []
            async for chunk in self.service.process_chat_request_stream(request):
                chunks.append(chunk)
            
            assert chunks == ["Hello", " there", "!"]
    
    def test_validate_request_success(self):
        """Test successful request validation."""
        request = ChatRequest(message="Hello", history=[])
        # Should not raise any exception
        self.service._validate_request(request)
    
    def test_validate_request_empty_message(self):
        """Test validation failure for empty message."""
        # Create a mock request with empty message to bypass Pydantic validation
        request = Mock()
        request.message = ""
        request.history = []
        
        with pytest.raises(ValueError) as exc_info:
            self.service._validate_request(request)
        
        assert "Message cannot be empty" in str(exc_info.value)
    
    def test_validate_request_message_too_long(self):
        """Test validation failure for overly long message."""
        # Create a mock request with long message to bypass Pydantic validation
        request = Mock()
        request.message = "x" * 4001
        request.history = []
        
        with pytest.raises(ValueError) as exc_info:
            self.service._validate_request(request)
        
        assert "Message too long" in str(exc_info.value)
    
    def test_validate_request_history_too_long(self):
        """Test validation failure for overly long history."""
        # Create a mock request with long history to bypass Pydantic validation
        request = Mock()
        request.message = "Hello"
        request.history = [Mock() for _ in range(101)]
        
        with pytest.raises(ValueError) as exc_info:
            self.service._validate_request(request)
        
        assert "Conversation history too long" in str(exc_info.value)
    
    def test_validate_request_invalid_role(self):
        """Test validation failure for invalid message role."""
        # Create a mock message with invalid role
        invalid_message = Mock()
        invalid_message.role = "invalid"
        invalid_message.parts = "Hello"
        
        # Create a mock request to bypass Pydantic validation
        request = Mock()
        request.message = "Hello"
        request.history = [invalid_message]
        
        with pytest.raises(ValueError) as exc_info:
            self.service._validate_request(request)
        
        assert "Invalid message format" in str(exc_info.value)
    
    def test_create_or_get_session_success(self):
        """Test successful session creation."""
        mock_session = Mock()
        self.service.gemini_client.create_chat_session.return_value = mock_session
        
        history = [ChatMessage(role="user", parts="Hi")]
        session = self.service._create_or_get_session(history)
        
        assert session == mock_session
        self.service.gemini_client.create_chat_session.assert_called_once()
    
    def test_create_or_get_session_failure(self):
        """Test session creation failure."""
        self.service.gemini_client.create_chat_session.side_effect = Exception("Session error")
        
        with pytest.raises(ValueError) as exc_info:
            self.service._create_or_get_session([])
        
        assert "Failed to create chat session" in str(exc_info.value)
    
    def test_get_session_info(self):
        """Test session information retrieval."""
        info = self.service.get_session_info()
        
        assert info["model"] == "gemini-2.5-flash"
        assert info["active_sessions"] == 0
        assert info["service_status"] == "active"
    
    def test_handle_conversation_context_empty_history(self):
        """Test context handling with empty history."""
        context = self.service._handle_conversation_context([])
        assert context == ""
    
    def test_handle_conversation_context_with_history(self):
        """Test context handling with conversation history."""
        history = [
            ChatMessage(role="user", parts="Hello"),
            ChatMessage(role="model", parts="Hi there!")
        ]
        
        context = self.service._handle_conversation_context(history)
        
        assert "User: Hello" in context
        assert "Assistant: Hi there!" in context
    
    def test_handle_conversation_context_long_history(self):
        """Test context handling with long history (should limit to 10)."""
        history = [
            ChatMessage(role="user", parts=f"Message {i}")
            for i in range(15)
        ]
        
        context = self.service._handle_conversation_context(history)
        
        # Should only include last 10 messages
        lines = context.split('\n')
        assert len(lines) == 10
        assert "Message 14" in context  # Last message should be included
        assert "Message 4" not in context  # Early messages should be excluded