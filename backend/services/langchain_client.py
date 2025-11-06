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
from backend.exceptions import (
    AIServiceError, 
    ConfigurationError,
    LangChainError,
    ModelInitializationError,
    LangChainMemoryError,
    LangChainExceptionMapper,
    handle_langchain_exception
)
from backend.config.system_instructions import get_system_instruction, list_available_instructions


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
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                "Failed to initialize ChatGoogleGenerativeAI",
                additional_context={"model": self.model, "api_key_present": bool(api_key)}
            )
            if isinstance(mapped_error, ModelInitializationError):
                raise mapped_error
            else:
                raise ModelInitializationError(
                    f"Failed to initialize ChatGoogleGenerativeAI: {str(e)}",
                    e,
                    model_name=self.model,
                    api_key_present=bool(api_key)
                )
        
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
            # Import here to avoid circular imports
            from backend.services.context_optimizer import ContextOptimizer, ContextConfig
            
            # Create context optimizer for this session
            context_config = ContextConfig()
            context_optimizer = ContextOptimizer(config=context_config, session_id=session_id)
            
            chat_session = LangChainChatSession(
                chat_model=self.chat_model,
                session_id=session_id,
                system_instruction=system_instruction,
                context_optimizer=context_optimizer
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
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                f"Failed to create LangChain session for session {session_id}",
                session_id=session_id
            )
            raise mapped_error
        except Exception as e:
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                f"Failed to create chat session for session {session_id}",
                session_id=session_id
            )
            raise mapped_error
    
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
            # Import here to avoid circular imports
            from backend.services.context_optimizer import ContextOptimizer, ContextConfig
            
            # Create context optimizer for standalone session
            context_config = ContextConfig()
            context_optimizer = ContextOptimizer(config=context_config, session_id=None)
            
            return LangChainChatSession(
                chat_model=self.chat_model,
                session_id=None,  # Standalone session
                system_instruction=system_instruction,
                context_optimizer=context_optimizer
            )
        except Exception as e:
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                "Failed to create standalone chat session"
            )
            raise mapped_error
    
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
    
    def sync_session_with_database(self, session_id: int, recent_messages: List[Dict[str, str]]) -> bool:
        """
        Synchronize a session's memory with database state.
        
        This method ensures that the LangChain memory state is consistent
        with the database persistence layer.
        
        Args:
            session_id: The session ID to synchronize
            recent_messages: Recent messages from database to restore
            
        Returns:
            bool: True if synchronization was successful
        """
        try:
            chat_session = self.active_sessions.get(session_id)
            if not chat_session:
                self.logger.debug(f"No active session {session_id} to synchronize")
                return True
            
            # Clear existing memory and restore from database
            chat_session.clear_history()
            
            # Restore system instruction if needed
            if chat_session.has_system_instruction():
                current_instruction = chat_session.get_system_instruction()
                if current_instruction:
                    chat_session._process_system_instruction(current_instruction)
            
            # Restore context from database messages
            if recent_messages:
                chat_session.restore_context(recent_messages)
            
            self.logger.info(f"Successfully synchronized session {session_id} with database")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to synchronize session {session_id} with database: {str(e)}")
            return False
    
    def get_memory_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about memory-database coordination across all sessions.
        
        Returns:
            Dictionary containing hybrid persistence statistics
        """
        stats = {
            "total_active_sessions": len(self.active_sessions),
            "sessions_with_memory": 0,
            "sessions_with_optimization": 0,
            "total_memory_messages": 0,
            "optimization_stats": {}
        }
        
        try:
            for session_id, chat_session in self.active_sessions.items():
                if chat_session.get_message_count() > 0:
                    stats["sessions_with_memory"] += 1
                    stats["total_memory_messages"] += chat_session.get_message_count()
                
                # Check if session has optimization stats
                if hasattr(chat_session, 'get_optimization_stats'):
                    try:
                        session_stats = chat_session.get_optimization_stats()
                        stats["sessions_with_optimization"] += 1
                        
                        # Aggregate optimization stats
                        if "total_optimizations" not in stats["optimization_stats"]:
                            stats["optimization_stats"]["total_optimizations"] = 0
                            stats["optimization_stats"]["total_tokens_saved"] = 0
                        
                        optimizer_stats = session_stats.get("optimizer", {})
                        stats["optimization_stats"]["total_optimizations"] += optimizer_stats.get("optimizations_performed", 0)
                        stats["optimization_stats"]["total_tokens_saved"] += optimizer_stats.get("tokens_saved", 0)
                        
                    except Exception as e:
                        self.logger.debug(f"Failed to get optimization stats for session {session_id}: {str(e)}")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get memory-database stats: {str(e)}")
            stats["error"] = str(e)
            return stats