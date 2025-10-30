"""
Session management API router for Oracle chat application.

This router provides session-based endpoints for creating, managing, and
interacting with chat sessions, replacing the stateless chat architecture
with persistent session management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlmodel import Session
import os

from backend.config.database import get_session
from backend.services.session_service import SessionService
from backend.services.session_chat_service import SessionChatService
from backend.services.gemini_client import GeminiClient
from backend.models.session_models import (
    SessionCreate,
    SessionUpdate,
    SessionPublic,
    MessagePublic,
    ChatRequest,
    ChatResponse
)
from backend.models.error_models import ErrorResponse, ServiceErrorResponse
from backend.utils.logging_config import get_logger, log_error_context
from backend.api.v1.monitoring_router import track_session_operation

# Create the router
router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

# Get logger instance
logger = get_logger("session_router")


def get_session_service(db: Session = Depends(get_session)) -> SessionService:
    """
    Dependency to get session service instance.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        SessionService: Configured session service instance
    """
    return SessionService(db)


def get_session_chat_service(db: Session = Depends(get_session)) -> SessionChatService:
    """
    Dependency to get session chat service instance.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        SessionChatService: Configured session chat service instance
        
    Raises:
        HTTPException: If Gemini API key is not configured
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("Gemini API key not configured")
        raise HTTPException(
            status_code=500,
            detail="AI service not configured - please contact administrator"
        )
    
    try:
        gemini_client = GeminiClient(api_key=api_key)
        return SessionChatService(db, gemini_client)
    except Exception as e:
        logger.error(f"Failed to initialize session chat service: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize AI service"
        )


# Session Management Endpoints

