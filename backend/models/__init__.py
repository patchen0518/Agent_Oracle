# Pydantic models package

from .chat_models import ChatMessage, ChatRequest, ChatResponse
from .error_models import (
    ErrorResponse,
    ServiceErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)
from .session_models import (
    Session,
    Message,
    SessionCreate,
    SessionUpdate,
    SessionPublic,
    SessionWithMessages,
    MessageCreate,
    MessagePublic,
    ChatRequest as SessionChatRequest,
    ChatResponse as SessionChatResponse,
)

__all__ = [
    # Chat models
    "ChatMessage",
    "ChatRequest", 
    "ChatResponse",
    # Session models
    "Session",
    "Message",
    "SessionCreate",
    "SessionUpdate",
    "SessionPublic",
    "SessionWithMessages",
    "MessageCreate",
    "MessagePublic",
    "SessionChatRequest",
    "SessionChatResponse",
    # Error models
    "ErrorResponse",
    "ServiceErrorResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
]