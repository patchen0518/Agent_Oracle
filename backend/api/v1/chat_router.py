"""
Chat API router for handling chat requests.

Based on FastAPI v0.115.13+ documentation (Context 7 lookup: 2025-01-26)
Implements RESTful chat endpoint with Pydantic validation and proper HTTP status codes.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from google.genai import errors
import os
from typing import Dict, Any

from backend.models.chat_models import ChatRequest, ChatResponse
from backend.models.error_models import ErrorResponse, ServiceErrorResponse
from backend.services.chat_service import ChatService
from backend.utils.logging_config import get_logger, log_error_context

# Create the router
router = APIRouter(prefix="/api/v1", tags=["chat"])

# Get logger instance
logger = get_logger("chat_router")

# Initialize chat service (in production, this might be dependency injected)
def get_chat_service() -> ChatService:
    """
    Dependency to get chat service instance.
    
    Returns:
        ChatService: Configured chat service instance
        
    Raises:
        HTTPException: If API key is not configured
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("Gemini API key not configured")
        raise HTTPException(
            status_code=500,
            detail="AI service not configured - please contact administrator"
        )
    
    try:
        return ChatService(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize chat service: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize AI service"
        )


@router.post("/chat", response_model=ChatResponse, responses={
    400: {"model": ErrorResponse, "description": "Invalid request data"},
    401: {"model": ServiceErrorResponse, "description": "Authentication failed"},
    429: {"model": ServiceErrorResponse, "description": "Rate limit exceeded"},
    502: {"model": ServiceErrorResponse, "description": "AI service error"},
    503: {"model": ServiceErrorResponse, "description": "Service unavailable"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def chat_endpoint(
    chat_request: ChatRequest,
    request: Request,
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    """
    Process a chat message and return AI response.
    
    Args:
        chat_request: Chat request containing message and conversation history
        request: FastAPI request object for logging context
        chat_service: Injected chat service instance
        
    Returns:
        ChatResponse: AI agent's response with timestamp
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    # Create request context for logging
    request_context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "message_length": len(chat_request.message),
        "history_length": len(chat_request.history)
    }
    
    logger.info("Processing chat request", extra=request_context)
    
    try:
        # Process the chat request
        response = await chat_service.process_chat_request(chat_request)
        
        logger.info(
            "Chat request processed successfully", 
            extra={**request_context, "response_length": len(response.response)}
        )
        
        return response
        
    except ValueError as e:
        # Client error - invalid request data
        logger.warning(f"Invalid chat request: {e}", extra=request_context)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        
    except errors.APIError as e:
        # Gemini API error with enhanced error mapping
        error_context = {**request_context, "gemini_error": str(e)}
        log_error_context(logger, e, error_context)
        
        # Map Gemini API errors to appropriate HTTP status codes with user-friendly messages
        if hasattr(e, 'code'):
            if e.code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication with AI service failed"
                )
            elif e.code == 403:
                raise HTTPException(
                    status_code=403,
                    detail="Access to AI service denied"
                )
            elif e.code == 429:
                # Extract retry-after if available
                retry_after = getattr(e, 'retry_after', 60)
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Please wait {retry_after} seconds before trying again.",
                    headers={"Retry-After": str(retry_after)}
                )
            elif e.code == 400:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid request to AI service - please check your message format"
                )
            elif e.code == 503:
                raise HTTPException(
                    status_code=503,
                    detail="AI service is temporarily unavailable. Please try again in a few minutes."
                )
        
        # Generic API error
        raise HTTPException(
            status_code=502,
            detail="AI service is experiencing issues. Please try again later."
        )
        
    except Exception as e:
        # Unexpected server error
        log_error_context(logger, e, request_context)
        
        # Don't expose internal error details in production
        error_detail = "An unexpected error occurred while processing your request"
        if os.getenv("ENVIRONMENT", "production").lower() == "development":
            error_detail = f"Internal server error: {str(e)}"
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )


@router.get("/chat/health", responses={
    200: {"description": "Service is healthy"},
    503: {"model": ErrorResponse, "description": "Service is unhealthy"}
})
async def chat_health_check(
    request: Request,
    chat_service: ChatService = Depends(get_chat_service)
) -> Dict[str, Any]:
    """
    Health check endpoint for chat service.
    
    Args:
        request: FastAPI request object for logging context
        chat_service: Injected chat service instance
    
    Returns:
        dict: Service health information
        
    Raises:
        HTTPException: If service is unhealthy
    """
    request_context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown"
    }
    
    try:
        info = chat_service.get_session_info()
        
        health_data = {
            "status": "healthy",
            "service": "chat",
            "timestamp": "2025-01-27T00:00:00Z",  # Would use actual timestamp
            **info
        }
        
        logger.debug("Chat health check successful", extra={**request_context, **health_data})
        return health_data
        
    except Exception as e:
        log_error_context(logger, e, request_context)
        raise HTTPException(
            status_code=503,
            detail="Chat service is currently unavailable"
        )