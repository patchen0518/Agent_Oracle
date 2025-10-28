"""
Chat service business logic for orchestrating Gemini interactions.

Based on google-genai v1.33.0+ documentation (Context 7 lookup: 2025-01-27)
Implements conversation history processing, context management, and response
formatting following current API standards and best practices.
"""

from typing import List, Optional, Dict, Any
from google.genai import errors
from backend.models.chat_models import ChatMessage, ChatRequest, ChatResponse
from backend.services.gemini_client import GeminiClient, ChatSession
from backend.utils.logging_config import get_logger, log_error_context


class ChatService:
    """
    Service class for managing chat interactions with Gemini API.
    
    Orchestrates conversation flow, manages context, handles response formatting,
    and provides error handling for chat operations. Follows the latest patterns
    from Gemini API conversation management.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite"):
        """
        Initialize the chat service.
        
        Args:
            api_key: Gemini API key. If None, will use environment variable
            model: Model name to use for chat sessions
            
        Raises:
            ValueError: If API key is not provided or invalid
        """
        self.logger = get_logger("chat_service")
        
        try:
            self.gemini_client = GeminiClient(api_key=api_key, model=model)
            self.model = model
            # Store active chat sessions (in production, this would be in a database)
            self._active_sessions: Dict[str, ChatSession] = {}
            
            self.logger.info(f"Chat service initialized with model: {model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize chat service: {e}")
            raise ValueError(f"Chat service initialization failed: {str(e)}")
    
    async def process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """
        Process a chat request and return a response.
        
        Args:
            request: The chat request containing message and history
            
        Returns:
            ChatResponse: The formatted response from Gemini
            
        Raises:
            errors.APIError: If the Gemini API call fails
            ValueError: If the request is invalid
        """
        request_context = {
            "message_length": len(request.message),
            "history_length": len(request.history),
            "model": self.model
        }
        
        self.logger.debug("Processing chat request", extra=request_context)
        
        try:
            # Validate the request
            self._validate_request(request)
            
            # For single-session chat, we create a new session for each request
            # and rebuild the conversation context from the history using latest SDK patterns
            chat_session = self._create_or_get_session(request.history)
            
            # Send the message and get response
            # The chat session now automatically maintains context
            response_text = chat_session.send_message(request.message)
            
            # Format and return the response
            response = ChatResponse(response=response_text)
            
            self.logger.info(
                "Chat request processed successfully", 
                extra={**request_context, "response_length": len(response_text)}
            )
            
            return response
            
        except errors.APIError as e:
            # Log API errors with context
            log_error_context(self.logger, e, request_context)
            
            # Re-raise API errors with enhanced context
            enhanced_error = errors.APIError(f"Gemini API error: {str(e)}", {})
            if hasattr(e, 'code'):
                enhanced_error.code = e.code
            if hasattr(e, 'retry_after'):
                enhanced_error.retry_after = e.retry_after
            raise enhanced_error
            
        except ValueError as e:
            # Log validation errors
            self.logger.warning(f"Request validation failed: {e}", extra=request_context)
            raise e
            
        except Exception as e:
            # Log unexpected errors with full context
            log_error_context(self.logger, e, request_context)
            raise ValueError(f"Unexpected error in chat processing: {str(e)}")
    
    async def process_chat_request_stream(self, request: ChatRequest):
        """
        Process a chat request with streaming response.
        
        Args:
            request: The chat request containing message and history
            
        Yields:
            str: Chunks of the response as they arrive
            
        Raises:
            errors.APIError: If the Gemini API call fails
            ValueError: If the request is invalid
        """
        try:
            # Validate the request
            self._validate_request(request)
            
            # Create or get chat session with history using latest SDK patterns
            chat_session = self._create_or_get_session(request.history)
            
            # Stream the response - the chat session maintains context automatically
            for chunk in chat_session.send_message_stream(request.message):
                yield chunk
                
        except errors.APIError as e:
            new_error = errors.APIError(f"Streaming chat processing failed: {e}", {})
            if hasattr(e, 'code'):
                new_error.code = e.code
            raise new_error
        except Exception as e:
            raise ValueError(f"Unexpected error in streaming chat: {str(e)}")
    
    def _validate_request(self, request: ChatRequest) -> None:
        """
        Validate the chat request with comprehensive error messages.
        
        Args:
            request: The chat request to validate
            
        Raises:
            ValueError: If the request is invalid with specific error details
        """
        # Message validation
        if not request.message:
            raise ValueError("Message is required")
        
        if not request.message.strip():
            raise ValueError("Message cannot be empty or contain only whitespace")
        
        if len(request.message) > 4000:
            raise ValueError(f"Message too long ({len(request.message)} characters). Maximum allowed is 4000 characters.")
        
        # History validation
        if len(request.history) > 100:
            raise ValueError(f"Conversation history too long ({len(request.history)} messages). Maximum allowed is 100 messages.")
        
        # Validate history format
        for i, msg in enumerate(request.history):
            if not isinstance(msg, ChatMessage):
                raise ValueError(f"Invalid message format at history position {i}. Expected ChatMessage object.")
            
            if msg.role not in ["user", "model"]:
                raise ValueError(f"Invalid role '{msg.role}' at history position {i}. Must be 'user' or 'model'.")
            
            if not msg.parts or not msg.parts.strip():
                raise ValueError(f"Empty message content at history position {i}")
            
            if len(msg.parts) > 4000:
                raise ValueError(f"Message at history position {i} too long ({len(msg.parts)} characters)")
        
        self.logger.debug(f"Request validation passed: {len(request.message)} chars, {len(request.history)} history messages")
    
    def _create_or_get_session(self, history: List[ChatMessage]) -> ChatSession:
        """
        Create a new chat session with conversation history using latest SDK patterns.
        
        For single-session chat, we create a fresh session and establish context
        from the provided history. The new SDK automatically manages conversation
        history within the session.
        
        Args:
            history: The conversation history to establish context
            
        Returns:
            ChatSession: A chat session with the conversation context
            
        Raises:
            ValueError: If session creation fails
        """
        session_context = {
            "history_length": len(history),
            "model": self.model
        }
        
        try:
            # Create a new chat session with system instruction
            system_instruction = (
                "You are Oracle, a helpful AI assistant. Provide clear, accurate, and "
                "helpful responses to user questions. Maintain context from the "
                "conversation history and engage in natural, contextual dialogue."
            )
            
            self.logger.debug("Creating chat session", extra=session_context)
            
            # Create chat session with history using the latest SDK patterns
            chat_session = self.gemini_client.create_chat_session(
                system_instruction=system_instruction,
                history=history
            )
            
            self.logger.debug("Chat session created successfully", extra=session_context)
            return chat_session
            
        except errors.APIError as e:
            log_error_context(self.logger, e, session_context)
            raise e  # Re-raise API errors as-is
            
        except Exception as e:
            log_error_context(self.logger, e, session_context)
            raise ValueError(f"Failed to create chat session: {str(e)}")
    

    
    def _format_response(self, response_text: str) -> ChatResponse:
        """
        Format the raw response from Gemini into a structured response.
        
        Args:
            response_text: The raw response text from Gemini
            
        Returns:
            ChatResponse: The formatted response object
        """
        # Clean up the response text
        cleaned_text = response_text.strip()
        
        # Create the response object
        return ChatResponse(response=cleaned_text)
    
    def _handle_conversation_context(self, history: List[ChatMessage]) -> str:
        """
        Process conversation history into context for Gemini API.
        
        Args:
            history: The conversation history
            
        Returns:
            str: Formatted context string for the API
        """
        if not history:
            return ""
        
        # Format recent history for context (last 10 messages)
        recent_history = history[-10:] if len(history) > 10 else history
        
        context_parts = []
        for msg in recent_history:
            role_label = "User" if msg.role == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg.parts}")
        
        return "\n".join(context_parts)
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about active chat sessions.
        
        Returns:
            Dict[str, Any]: Session information
        """
        return {
            "model": self.model,
            "active_sessions": len(self._active_sessions),
            "service_status": "active"
        }