@router.post("/", response_model=SessionPublic, status_code=status.HTTP_201_CREATED, responses={
    400: {"model": ErrorResponse, "description": "Invalid session data"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def create_session(
    session_data: SessionCreate,
    request: Request,
    session_service: SessionService = Depends(get_session_service)
) -> SessionPublic:
    """
    Create a new chat session.
    
    Args:
        session_data: Session creation data including title and metadata
        request: FastAPI request object for logging context
        session_service: Injected session service instance
        
    Returns:
        SessionPublic: Created session with generated ID and timestamps
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    request_context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "session_title": session_data.title
    }
    
    logger.info("Creating new session", extra=request_context)
    
    try:
        from datetime import datetime
        start_time = datetime.utcnow()
        
        session = await session_service.create_session(session_data)
        
        # Track operation performance
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        track_session_operation("create_session", duration_ms)
        
        logger.info(
            "Session created successfully",
            extra={**request_context, "session_id": session.id}
        )
        
        return session
        
    except ValueError as e:
        logger.warning(f"Invalid session data: {e}", extra=request_context)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        
    except Exception as e:
        log_error_context(logger, e, request_context)
        raise HTTPException(
            status_code=500,
            detail="Failed to create session"
        )


@router.get("/", response_model=List[SessionPublic], responses={
    400: {"model": ErrorResponse, "description": "Invalid query parameters"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    request: Request = None,
    session_service: SessionService = Depends(get_session_service)
) -> List[SessionPublic]:
    """
    List all chat sessions with pagination.
    
    Args:
        limit: Maximum number of sessions to return (1-100, default: 50)
        offset: Number of sessions to skip for pagination (default: 0)
        request: FastAPI request object for logging context
        session_service: Injected session service instance
        
    Returns:
        List[SessionPublic]: List of sessions ordered by updated_at desc
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    request_context = {
        "method": request.method if request else "GET",
        "url": str(request.url) if request else "/api/v1/sessions/",
        "client_ip": request.client.host if request and request.client else "unknown",
        "limit": limit,
        "offset": offset
    }
    
    logger.info("Listing sessions", extra=request_context)
    
    try:
        from datetime import datetime
        start_time = datetime.utcnow()
        
        sessions = await session_service.list_sessions(limit=limit, offset=offset)
        
        # Track operation performance
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        track_session_operation("list_sessions", duration_ms)
        
        logger.info(
            "Sessions listed successfully",
            extra={**request_context, "session_count": len(sessions)}
        )
        
        return sessions
        
    except ValueError as e:
        logger.warning(f"Invalid query parameters: {e}", extra=request_context)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        
    except Exception as e:
        log_error_context(logger, e, request_context)
        raise HTTPException(
            status_code=500,
            detail="Failed to list sessions"
        )


@router.get("/{session_id}", response_model=SessionPublic, responses={
    400: {"model": ErrorResponse, "description": "Invalid session ID"},
    404: {"model": ErrorResponse, "description": "Session not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_session(
    session_id: int,
    request: Request,
    session_service: SessionService = Depends(get_session_service)
) -> SessionPublic:
    """
    Retrieve a specific session by ID.
    
    Args:
        session_id: Unique identifier of the session
        request: FastAPI request object for logging context
        session_service: Injected session service instance
        
    Returns:
        SessionPublic: Session data if found
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    request_context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "session_id": session_id
    }
    
    logger.info("Retrieving session", extra=request_context)
    
    try:
        from datetime import datetime
        start_time = datetime.utcnow()
        
        session = await session_service.get_session(session_id)
        
        if not session:
            logger.warning("Session not found", extra=request_context)
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Track operation performance
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        track_session_operation("get_session", duration_ms)
        
        logger.info("Session retrieved successfully", extra=request_context)
        return session
        
    except HTTPException:
        raise
        
    except ValueError as e:
        logger.warning(f"Invalid session ID: {e}", extra=request_context)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        
    except Exception as e:
        log_error_context(logger, e, request_context)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve session"
        )


@router.put("/{session_id}", response_model=SessionPublic, responses={
    400: {"model": ErrorResponse, "description": "Invalid session ID or update data"},
    404: {"model": ErrorResponse, "description": "Session not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def update_session(
    session_id: int,
    updates: SessionUpdate,
    request: Request,
    session_service: SessionService = Depends(get_session_service)
) -> SessionPublic:
    """
    Update a session's title and metadata.
    
    Args:
        session_id: Unique identifier of the session to update
        updates: Session update data containing new title and/or metadata
        request: FastAPI request object for logging context
        session_service: Injected session service instance
        
    Returns:
        SessionPublic: Updated session data
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    request_context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "session_id": session_id
    }
    
    logger.info("Updating session", extra=request_context)
    
    try:
        session = await session_service.update_session(session_id, updates)
        
        if not session:
            logger.warning("Session not found for update", extra=request_context)
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        logger.info("Session updated successfully", extra=request_context)
        return session
        
    except HTTPException:
        raise
        
    except ValueError as e:
        logger.warning(f"Invalid update data: {e}", extra=request_context)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        
    except Exception as e:
        log_error_context(logger, e, request_context)
        raise HTTPException(
            status_code=500,
            detail="Failed to update session"
        )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT, responses={
    400: {"model": ErrorResponse, "description": "Invalid session ID"},
    404: {"model": ErrorResponse, "description": "Session not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def delete_session(
    session_id: int,
    request: Request,
    session_service: SessionService = Depends(get_session_service)
) -> None:
    """
    Delete a session and all associated messages.
    
    Args:
        session_id: Unique identifier of the session to delete
        request: FastAPI request object for logging context
        session_service: Injected session service instance
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    request_context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "session_id": session_id
    }
    
    logger.info("Deleting session", extra=request_context)
    
    try:
        deleted = await session_service.delete_session(session_id)
        
        if not deleted:
            logger.warning("Session not found for deletion", extra=request_context)
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        logger.info("Session deleted successfully", extra=request_context)
        
    except HTTPException:
        raise
        
    except ValueError as e:
        logger.warning(f"Invalid session ID: {e}", extra=request_context)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
        
    except Exception as e:
        log_error_context(logger, e, request_context)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete session"
        )


# Session Chat Endpoints

@router.post("/{session_id}/chat", response_model=ChatResponse, responses={
    400: {"model": ErrorResponse, "description": "Invalid session ID or message data"},
    404: {"model": ErrorResponse, "description": "Session not found"},
    401: {"model": ServiceErrorResponse, "description": "Authentication failed"},
    429: {"model": ServiceErrorResponse, "description": "Rate limit exceeded"},
    502: {"model": ServiceErrorResponse, "description": "AI service error"},
    503: {"model": ServiceErrorResponse, "description": "Service unavailable"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def send_message(
    session_id: int,
    chat_request: ChatRequest,
    request: Request,
    session_chat_service: SessionChatService = Depends(get_session_chat_service)
) -> ChatResponse:
    """
    Send a message within a session context and get AI response.
    
    Args:
        session_id: Unique identifier of the session
        chat_request: Chat request containing the user message
        request: FastAPI request object for logging context
        session_chat_service: Injected session chat service instance
        
    Returns:
        ChatResponse: Complete response including user message, assistant response, and session info
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    request_context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "session_id": session_id,
        "message_length": len(chat_request.message)
    }
    
    logger.info("Processing session chat message", extra=request_context)
    
    try:
        from datetime import datetime
        start_time = datetime.utcnow()
        
        response = await session_chat_service.send_message(session_id, chat_request.message)
        
        # Track operation performance
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        track_session_operation("send_message", duration_ms)
        
        logger.info(
            "Session chat message processed successfully",
            extra={
                **request_context,
                "response_length": len(response.assistant_message.content)
            }
        )
        
        return response
        
    except ValueError as e:
        logger.warning(f"Invalid chat request: {e}", extra=request_context)
        raise HTTPException(
            status_code=400 if "not found" not in str(e).lower() else 404,
            detail=str(e)
        )
        
    except Exception as e:
        # Handle Gemini API errors similar to the original chat router
        from google.genai import errors
        
        if isinstance(e, errors.APIError):
            error_context = {**request_context, "gemini_error": str(e)}
            log_error_context(logger, e, error_context)
            
            # Map Gemini API errors to appropriate HTTP status codes
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
        
        # Unexpected server error
        log_error_context(logger, e, request_context)
        
        error_detail = "An unexpected error occurred while processing your message"
        if os.getenv("ENVIRONMENT", "production").lower() == "development":
            error_detail = f"Internal server error: {str(e)}"
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )


@router.get("/{session_id}/messages", response_model=List[MessagePublic], responses={
    400: {"model": ErrorResponse, "description": "Invalid session ID or query parameters"},
    404: {"model": ErrorResponse, "description": "Session not found"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_session_messages(
    session_id: int,
    limit: int = 100,
    offset: int = 0,
    request: Request = None,
    session_service: SessionService = Depends(get_session_service)
) -> List[MessagePublic]:
    """
    Retrieve message history for a session.
    
    Args:
        session_id: Unique identifier of the session
        limit: Maximum number of messages to return (1-1000, default: 100)
        offset: Number of messages to skip for pagination (default: 0)
        request: FastAPI request object for logging context
        session_service: Injected session service instance
        
    Returns:
        List[MessagePublic]: List of messages ordered by timestamp asc
        
    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    request_context = {
        "method": request.method if request else "GET",
        "url": str(request.url) if request else f"/api/v1/sessions/{session_id}/messages",
        "client_ip": request.client.host if request and request.client else "unknown",
        "session_id": session_id,
        "limit": limit,
        "offset": offset
    }
    
    logger.info("Retrieving session messages", extra=request_context)
    
    try:
        from datetime import datetime
        start_time = datetime.utcnow()
        
        messages = await session_service.get_session_messages(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        # Track operation performance
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        track_session_operation("get_messages", duration_ms)
        
        logger.info(
            "Session messages retrieved successfully",
            extra={**request_context, "message_count": len(messages)}
        )
        
        return messages
        
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            logger.warning("Session not found for message retrieval", extra=request_context)
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )
        else:
            logger.warning(f"Invalid query parameters: {e}", extra=request_context)
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
    except Exception as e:
        log_error_context(logger, e, request_context)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve session messages"
        )