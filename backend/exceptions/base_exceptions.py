"""
Custom exception hierarchy for Oracle application.

This module defines a structured exception hierarchy for better error handling
and categorization throughout the application.
"""


class OracleException(Exception):
    """Base exception for Oracle application."""
    
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        super().__init__(self.message)


class ValidationError(OracleException):
    """Raised when input validation fails."""
    pass


class NotFoundError(OracleException):
    """Raised when requested resource is not found."""
    pass


class DatabaseError(OracleException):
    """Raised when database operations fail."""
    pass


class AIServiceError(OracleException):
    """Raised when AI service operations fail."""
    
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class SessionError(OracleException):
    """Raised when session operations fail."""
    pass


class ConfigurationError(OracleException):
    """Raised when configuration is invalid or missing."""
    pass