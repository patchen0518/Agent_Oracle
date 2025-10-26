"""
Chat-related Pydantic models for request/response validation.

Based on Pydantic v2 documentation (Context 7 lookup: 2025-01-26)
and FastAPI integration patterns for structured API validation.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    Represents a single message in a conversation.
    
    Used for both user messages and agent responses in conversation history.
    Follows Gemini API message format with role and parts fields.
    """
    role: Literal["user", "model"] = Field(
        ..., 
        description="The role of the message sender - 'user' for human input, 'model' for AI responses"
    )
    parts: str = Field(
        ..., 
        min_length=1, 
        max_length=4000,
        description="The message content/text"
    )


class ChatRequest(BaseModel):
    """
    Request model for chat API endpoint.
    
    Contains the user's message and conversation history for context.
    Validates message content and history structure.
    """
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=4000,
        description="The user's message to send to the AI agent"
    )
    history: List[ChatMessage] = Field(
        default_factory=list,
        max_length=100,  # Limit conversation history to prevent excessive context
        description="Previous messages in the conversation for context"
    )


class ChatResponse(BaseModel):
    """
    Response model for chat API endpoint.
    
    Contains the AI agent's response and optional metadata.
    """
    response: str = Field(
        ..., 
        description="The AI agent's response to the user's message"
    )
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.now,
        description="When the response was generated"
    )