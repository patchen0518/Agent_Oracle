"""
LangChain-specific exception handling for Oracle application.

This module defines LangChain-specific exceptions and provides mapping
to existing Oracle exception types for consistent error handling.
"""

from typing import Optional, Dict, Any
from langchain_core.exceptions import LangChainException

from .base_exceptions import (
    OracleException,
    AIServiceError,
    ConfigurationError,
    ValidationError
)


class LangChainError(AIServiceError):
    """Base exception for LangChain operations"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, original_error)
        self.context = context or {}
        self.error_code = "LANGCHAIN_ERROR"


class MemoryError(LangChainError):
    """Memory management operation failures"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, 
                 session_id: Optional[int] = None, memory_strategy: Optional[str] = None):
        context = {}
        if session_id is not None:
            context["session_id"] = session_id
        if memory_strategy:
            context["memory_strategy"] = memory_strategy
            
        super().__init__(message, original_error, context)
        self.error_code = "MEMORY_ERROR"
        self.session_id = session_id
        self.memory_strategy = memory_strategy


class ContextOptimizationError(LangChainError):
    """Context optimization failures"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None,
                 session_id: Optional[int] = None, optimization_type: Optional[str] = None):
        context = {}
        if session_id is not None:
            context["session_id"] = session_id
        if optimization_type:
            context["optimization_type"] = optimization_type
            
        super().__init__(message, original_error, context)
        self.error_code = "CONTEXT_OPTIMIZATION_ERROR"
        self.session_id = session_id
        self.optimization_type = optimization_type


class ModelInitializationError(LangChainError):
    """LangChain model initialization failures"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None,
                 model_name: Optional[str] = None, api_key_present: Optional[bool] = None):
        context = {}
        if model_name:
            context["model_name"] = model_name
        if api_key_present is not None:
            context["api_key_present"] = api_key_present
            
        super().__init__(message, original_error, context)
        self.error_code = "MODEL_INITIALIZATION_ERROR"
        self.model_name = model_name


class SessionMemoryError(MemoryError):
    """Session-specific memory operation failures"""
    
    def __init__(self, message: str, session_id: int, original_error: Optional[Exception] = None,
                 operation: Optional[str] = None):
        super().__init__(message, original_error, session_id)
        self.error_code = "SESSION_MEMORY_ERROR"
        self.operation = operation
        if operation:
            self.context["operation"] = operation


class MessageProcessingError(LangChainError):
    """Message processing and conversion failures"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None,
                 message_role: Optional[str] = None, session_id: Optional[int] = None):
        context = {}
        if message_role:
            context["message_role"] = message_role
        if session_id is not None:
            context["session_id"] = session_id
            
        super().__init__(message, original_error, context)
        self.error_code = "MESSAGE_PROCESSING_ERROR"
        self.message_role = message_role
        self.session_id = session_id


class SummarizationError(ContextOptimizationError):
    """Summarization operation failures"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None,
                 session_id: Optional[int] = None, message_count: Optional[int] = None):
        super().__init__(message, original_error, session_id, "summarization")
        self.error_code = "SUMMARIZATION_ERROR"
        self.message_count = message_count
        if message_count is not None:
            self.context["message_count"] = message_count


