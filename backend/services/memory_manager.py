"""
Memory management system for LangChain integration.

This module provides intelligent memory strategies for conversation management,
including buffer memory, summary memory, and entity extraction capabilities.
"""

from typing import List, Dict, Any, Optional
import logging
from abc import ABC, abstractmethod
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class MemoryStrategy(ABC):
    """Abstract base class for memory strategies."""
    
    @abstractmethod
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to memory."""
        pass
    
    @abstractmethod
    def get_context(self) -> List[BaseMessage]:
        """Get conversation context."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear memory."""
        pass


class BufferMemoryStrategy(MemoryStrategy):
    """Buffer memory strategy that keeps recent messages in full detail."""
    
    def __init__(self, max_buffer_size: int = 20):
        """
        Initialize buffer memory strategy.
        
        Args:
            max_buffer_size: Maximum number of messages to keep in buffer
        """
        self.max_buffer_size = max_buffer_size
        self.messages: List[BaseMessage] = []
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the buffer."""
        self.messages.append(message)
        
        # Keep only the most recent messages
        if len(self.messages) > self.max_buffer_size:
            # Always keep system messages at the beginning
            system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
            other_messages = [msg for msg in self.messages if not isinstance(msg, SystemMessage)]
            
            # Keep the most recent non-system messages
            recent_messages = other_messages[-(self.max_buffer_size - len(system_messages)):]
            self.messages = system_messages + recent_messages
    
    def get_context(self) -> List[BaseMessage]:
        """Get all messages in buffer."""
        return self.messages.copy()
    
    def clear(self) -> None:
        """Clear the buffer."""
        self.messages.clear()


class MemoryManager:
    """
    Intelligent memory manager for conversation context.
    
    This class manages conversation memory using configurable strategies
    and provides session-specific context isolation.
    """
    
    def __init__(
        self, 
        session_id: int, 
        memory_strategy: str = "buffer",
        max_buffer_size: int = 20
    ):
        """
        Initialize the memory manager.
        
        Args:
            session_id: Unique session identifier
            memory_strategy: Memory strategy to use ("buffer", "summary", "entity", "hybrid")
            max_buffer_size: Maximum buffer size for buffer strategy
        """
        self.session_id = session_id
        self.memory_strategy_name = memory_strategy
        
        # Initialize memory strategy
        if memory_strategy == "buffer":
            self.strategy = BufferMemoryStrategy(max_buffer_size)
        else:
            # For now, default to buffer strategy
            # Other strategies will be implemented in future tasks
            logger.warning(f"Strategy '{memory_strategy}' not implemented, using buffer")
            self.strategy = BufferMemoryStrategy(max_buffer_size)
        
        logger.info(f"Memory manager initialized for session {session_id} with {memory_strategy} strategy")
    
    def add_message(self, message: BaseMessage) -> None:
        """
        Add a message to memory.
        
        Args:
            message: Message to add to memory
        """
        try:
            self.strategy.add_message(message)
            logger.debug(f"Added message to memory for session {self.session_id}")
        except Exception as e:
            logger.error(f"Error adding message to memory: {e}")
            raise
    
    def get_conversation_context(self) -> List[BaseMessage]:
        """
        Get the current conversation context.
        
        Returns:
            List of messages representing the conversation context
        """
        try:
            context = self.strategy.get_context()
            logger.debug(f"Retrieved {len(context)} messages from memory for session {self.session_id}")
            return context
        except Exception as e:
            logger.error(f"Error retrieving conversation context: {e}")
            raise
    
    def extract_entities(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        Extract entities from conversation messages.
        
        Args:
            messages: Messages to extract entities from
            
        Returns:
            Dictionary of extracted entities
            
        Note:
            This is a placeholder implementation. Entity extraction
            will be implemented in future tasks.
        """
        # Placeholder implementation
        entities = {
            "names": [],
            "dates": [],
            "preferences": [],
            "facts": []
        }
        
        logger.debug(f"Entity extraction placeholder called for {len(messages)} messages")
        return entities
    
    def summarize_conversation(self, messages: List[BaseMessage]) -> str:
        """
        Summarize conversation messages.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Summary of the conversation
            
        Note:
            This is a placeholder implementation. Summarization
            will be implemented in future tasks.
        """
        # Placeholder implementation
        summary = f"Conversation summary for {len(messages)} messages"
        logger.debug(f"Conversation summarization placeholder called")
        return summary
    
    def clear_memory(self) -> None:
        """Clear all memory for this session."""
        try:
            self.strategy.clear()
            logger.info(f"Cleared memory for session {self.session_id}")
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")
            raise