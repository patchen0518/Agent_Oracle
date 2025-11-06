"""
Memory fallback mechanisms for LangChain integration.

Provides graceful degradation when memory strategies fail, ensuring
core functionality continues with partial memory failures.
"""

from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from backend.utils.logging_config import get_logger
from backend.exceptions import (
    LangChainMemoryError,
    SessionMemoryError,
    LangChainExceptionMapper
)


class FallbackLevel(Enum):
    """Levels of memory fallback degradation."""
    NONE = "none"                    # No fallback needed
    SIMPLE_BUFFER = "simple_buffer"  # Fall back to simple buffer memory
    BASIC_CONTEXT = "basic_context"  # Fall back to basic context management
    NO_MEMORY = "no_memory"          # No memory, session-only operation


@dataclass
class FallbackConfig:
    """Configuration for memory fallback behavior."""
    max_fallback_attempts: int = 3
    simple_buffer_size: int = 10
    basic_context_size: int = 5
    enable_fallback_logging: bool = True
    preserve_system_messages: bool = True
    fallback_timeout_seconds: int = 30


class MemoryFallbackManager:
    """
    Manages fallback mechanisms for memory operations.
    
    Provides graceful degradation when memory strategies fail,
    ensuring core functionality continues even with memory failures.
    """
    
    def __init__(self, session_id: Optional[int] = None, config: Optional[FallbackConfig] = None):
        """
        Initialize memory fallback manager.
        
        Args:
            session_id: Optional session ID for context
            config: Fallback configuration
        """
        self.session_id = session_id
        self.config = config or FallbackConfig()
        self.logger = get_logger("memory_fallback")
        
        # Track fallback state
        self.current_fallback_level = FallbackLevel.NONE
        self.fallback_attempts = 0
        self.fallback_history: List[Dict[str, Any]] = []
        
        # Simple buffer for fallback memory
        self.simple_buffer: List[BaseMessage] = []
        
        self.logger.debug(f"MemoryFallbackManager initialized for session {session_id}")
    
    def execute_with_fallback(
        self,
        primary_operation: Callable,
        operation_name: str,
        fallback_data: Optional[Any] = None,
        **kwargs
    ) -> Any:
        """
        Execute a memory operation with automatic fallback on failure.
        
        Args:
            primary_operation: The primary memory operation to attempt
            operation_name: Name of the operation for logging
            fallback_data: Optional data to use in fallback operations
            **kwargs: Additional arguments for the operation
            
        Returns:
            Result of the operation (primary or fallback)
            
        Raises:
            SessionMemoryError: If all fallback attempts fail
        """
        try:
            # Attempt primary operation
            result = primary_operation(**kwargs)
            
            # Reset fallback state on success
            if self.current_fallback_level != FallbackLevel.NONE:
                self.logger.info(
                    f"Session {self.session_id}: Primary operation '{operation_name}' "
                    f"succeeded after fallback level {self.current_fallback_level.value}"
                )
                self._reset_fallback_state()
            
            return result
            
        except Exception as primary_error:
            self.logger.warning(
                f"Session {self.session_id}: Primary operation '{operation_name}' failed: {str(primary_error)}"
            )
            
            # Attempt fallback
            return self._attempt_fallback(
                operation_name,
                primary_error,
                fallback_data,
                **kwargs
            )
    
    def _attempt_fallback(
        self,
        operation_name: str,
        primary_error: Exception,
        fallback_data: Optional[Any] = None,
        **kwargs
    ) -> Any:
        """
        Attempt fallback operations with progressive degradation.
        
        Args:
            operation_name: Name of the operation
            primary_error: The primary operation error
            fallback_data: Optional fallback data
            **kwargs: Operation arguments
            
        Returns:
            Result of fallback operation
            
        Raises:
            SessionMemoryError: If all fallbacks fail
        """
        self.fallback_attempts += 1
        
        # Record fallback attempt
        fallback_record = {
            "operation": operation_name,
            "attempt": self.fallback_attempts,
            "primary_error": str(primary_error),
            "fallback_level": self.current_fallback_level.value,
            "timestamp": self.logger.handlers[0].formatter.formatTime(self.logger.makeRecord(
                "memory_fallback", 20, "", 0, "", (), None
            )) if self.logger.handlers else "unknown"
        }
        self.fallback_history.append(fallback_record)
        
        # Check if we've exceeded max attempts
        if self.fallback_attempts > self.config.max_fallback_attempts:
            error = SessionMemoryError(
                f"All fallback attempts exhausted for operation '{operation_name}'",
                self.session_id,
                primary_error,
                operation=operation_name
            )
            self.logger.error(f"Session {self.session_id}: {str(error)}")
            raise error
        
        # Progressive fallback based on current level
        try:
            if self.current_fallback_level == FallbackLevel.NONE:
                return self._fallback_to_simple_buffer(operation_name, fallback_data, **kwargs)
            elif self.current_fallback_level == FallbackLevel.SIMPLE_BUFFER:
                return self._fallback_to_basic_context(operation_name, fallback_data, **kwargs)
            elif self.current_fallback_level == FallbackLevel.BASIC_CONTEXT:
                return self._fallback_to_no_memory(operation_name, fallback_data, **kwargs)
            else:
                # Already at lowest level
                raise SessionMemoryError(
                    f"No further fallback available for operation '{operation_name}'",
                    self.session_id,
                    primary_error,
                    operation=operation_name
                )
                
        except Exception as fallback_error:
            # Create combined error
            combined_error = LangChainExceptionMapper.create_fallback_error(
                primary_error,
                fallback_error,
                operation_name,
                self.session_id
            )
            
            self.logger.error(
                f"Session {self.session_id}: Fallback failed for '{operation_name}': {str(combined_error)}"
            )
            
            # Try next fallback level
            self._escalate_fallback_level()
            return self._attempt_fallback(operation_name, combined_error, fallback_data, **kwargs)
    
    def _fallback_to_simple_buffer(self, operation_name: str, fallback_data: Any, **kwargs) -> Any:
        """
        Fallback to simple buffer memory strategy.
        
        Args:
            operation_name: Name of the operation
            fallback_data: Fallback data
            **kwargs: Operation arguments
            
        Returns:
            Result using simple buffer strategy
        """
        self.current_fallback_level = FallbackLevel.SIMPLE_BUFFER
        self.logger.info(f"Session {self.session_id}: Falling back to simple buffer for '{operation_name}'")
        
        if operation_name == "add_message":
            return self._simple_buffer_add_message(kwargs.get("message"))
        elif operation_name == "get_context":
            return self._simple_buffer_get_context()
        elif operation_name == "restore_context":
            return self._simple_buffer_restore_context(kwargs.get("messages", []))
        elif operation_name == "clear_memory":
            return self._simple_buffer_clear()
        else:
            # Generic fallback - return empty result
            self.logger.warning(f"Session {self.session_id}: No specific simple buffer fallback for '{operation_name}'")
            return self._get_default_result(operation_name)
    
    def _fallback_to_basic_context(self, operation_name: str, fallback_data: Any, **kwargs) -> Any:
        """
        Fallback to basic context management (keep only recent messages).
        
        Args:
            operation_name: Name of the operation
            fallback_data: Fallback data
            **kwargs: Operation arguments
            
        Returns:
            Result using basic context strategy
        """
        self.current_fallback_level = FallbackLevel.BASIC_CONTEXT
        self.logger.info(f"Session {self.session_id}: Falling back to basic context for '{operation_name}'")
        
        if operation_name == "add_message":
            return self._basic_context_add_message(kwargs.get("message"))
        elif operation_name == "get_context":
            return self._basic_context_get_context()
        elif operation_name == "restore_context":
            return self._basic_context_restore_context(kwargs.get("messages", []))
        elif operation_name == "clear_memory":
            return self._basic_context_clear()
        else:
            # Generic fallback
            self.logger.warning(f"Session {self.session_id}: No specific basic context fallback for '{operation_name}'")
            return self._get_default_result(operation_name)
    
    def _fallback_to_no_memory(self, operation_name: str, fallback_data: Any, **kwargs) -> Any:
        """
        Fallback to no memory (session-only operation).
        
        Args:
            operation_name: Name of the operation
            fallback_data: Fallback data
            **kwargs: Operation arguments
            
        Returns:
            Result with no memory functionality
        """
        self.current_fallback_level = FallbackLevel.NO_MEMORY
        self.logger.warning(f"Session {self.session_id}: Falling back to no memory for '{operation_name}'")
        
        # For no-memory fallback, most operations return empty/default results
        if operation_name == "get_context":
            # Return only system messages if preserved
            if self.config.preserve_system_messages:
                system_messages = [msg for msg in self.simple_buffer if isinstance(msg, SystemMessage)]
                return system_messages
            return []
        else:
            return self._get_default_result(operation_name)
    
    def _simple_buffer_add_message(self, message: BaseMessage) -> bool:
        """Add message to simple buffer with size limit."""
        if not message:
            return False
        
        self.simple_buffer.append(message)
        
        # Maintain buffer size limit
        if len(self.simple_buffer) > self.config.simple_buffer_size:
            # Keep system messages and trim others
            system_messages = [msg for msg in self.simple_buffer if isinstance(msg, SystemMessage)]
            other_messages = [msg for msg in self.simple_buffer if not isinstance(msg, SystemMessage)]
            
            # Keep most recent messages
            recent_messages = other_messages[-(self.config.simple_buffer_size - len(system_messages)):]
            self.simple_buffer = system_messages + recent_messages
        
        return True
    
    def _simple_buffer_get_context(self) -> List[BaseMessage]:
        """Get context from simple buffer."""
        return self.simple_buffer.copy()
    
    def _simple_buffer_restore_context(self, messages: List[Dict[str, str]]) -> bool:
        """Restore context to simple buffer."""
        try:
            self.simple_buffer.clear()
            
            for msg_dict in messages[-self.config.simple_buffer_size:]:  # Keep only recent messages
                role = msg_dict.get("role", "").lower()
                content = msg_dict.get("content", "")
                
                if not content:
                    continue
                
                if role == "user":
                    self.simple_buffer.append(HumanMessage(content=content))
                elif role == "assistant":
                    self.simple_buffer.append(AIMessage(content=content))
                elif role == "system":
                    self.simple_buffer.append(SystemMessage(content=content))
            
            return True
        except Exception as e:
            self.logger.warning(f"Session {self.session_id}: Simple buffer restore failed: {str(e)}")
            return False
    
    def _simple_buffer_clear(self) -> bool:
        """Clear simple buffer."""
        if self.config.preserve_system_messages:
            # Keep only system messages
            system_messages = [msg for msg in self.simple_buffer if isinstance(msg, SystemMessage)]
            self.simple_buffer = system_messages
        else:
            self.simple_buffer.clear()
        return True
    
    def _basic_context_add_message(self, message: BaseMessage) -> bool:
        """Add message with basic context management."""
        if not message:
            return False
        
        self.simple_buffer.append(message)
        
        # More aggressive trimming for basic context
        if len(self.simple_buffer) > self.config.basic_context_size:
            system_messages = [msg for msg in self.simple_buffer if isinstance(msg, SystemMessage)]
            other_messages = [msg for msg in self.simple_buffer if not isinstance(msg, SystemMessage)]
            
            # Keep only most recent messages
            recent_messages = other_messages[-(self.config.basic_context_size - len(system_messages)):]
            self.simple_buffer = system_messages + recent_messages
        
        return True
    
    def _basic_context_get_context(self) -> List[BaseMessage]:
        """Get basic context (very limited)."""
        return self.simple_buffer[-self.config.basic_context_size:] if self.simple_buffer else []
    
    def _basic_context_restore_context(self, messages: List[Dict[str, str]]) -> bool:
        """Restore very limited context."""
        try:
            self.simple_buffer.clear()
            
            # Only restore the most recent messages
            recent_messages = messages[-self.config.basic_context_size:]
            
            for msg_dict in recent_messages:
                role = msg_dict.get("role", "").lower()
                content = msg_dict.get("content", "")
                
                if not content:
                    continue
                
                if role == "user":
                    self.simple_buffer.append(HumanMessage(content=content))
                elif role == "assistant":
                    self.simple_buffer.append(AIMessage(content=content))
                elif role == "system" and self.config.preserve_system_messages:
                    self.simple_buffer.append(SystemMessage(content=content))
            
            return True
        except Exception as e:
            self.logger.warning(f"Session {self.session_id}: Basic context restore failed: {str(e)}")
            return False
    
    def _basic_context_clear(self) -> bool:
        """Clear basic context."""
        if self.config.preserve_system_messages:
            system_messages = [msg for msg in self.simple_buffer if isinstance(msg, SystemMessage)]
            self.simple_buffer = system_messages
        else:
            self.simple_buffer.clear()
        return True
    
    def _escalate_fallback_level(self) -> None:
        """Escalate to the next fallback level."""
        if self.current_fallback_level == FallbackLevel.NONE:
            self.current_fallback_level = FallbackLevel.SIMPLE_BUFFER
        elif self.current_fallback_level == FallbackLevel.SIMPLE_BUFFER:
            self.current_fallback_level = FallbackLevel.BASIC_CONTEXT
        elif self.current_fallback_level == FallbackLevel.BASIC_CONTEXT:
            self.current_fallback_level = FallbackLevel.NO_MEMORY
        # NO_MEMORY is the final level
    
    def _reset_fallback_state(self) -> None:
        """Reset fallback state after successful operation."""
        self.current_fallback_level = FallbackLevel.NONE
        self.fallback_attempts = 0
        self.logger.debug(f"Session {self.session_id}: Fallback state reset")
    
    def _get_default_result(self, operation_name: str) -> Any:
        """Get default result for unknown operations."""
        if operation_name in ["add_message", "clear_memory", "restore_context"]:
            return True
        elif operation_name in ["get_context", "get_history"]:
            return []
        else:
            return None
    
    def get_fallback_status(self) -> Dict[str, Any]:
        """
        Get current fallback status and statistics.
        
        Returns:
            Dictionary with fallback status information
        """
        return {
            "session_id": self.session_id,
            "current_fallback_level": self.current_fallback_level.value,
            "fallback_attempts": self.fallback_attempts,
            "fallback_history_count": len(self.fallback_history),
            "simple_buffer_size": len(self.simple_buffer),
            "config": {
                "max_fallback_attempts": self.config.max_fallback_attempts,
                "simple_buffer_size": self.config.simple_buffer_size,
                "basic_context_size": self.config.basic_context_size
            }
        }
    
    def get_fallback_history(self) -> List[Dict[str, Any]]:
        """Get detailed fallback history."""
        return self.fallback_history.copy()
    
    def is_in_fallback_mode(self) -> bool:
        """Check if currently in fallback mode."""
        return self.current_fallback_level != FallbackLevel.NONE
    
    def force_fallback_level(self, level: FallbackLevel) -> None:
        """Force a specific fallback level (for testing or manual intervention)."""
        self.current_fallback_level = level
        self.logger.warning(f"Session {self.session_id}: Forced fallback level to {level.value}")
    
    def reset_fallback_manager(self) -> None:
        """Reset the entire fallback manager state."""
        self.current_fallback_level = FallbackLevel.NONE
        self.fallback_attempts = 0
        self.fallback_history.clear()
        self.simple_buffer.clear()
        self.logger.info(f"Session {self.session_id}: Fallback manager reset")