class TokenCalculationError(ContextOptimizationError):
    """Token calculation and management failures"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None,
                 session_id: Optional[int] = None, token_count: Optional[int] = None):
        super().__init__(message, original_error, session_id, "token_calculation")
        self.error_code = "TOKEN_CALCULATION_ERROR"
        self.token_count = token_count
        if token_count is not None:
            self.context["token_count"] = token_count


class LangChainExceptionMapper:
    """
    Maps LangChain exceptions to Oracle application exceptions.
    
    Provides consistent error handling by converting LangChain-specific
    exceptions to the application's exception hierarchy.
    """
    
    @staticmethod
    def map_langchain_exception(
        original_error: Exception,
        context_message: str = "",
        session_id: Optional[int] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> LangChainError:
        """
        Map a LangChain exception to an appropriate Oracle exception.
        
        Args:
            original_error: The original LangChain exception
            context_message: Additional context about where the error occurred
            session_id: Optional session ID for context
            additional_context: Additional context information
            
        Returns:
            LangChainError: Mapped exception with appropriate type and context
        """
        error_message = str(original_error)
        full_message = f"{context_message}: {error_message}" if context_message else error_message
        
        # Map based on exception type and message content
        if isinstance(original_error, LangChainException):
            # Handle specific LangChain exception types
            error_type = type(original_error).__name__.lower()
            
            if "memory" in error_type or "memory" in error_message.lower():
                return MemoryError(
                    full_message,
                    original_error,
                    session_id=session_id
                )
            elif "token" in error_message.lower() or "context" in error_message.lower():
                return ContextOptimizationError(
                    full_message,
                    original_error,
                    session_id=session_id,
                    optimization_type="context_management"
                )
            elif "model" in error_message.lower() or "initialization" in error_message.lower():
                return ModelInitializationError(
                    full_message,
                    original_error
                )
            elif "message" in error_message.lower() or "conversion" in error_message.lower():
                return MessageProcessingError(
                    full_message,
                    original_error,
                    session_id=session_id
                )
            else:
                # Generic LangChain error
                return LangChainError(
                    full_message,
                    original_error,
                    additional_context
                )
        
        # Handle API-related errors
        elif "api" in error_message.lower() or "key" in error_message.lower():
            return ModelInitializationError(
                full_message,
                original_error,
                api_key_present=False
            )
        
        # Handle rate limiting and quota errors
        elif any(term in error_message.lower() for term in ["rate", "quota", "limit", "throttle"]):
            return LangChainError(
                full_message,
                original_error,
                {"error_type": "rate_limiting"}
            )
        
        # Handle network and connectivity errors
        elif any(term in error_message.lower() for term in ["network", "connection", "timeout", "unreachable"]):
            return LangChainError(
                full_message,
                original_error,
                {"error_type": "connectivity"}
            )
        
        # Default mapping
        return LangChainError(
            full_message,
            original_error,
            additional_context
        )
    
    @staticmethod
    def handle_memory_operation_error(
        operation: str,
        session_id: int,
        original_error: Exception,
        memory_strategy: Optional[str] = None
    ) -> MemoryError:
        """
        Handle memory operation specific errors with detailed context.
        
        Args:
            operation: The memory operation that failed
            session_id: The session ID where the error occurred
            original_error: The original exception
            memory_strategy: The memory strategy being used
            
        Returns:
            MemoryError: Detailed memory error with operation context
        """
        message = f"Memory operation '{operation}' failed for session {session_id}"
        
        if isinstance(original_error, MemoryError):
            return original_error
        
        return MemoryError(
            message,
            original_error,
            session_id=session_id,
            memory_strategy=memory_strategy
        )
    
    @staticmethod
    def handle_context_optimization_error(
        optimization_type: str,
        session_id: Optional[int],
        original_error: Exception,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> ContextOptimizationError:
        """
        Handle context optimization specific errors with detailed context.
        
        Args:
            optimization_type: The type of optimization that failed
            session_id: The session ID where the error occurred
            original_error: The original exception
            additional_info: Additional information about the error
            
        Returns:
            ContextOptimizationError: Detailed optimization error
        """
        message = f"Context optimization '{optimization_type}' failed"
        if session_id is not None:
            message += f" for session {session_id}"
        
        if isinstance(original_error, ContextOptimizationError):
            return original_error
        
        error = ContextOptimizationError(
            message,
            original_error,
            session_id=session_id,
            optimization_type=optimization_type
        )
        
        if additional_info:
            error.context.update(additional_info)
        
        return error
    
    @staticmethod
    def create_fallback_error(
        primary_error: Exception,
        fallback_error: Exception,
        operation: str,
        session_id: Optional[int] = None
    ) -> LangChainError:
        """
        Create an error that represents both primary and fallback failures.
        
        Args:
            primary_error: The primary operation error
            fallback_error: The fallback operation error
            operation: The operation that failed
            session_id: Optional session ID for context
            
        Returns:
            LangChainError: Combined error with both failure contexts
        """
        message = (
            f"Operation '{operation}' failed: Primary error: {str(primary_error)}. "
            f"Fallback also failed: {str(fallback_error)}"
        )
        
        context = {
            "operation": operation,
            "primary_error": str(primary_error),
            "fallback_error": str(fallback_error),
            "primary_error_type": type(primary_error).__name__,
            "fallback_error_type": type(fallback_error).__name__
        }
        
        if session_id is not None:
            context["session_id"] = session_id
        
        return LangChainError(
            message,
            primary_error,  # Use primary error as the original
            context
        )


def handle_langchain_exception(
    func_name: str,
    session_id: Optional[int] = None,
    additional_context: Optional[Dict[str, Any]] = None
):
    """
    Decorator for handling LangChain exceptions in service methods.
    
    Args:
        func_name: Name of the function for error context
        session_id: Optional session ID for context
        additional_context: Additional context information
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except LangChainError:
                # Re-raise our own exceptions
                raise
            except LangChainException as e:
                # Map LangChain exceptions
                mapped_error = LangChainExceptionMapper.map_langchain_exception(
                    e,
                    f"Error in {func_name}",
                    session_id,
                    additional_context
                )
                raise mapped_error
            except Exception as e:
                # Handle unexpected exceptions
                mapped_error = LangChainExceptionMapper.map_langchain_exception(
                    e,
                    f"Unexpected error in {func_name}",
                    session_id,
                    additional_context
                )
                raise mapped_error
        return wrapper
    return decorator