"""
Chat service business logic for orchestrating Gemini interactions.

Based on google-genai v1.33.0+ documentation (Context 7 lookup: 2025-01-27)
Implements conversation history processing, context management, and response
formatting following current API standards and best practices.
"""

import os
from typing import List, Optional, Dict, Any
from google.genai import errors, types
from backend.models.chat_models import ChatMessage, ChatRequest, ChatResponse
from backend.services.gemini_client import GeminiClient, ChatSession
from backend.utils.logging_config import get_logger, log_error_context
from backend.config.system_instructions import get_system_instruction


class ChatService:
    """
    Service class for managing chat interactions with Gemini API.
    
    Orchestrates conversation flow, manages context, handles response formatting,
    and provides error handling for chat operations. Follows the latest patterns
    from Gemini API conversation management.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the chat service.
        
        Args:
            api_key: Gemini API key. If None, will use environment variable
            model: Model name to use for chat sessions. If None, will use GEMINI_MODEL env var or default to "gemini-2.5-flash"
            
        Raises:
            ValueError: If API key is not provided or invalid
        """
        self.logger = get_logger("chat_service")
        
        # Get model from parameter or environment, with fallback to default
        if model is None:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
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
        Process a chat request and return a response using stateless conversation approach.
        
        This method uses the generate_content API with full conversation history
        to maintain context across requests without persistent chat sessions.
        
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
            
            # Get system instruction
            system_instruction = get_system_instruction()
            
            # Build conversation contents including history + current message
            contents = self._build_conversation_contents(request.history, request.message)
            
            # Generate response using stateless approach
            response = self.gemini_client.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    system_instruction=system_instruction
                )
            )
            
            response_text = response.text
            
            # Format and return the response
            chat_response = ChatResponse(response=response_text)
            
            self.logger.info(
                "Chat request processed successfully", 
                extra={**request_context, "response_length": len(response_text)}
            )
            
            return chat_response
            
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
        Process a chat request with streaming response using stateless approach.
        
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
            
            # Get system instruction
            system_instruction = get_system_instruction()
            
            # Build conversation contents including history + current message
            contents = self._build_conversation_contents(request.history, request.message)
            
            # Stream response using stateless approach
            for chunk in self.gemini_client.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    system_instruction=system_instruction
                )
            ):
                yield chunk.text
                
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
    
    
    def _build_conversation_contents(self, history: List[ChatMessage], current_message: str) -> List[types.Content]:
        """
        Build conversation contents for stateless Gemini API call.
        
        Converts conversation history and current message into the format expected
        by the generate_content API, maintaining proper conversation flow.
        
        Args:
            history: Previous conversation messages
            current_message: The current user message
            
        Returns:
            List[types.Content]: Formatted conversation contents
        """
        contents = []
        
        # Add conversation history
        for msg in history:
            content = types.Content(
                role=msg.role,  # 'user' or 'model'
                parts=[types.Part.from_text(text=msg.parts)]
            )
            contents.append(content)
        
        # Add current user message
        current_content = types.Content(
            role='user',
            parts=[types.Part.from_text(text=current_message)]
        )
        contents.append(current_content)
        
        return contents
    
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