class MemoryOperationWrapper:
    """
    Wrapper for memory operations that automatically applies fallback mechanisms.
    
    This class can be used to wrap existing memory managers and add
    fallback capabilities without modifying the original implementation.
    """
    
    def __init__(self, memory_manager: Any, fallback_manager: MemoryFallbackManager):
        """
        Initialize memory operation wrapper.
        
        Args:
            memory_manager: The original memory manager to wrap
            fallback_manager: The fallback manager to use
        """
        self.memory_manager = memory_manager
        self.fallback_manager = fallback_manager
        self.logger = get_logger("memory_operation_wrapper")
    
    def add_message(self, message: BaseMessage) -> bool:
        """Add message with fallback support."""
        return self.fallback_manager.execute_with_fallback(
            lambda **kwargs: self.memory_manager.add_message(kwargs["message"]),
            "add_message",
            message=message
        )
    
    def get_conversation_context(self) -> List[BaseMessage]:
        """Get conversation context with fallback support."""
        return self.fallback_manager.execute_with_fallback(
            lambda **kwargs: self.memory_manager.get_conversation_context(),
            "get_context"
        )
    
    def restore_context(self, messages: List[Dict[str, str]]) -> bool:
        """Restore context with fallback support."""
        return self.fallback_manager.execute_with_fallback(
            lambda **kwargs: self.memory_manager.restore_context(kwargs["messages"]),
            "restore_context",
            messages=messages
        )
    
    def clear_memory(self) -> bool:
        """Clear memory with fallback support."""
        return self.fallback_manager.execute_with_fallback(
            lambda **kwargs: self.memory_manager.clear_memory(),
            "clear_memory"
        )
    
    def __getattr__(self, name):
        """Delegate other attributes to the wrapped memory manager."""
        return getattr(self.memory_manager, name)