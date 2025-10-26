"""
Error response models for standardized API error handling.

Based on FastAPI error handling patterns and Pydantic v2 documentation
(Context 7 lookup: 2025-01-26). Provides consistent error response structure
across all API endpoints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ValidationErrorDetail(BaseModel):
    """
    Individual validation error detail.
    
    Follows FastAPI's default validation error format for consistency
    with automatic Pydantic validation errors.
    """
    loc: List[str] = Field(
        ...,
        description="Location of the error (e.g., ['body', 'message'])"
    )
    msg: str = Field(
        ...,
        description="Human-readable error message"
    )
    type: str = Field(
        ...,
        description="Error type identifier (e.g., 'value_error.missing')"
    )
    input: Optional[Any] = Field(
        default=None,
        description="The input value that caused the error"
    )


class ValidationErrorResponse(BaseModel):
    """
    Response model for validation errors (HTTP 400).
    
    Used when request data fails Pydantic validation.
    Compatible with FastAPI's automatic validation error format.
    """
    detail: List[ValidationErrorDetail] = Field(
        ...,
        description="List of validation errors"
    )


class ErrorResponse(BaseModel):
    """
    Generic error response model for API errors.
    
    Used for business logic errors, external service failures,
    and other non-validation errors. Follows FastAPI's HTTPException format.
    """
    detail: str = Field(
        ...,
        description="Human-readable error message"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Application-specific error code for programmatic handling"
    )


class ServiceErrorResponse(BaseModel):
    """
    Error response for external service failures.
    
    Used when Gemini API or other external services are unavailable
    or return errors. Provides additional context for debugging.
    """
    detail: str = Field(
        ...,
        description="Human-readable error message"
    )
    service: str = Field(
        ...,
        description="Name of the external service that failed"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Service-specific error code if available"
    )
    retry_after: Optional[int] = Field(
        default=None,
        description="Suggested retry delay in seconds for rate limiting"
    )