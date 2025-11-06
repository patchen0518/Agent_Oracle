"""
Exception handling package for Oracle application.

This package provides comprehensive exception handling including
base Oracle exceptions and LangChain-specific exceptions.
"""

# Import base exceptions
from .base_exceptions import (
    OracleException,
    ValidationError,
    NotFoundError,
    DatabaseError,
    AIServiceError,
    SessionError,
    ConfigurationError
)

# Import LangChain-specific exceptions
from .langchain_exceptions import (
    LangChainError,
    MemoryError as LangChainMemoryError,
    ContextOptimizationError,
    ModelInitializationError,
    SessionMemoryError,
    MessageProcessingError,
    SummarizationError,
    TokenCalculationError,
    LangChainExceptionMapper,
    handle_langchain_exception
)

__all__ = [
    # Base exceptions
    "OracleException",
    "ValidationError",
    "NotFoundError",
    "DatabaseError",
    "AIServiceError",
    "SessionError",
    "ConfigurationError",
    # LangChain exceptions
    "LangChainError",
    "LangChainMemoryError",
    "ContextOptimizationError",
    "ModelInitializationError",
    "SessionMemoryError",
    "MessageProcessingError",
    "SummarizationError",
    "TokenCalculationError",
    "LangChainExceptionMapper",
    "handle_langchain_exception"
]