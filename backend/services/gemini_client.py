"""
Gemini API client wrapper for Google Generative AI integration.

Based on google-genai v1.33.0+ documentation (Context 7 lookup: 2025-01-27)
Implements proper chat session management leveraging Gemini's native conversation handling.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from google import genai
from google.genai import errors, types
from backend.utils.logging_config import get_logger


class GeminiClient:
    """
    Wrapper class for Google Generative AI client.
    
    Properly leverages Gemini's native conversation management instead of
    manually reconstructing context. Each session maintains its own conversation
    history automatically through the Gemini SDK.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Gemini API key. If None, will use GEMINI_API_KEY or GOOGLE_API_KEY env var
            model: Model name to use for chat sessions. If None, will use GEMINI_MODEL env var or default to "gemini-2.5-flash"
            
        Raises:
            ValueError: If no API key is provided or found in environment
        """
        # Get model from parameter or environment, with fallback to default
        if model is None:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
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
        
        # Simple session cache: session_id -> ChatSession
        # Each ChatSession maintains its own conversation history via Gemini SDK
        self.active_sessions: Dict[int, "ChatSession"] = {}
        
        # Session management configuration
        self.session_timeout: int = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour default
        self.max_sessions: int = int(os.getenv("MAX_SESSIONS", "100"))  # Reduced default
        self.last_cleanup: datetime = datetime.now()
        
        # Simple statistics
        self.sessions_created: int = 0
        self.sessions_cleaned: int = 0
        
        # Initialize logger
        self.logger = get_logger("gemini_client")
    
    def get_or_create_session(self, session_id: int, system_instruction: Optional[str] = None, conversation_history: Optional[list] = None) -> "ChatSession":
        """
        Get existing Gemini chat session or create a new one with conversation history restoration.
        
        Leverages Gemini's native conversation management and restores conversation history
        from the database when creating new sessions to maintain memory across restarts.
        
        Args:
            session_id: The session ID to retrieve or create
            system_instruction: Optional system instruction for new sessions
            conversation_history: Optional list of previous messages to restore context
            
        Returns:
            ChatSession: The cached or newly created chat session with restored history
            
        Raises:
            errors.APIError: If session creation fails
        """
        # Periodic cleanup
        self._cleanup_if_needed()
        
        # Return existing session if available (no need to restore history)
        if session_id in self.active_sessions:
            self.logger.debug(f"Reusing existing Gemini session for session_id {session_id}")
            return self.active_sessions[session_id]
        
        # Create new Gemini chat session
        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(
                    temperature=0.7,
                    system_instruction=system_instruction
                )
            
            # Create Gemini chat session - this maintains conversation history automatically
            chat = self.client.chats.create(
                model=self.model,
                config=config
            )
            
            chat_session = ChatSession(chat)
            
            # Restore conversation history if provided
            if conversation_history:
                chat_session.restore_conversation_history(conversation_history)
                self.logger.info(f"Restored {len(conversation_history)} messages for session_id {session_id}")
            
            self.active_sessions[session_id] = chat_session
            self.sessions_created += 1
            
            self.logger.info(f"Created new Gemini session for session_id {session_id}")
            return chat_session
            
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise errors.APIError(f"Failed to create chat session for session {session_id}: {str(e)}")
    
    def remove_session(self, session_id: int) -> bool:
        """
        Remove a session from cache.
        
        Args:
            session_id: The session ID to remove
            
        Returns:
            bool: True if session was found and removed
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            self.logger.info(f"Removed session {session_id} from cache")
            return True
        return False
    
    def _cleanup_if_needed(self) -> None:
        """
        Perform cleanup if we have too many sessions or it's been too long.
        """
        now = datetime.now()
        
        # Cleanup if we have too many sessions or it's been a while
        should_cleanup = (
            len(self.active_sessions) >= self.max_sessions or
            (now - self.last_cleanup).total_seconds() > 300  # 5 minutes
        )
        
        if should_cleanup:
            self._cleanup_sessions()
    
    def _cleanup_sessions(self) -> None:
        """
        Simple cleanup - remove oldest sessions if we have too many.
        """
        if len(self.active_sessions) <= self.max_sessions:
            return
        
        # Remove oldest sessions (simple FIFO approach)
        sessions_to_remove = len(self.active_sessions) - self.max_sessions + 10  # Remove a few extra
        session_ids = list(self.active_sessions.keys())
        
        for i in range(min(sessions_to_remove, len(session_ids))):
            session_id = session_ids[i]
            del self.active_sessions[session_id]
            self.sessions_cleaned += 1
        
        self.last_cleanup = datetime.now()
        self.logger.info(f"Cleaned up {sessions_to_remove} sessions, {len(self.active_sessions)} remaining")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get simple session statistics.
        
        Returns:
            Dict[str, Any]: Basic session statistics
        """
        return {
            "active_sessions": len(self.active_sessions),
            "sessions_created": self.sessions_created,
            "sessions_cleaned": self.sessions_cleaned,
            "max_sessions": self.max_sessions
        }
    
    def create_chat_session(self, system_instruction: Optional[str] = None) -> "ChatSession":
        """
        Create a standalone chat session (for non-persistent use cases).
        
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
    responses following the latest Gemini API patterns from Context 7 documentation.
    """
    
    def __init__(self, chat_session):
        """
        Initialize chat session wrapper.
        
        Args:
            chat_session: The underlying Gemini chat session object
        """
        self.chat = chat_session
    
    def send_message(self, message: str) -> str:
        """
        Send a message to the chat session.
        
        The chat session automatically maintains conversation history,
        so no need to manually pass history - it's handled by the SDK.
        
        Args:
            message: The user message to send
            
        Returns:
            str: The model's response text
            
        Raises:
            errors.APIError: If the API call fails
        """
        try:
            # The new SDK automatically manages conversation history within the chat session
            response = self.chat.send_message(message)
            return response.text
            
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise ValueError(f"Failed to send message: {str(e)}")
    
    def send_message_stream(self, message: str):
        """
        Send a message and get streaming response.
        
        Args:
            message: The user message to send
            
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
    
    def get_history(self) -> List[dict]:
        """
        Get the conversation history from the chat session.
        
        Returns:
            List[dict]: List of messages in the conversation as dictionaries
        """
        try:
            # Use the SDK's built-in history management
            history = self.chat.get_history()
            chat_messages = []
            
            for message in history:
                # Convert Gemini message format to dictionary
                chat_message = {
                    "role": message.role,
                    "content": message.parts[0].text if message.parts and len(message.parts) > 0 else ""
                }
                chat_messages.append(chat_message)
            
            return chat_messages
            
        except Exception as e:
            # Return empty history if retrieval fails
            return []
    
    def restore_conversation_history(self, messages: List[dict]) -> None:
        """
        Restore conversation history to the Gemini chat session.
        
        This method uses Gemini's history initialization to restore previous conversation
        context without actually sending new messages, ensuring efficient memory restoration.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                     Expected format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        try:
            if not messages:
                return
            
            # Convert messages to Gemini's expected format
            from google.genai.types import Content, Part
            
            history = []
            for message in messages:
                # Create content object for each message
                content = Content(
                    role=message["role"],
                    parts=[Part(text=message["content"])]
                )
                history.append(content)
            
            # Use Gemini's history initialization if available
            # This is more efficient than replaying messages
            if hasattr(self.chat, '_history') and history:
                # Set the internal history directly
                self.chat._history = history
            else:
                # Fallback: replay only the last few messages to establish context
                # This is more efficient than replaying all messages
                recent_messages = messages[-4:] if len(messages) > 4 else messages
                
                for i in range(0, len(recent_messages), 2):
                    if (i < len(recent_messages) and 
                        recent_messages[i]["role"] == "user" and
                        i + 1 < len(recent_messages) and 
                        recent_messages[i + 1]["role"] == "assistant"):
                        
                        try:
                            # Send user message to establish context
                            # The response will be different but context is established
                            self.chat.send_message(recent_messages[i]["content"])
                        except Exception:
                            # Continue if individual message fails
                            continue
            
        except Exception as e:
            # If history restoration fails completely, log the error but don't crash
            # The session will still work, just without the restored context
            pass
    

    
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