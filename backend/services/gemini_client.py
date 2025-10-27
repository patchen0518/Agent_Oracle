"""
Gemini API client wrapper for Google Generative AI integration.

Based on google-genai v1.33.0+ documentation (Context 7 lookup: 2025-01-27)
Implements chat session management, error handling, and API key configuration
following current best practices from googleapis/python-genai.
"""

import os
from typing import List, Optional
from google import genai
from google.genai import errors, types
from backend.models.chat_models import ChatMessage


class GeminiClient:
    """
    Wrapper class for Google Generative AI client.
    
    Handles API key configuration, chat session management, and error handling
    for Gemini API interactions. Follows the latest patterns from the official
    google-genai Python SDK.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite"):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Gemini API key. If None, will use GEMINI_API_KEY or GOOGLE_API_KEY env var
            model: Model name to use for chat sessions
            
        Raises:
            ValueError: If no API key is provided or found in environment
        """
        self.model = model
        
        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        # Initialize client following latest documentation patterns
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini client: {str(e)}")
    
    def create_chat_session(self, system_instruction: Optional[str] = None) -> "ChatSession":
        """
        Create a new chat session.
        
        Args:
            system_instruction: Optional system instruction for the chat session
            
        Returns:
            ChatSession: A new chat session instance
            
        Raises:
            errors.APIError: If chat session creation fails
        """
        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(
                    temperature=0.7,
                    system_instruction=system_instruction
                )
            
            chat = self.client.chats.create(
                model=self.model,
                config=config
            )
            
            return ChatSession(chat)
            
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise errors.APIError(f"Failed to create chat session: {str(e)}")
    
    def _handle_api_error(self, error: errors.APIError) -> errors.APIError:
        """
        Handle and enrich API errors with specific messages.
        
        Args:
            error: The original API error
            
        Returns:
            errors.APIError: Enhanced error with specific messaging
        """
        error_messages = {
            404: "Model not found or invalid model name",
            429: "Rate limit exceeded. Please try again later",
            400: "Invalid request format or parameters",
            401: "Invalid API key or authentication failed",
            403: "Access forbidden. Check API key permissions",
            500: "Internal server error. Please try again later"
        }
        
        specific_message = error_messages.get(error.code, "Unknown API error")
        enhanced_message = f"{specific_message}. Original error: {error.message}"
        
        # Create new error with enhanced message but preserve original code
        new_error = errors.APIError(enhanced_message, {})
        new_error.code = error.code
        return new_error


class ChatSession:
    """
    Wrapper for Gemini chat session with conversation management.
    
    Provides methods for sending messages, managing history, and handling
    responses following the latest Gemini API patterns.
    """
    
    def __init__(self, chat_session):
        """
        Initialize chat session wrapper.
        
        Args:
            chat_session: The underlying Gemini chat session object
        """
        self.chat = chat_session
    
    def send_message(self, message: str, history: Optional[List[ChatMessage]] = None) -> str:
        """
        Send a message to the chat session.
        
        Args:
            message: The user message to send
            history: Optional conversation history for context
            
        Returns:
            str: The model's response text
            
        Raises:
            errors.APIError: If the API call fails
        """
        try:
            # If history is provided, we need to rebuild the conversation context
            # Note: The current google-genai SDK manages history automatically
            # within a chat session, so we send the message directly
            response = self.chat.send_message(message)
            return response.text
            
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise ValueError(f"Failed to send message: {str(e)}")
    
    def send_message_stream(self, message: str, history: Optional[List[ChatMessage]] = None):
        """
        Send a message and get streaming response.
        
        Args:
            message: The user message to send
            history: Optional conversation history for context
            
        Yields:
            str: Chunks of the model's response as they arrive
            
        Raises:
            errors.APIError: If the API call fails
        """
        try:
            for chunk in self.chat.send_message_stream(message):
                yield chunk.text
                
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise ValueError(f"Failed to send streaming message: {str(e)}")
    
    def get_history(self) -> List[ChatMessage]:
        """
        Get the conversation history from the chat session.
        
        Returns:
            List[ChatMessage]: List of messages in the conversation
        """
        try:
            history = self.chat.get_history()
            chat_messages = []
            
            for message in history:
                # Convert Gemini message format to our ChatMessage model
                chat_message = ChatMessage(
                    role=message.role,
                    parts=message.parts[0].text if message.parts else ""
                )
                chat_messages.append(chat_message)
            
            return chat_messages
            
        except Exception as e:
            # Return empty history if retrieval fails
            return []
    
    def _handle_api_error(self, error: errors.APIError) -> errors.APIError:
        """
        Handle and enrich API errors with specific messages.
        
        Args:
            error: The original API error
            
        Returns:
            errors.APIError: Enhanced error with specific messaging
        """
        error_messages = {
            404: "Model not found or invalid model name",
            429: "Rate limit exceeded. Please try again later",
            400: "Invalid request format or parameters",
            401: "Invalid API key or authentication failed",
            403: "Access forbidden. Check API key permissions",
            500: "Internal server error. Please try again later"
        }
        
        specific_message = error_messages.get(error.code, "Unknown API error")
        enhanced_message = f"{specific_message}. Original error: {error.message}"
        
        new_error = errors.APIError(enhanced_message, {})
        new_error.code = error.code
        return new_error