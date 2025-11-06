"""
LangChain client implementation for Oracle Chat AI.

This module provides the LangChainClient class that replaces the direct
Google Generative AI API calls with LangChain's ChatGoogleGenerativeAI,
enabling advanced conversation management and memory strategies.
"""

from typing import Dict, List, Any, Optional
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from .langchain_chat_session import LangChainChatSession
from .memory_manager import MemoryManager
from .context_optimizer import ContextOptimizer

logger = logging.getLogger(__name__)


class LangChainClient:
    """
    LangChain-based client for managing AI conversations.
    
    This class replaces the existing GeminiClient with LangChain integration,
    providing enhanced memory management and context optimization while
    maintaining backward compatibility.
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialize the LangChain client.
        
        Args:
            api_key: Google API key for Gemini access
            model: Model name to use (default: gemini-2.5-flash)
        """
        self.api_key = api_key
        self.model = model
        self.sessions: Dict[int, LangChainChatSession] = {}
        
        # Initialize the ChatGoogleGenerativeAI model
        try:
            self.chat_model = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key,
                temperature=0.7,
                max_tokens=None,
                timeout=None,
                max_retries=2,
            )
            logger.info(f"LangChain client initialized with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize LangChain client: {e}")
            raise
    
    def get_or_create_session(
        self, 
        session_id: int, 
        system_instruction: str, 
        recent_messages: List[dict]
    ) -> LangChainChatSession:
        """
        Get existing session or create a new one.
        
        Args:
            session_id: Unique session identifier
            system_instruction: System instruction for AI personality
            recent_messages: Recent conversation messages for context restoration
            
        Returns:
            LangChainChatSession instance
        """
        if session_id not in self.sessions:
            # Create memory manager and context optimizer for the session
            memory_manager = MemoryManager(session_id=session_id)
            context_optimizer = ContextOptimizer()
            
            # Create new session
            session = LangChainChatSession(
                chat_model=self.chat_model,
                memory_manager=memory_manager,
                context_optimizer=context_optimizer
            )
            
            # Apply system instruction if provided
            if system_instruction:
                system_message = SystemMessage(content=system_instruction)
                memory_manager.add_message(system_message)
            
            # Restore context from recent messages
            if recent_messages:
                session.restore_context(recent_messages)
            
            self.sessions[session_id] = session
            logger.info(f"Created new LangChain session: {session_id}")
        
        return self.sessions[session_id]
    
    def remove_session(self, session_id: int) -> bool:
        """
        Remove a session from memory.
        
        Args:
            session_id: Session identifier to remove
            
        Returns:
            True if session was removed, False if not found
        """
        if session_id in self.sessions:
            # Clean up session memory
            self.sessions[session_id].memory_manager.clear_memory()
            del self.sessions[session_id]
            logger.info(f"Removed LangChain session: {session_id}")
            return True
        return False
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active sessions.
        
        Returns:
            Dictionary containing session statistics
        """
        return {
            "active_sessions": len(self.sessions),
            "session_ids": list(self.sessions.keys()),
            "model": self.model
        }