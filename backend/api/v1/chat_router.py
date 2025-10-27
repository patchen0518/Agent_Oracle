"""
Chat API router for handling chat requests.

Based on FastAPI v0.115.13+ documentation (Context 7 lookup: 2025-01-26)
Implements RESTful chat endpoint with Pydantic validation and proper HTTP status codes.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from google.genai import errors
import logging
import os

from backend.models.chat_models import ChatRequest, ChatResponse
from backend.services.chat_service import ChatService

# Create the router
router = APIRouter(prefix="/api/v1", tags=["chat"])

# Initialize chat service (in production, this might be dependency injected)
def get_chat_service() -> ChatService:
    """
    Dependency to get chat service instance.
    
    Returns:
        ChatService: Configured chat service instance
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Gemini API key not configured"
        )
    return ChatService(api_key=api_key)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    """
    Process a chat message and return AI response.
    
    Args:
        request: Chat request containing message and conversation history
        chat_service: Injected chat service instance
        
    Returns:
        ChatResponse: AI agent's response with timestamp
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    try:
        # Process the chat request
        response = await chat_service.process_chat_request(request)
        return response
        
    except ValueError as e:
        # Client error - invalid request data
        logging.warning(f"Invalid chat request: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        
    except errors.APIError as e:
        # Gemini API error
        logging.error(f"Gemini API error: {e}")
        
        # Map Gemini API errors to appropriate HTTP status codes
        if hasattr(e, 'code'):
            if e.code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API key"
                )
            elif e.code == 429:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later."
                )
            elif e.code == 503:
                raise HTTPException(
                    status_code=503,
                    detail="Gemini service temporarily unavailable"
                )
        
        # Generic API error
        raise HTTPException(
            status_code=502,
            detail="AI service error. Please try again."
        )
        
    except Exception as e:
        # Unexpected server error
        logging.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.get("/chat/health")
async def chat_health_check(
    chat_service: ChatService = Depends(get_chat_service)
) -> dict:
    """
    Health check endpoint for chat service.
    
    Returns:
        dict: Service health information
    """
    try:
        info = chat_service.get_session_info()
        return {
            "status": "healthy",
            "service": "chat",
            **info
        }
    except Exception as e:
        logging.error(f"Chat health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Chat service unhealthy"
        )