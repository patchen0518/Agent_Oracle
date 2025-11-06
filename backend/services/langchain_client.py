"""
LangChain client wrapper for Google Generative AI integration.

Replaces the direct Gemini API client with LangChain's ChatGoogleGenerativeAI
while maintaining backward compatibility with the existing GeminiClient interface.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.exceptions import LangChainException

from backend.utils.logging_config import get_logger
from backend.exceptions import AIServiceError, ConfigurationError
from backend.config.system_instructions import get_system_instruction, list_available_instructions


class LangChainError(Exception):
    """Base exception for LangChain operations"""
    pass


class MemoryError(LangChainError):
    """Memory management operation failures"""
    pass


class ContextOptimizationError(LangChainError):
    """Context optimization failures"""
    pass


class ModelInitializationError(LangChainError):
    """LangChain model initialization failures"""
    pass


class LangChainClient:
    """
    LangChain-based client wrapper for Google Generative AI.
    
    Provides backward compatibility with GeminiClient interface while
    leveraging LangChain's ChatGoogleGenerativeAI for enhanced conversation
    management and memory strategies.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the LangChain client.
        
        Args:
            api_key: Google API key. If None, will use GEMINI_API_KEY or GOOGLE_API_KEY env var
            model: Model name to use for chat sessions. If None, will use GEMINI_MODEL env var or default to "gemini-2.5-flash"
            
        Raises:
            ConfigurationError: If no API key is provided or found in environment
            ModelInitializationError: If ChatGoogleGenerativeAI initialization fails
        """
        # Get model from parameter or environment, with fallback to default
        if model is None:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        self.model = model
        
        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            raise ConfigurationError(
                "Google API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.api_key = api_key
        
        # Initialize ChatGoogleGenerativeAI
        try:
            self.chat_model = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=api_key,
                temperature=0.7,
                convert_system_message_to_human=True  # Handle system messages properly
            )
        except Exception as e:
            raise ModelInitializationError(f"Failed to initialize ChatGoogleGenerativeAI: {str(e)}")
        
        # Session cache: session_id -> LangChainChatSession
        self.active_sessions: Dict[int, "LangChainChatSession"] = {}
        
        # Session management configuration (matching GeminiClient)
        self.session_timeout: int = 3600  # 1 hour
        self.max_sessions: int = 50
        self.last_cleanup: datetime = datetime.now()
        
        # Statistics
        self.sessions_created: int = 0
        self.sessions_cleaned: int = 0
        
        # Initialize logger
        self.logger = get_logger("langchain_client")
        
        self.logger.info(f"LangChainClient initialized with model: {self.model}")
        
        # Log available system instruction types
        available_instructions = list_available_instructions()
        self.logger.debug(f"Available system instruction types: {list(available_instructions.keys())}")
    
    def get_or_create_session(self, session_id: int, system_instruction: Optional[str] = None, recent_messages: Optional[List[dict]] = None) -> "LangChainChatSession":
        """
        Get existing LangChain chat session or create a new one with recent message context.
        
        Args:
            session_id: The session ID to retrieve or create
            system_instruction: Optional system instruction for new sessions
            recent_messages: Optional list of recent messages to restore context
            
        Returns:
            LangChainChatSession: The cached or newly created chat session with restored context
            
        Raises:
            AIServiceError: If session creation fails
        """
        # Import here to avoid circular imports
        from backend.services.langchain_chat_session import LangChainChatSession
        
        # Periodic cleanup
        self._cleanup_if_needed()
        
        # Return existing session if available
        if session_id in self.active_sessions:
            self.logger.debug(f"Reusing existing LangChain session for session_id {session_id}")
            return self.active_sessions[session_id]
        
        # Create new LangChain chat session
        try:
            chat_session = LangChainChatSession(
                chat_model=self.chat_model,
                session_id=session_id,
                system_instruction=system_instruction
            )
            
            # Restore recent conversation context if provided
            if recent_messages:
                chat_session.restore_context(recent_messages)
                self.logger.info(f"Restored {len(recent_messages)} recent messages for session_id {session_id}")
            
            self.active_sessions[session_id] = chat_session
            self.sessions_created += 1
            
            self.logger.info(f"Created new LangChain session for session_id {session_id}")
            return chat_session
            
        except LangChainException as e:
            raise AIServiceError(f"LangChain error: {str(e)}", e)
        except Exception as e:
            raise AIServiceError(f"Failed to create chat session for session {session_id}: {str(e)}", e)
    
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
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Dict[str, Any]: Session statistics compatible with GeminiClient
        """
        return {
            "active_sessions": len(self.active_sessions),
            "sessions_created": self.sessions_created,
            "sessions_cleaned": self.sessions_cleaned,
            "max_sessions": self.max_sessions
        }
    
    def create_chat_session(self, system_instruction: Optional[str] = None) -> "LangChainChatSession":
        """
        Create a standalone chat session (for non-persistent use cases).
        
        Args:
            system_instruction: Optional system instruction for the chat session
            
        Returns:
            LangChainChatSession: A new chat session instance
            
        Raises:
            AIServiceError: If chat session creation fails
        """
        # Import here to avoid circular imports
        from backend.services.langchain_chat_session import LangChainChatSession
        
        try:
            return LangChainChatSession(
                chat_model=self.chat_model,
                session_id=None,  # Standalone session
                system_instruction=system_instruction
            )
        except Exception as e:
            raise AIServiceError(f"Failed to create standalone chat session: {str(e)}", e)
    
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
    
    def validate_system_instruction(self, system_instruction: str) -> str:
        """
        Validate and process system instruction.
        
        Args:
            system_instruction: The system instruction text or type name
            
        Returns:
            str: The processed system instruction text
            
        Raises:
            ValueError: If the system instruction type is invalid
        """
        if not system_instruction or not system_instruction.strip():
            return ""
        
        instruction_text = system_instruction.strip()
        
        # Check if this is a system instruction type name
        try:
            available_instructions = list_available_instructions()
            if instruction_text.lower() in available_instructions:
                processed_instruction = get_system_instruction(instruction_text.lower())
                self.logger.debug(f"Resolved system instruction type '{instruction_text.lower()}'")
                return processed_instruction
        except ValueError:
            # If it's not a valid type, treat it as direct instruction text
            pass
        
        # Return as direct instruction text
        return instruction_text
    
    def get_available_instruction_types(self) -> Dict[str, str]:
        """
        Get available system instruction types.
        
        Returns:
            Dict[str, str]: Mapping of instruction type to description
        """
        return list_available_instructions()