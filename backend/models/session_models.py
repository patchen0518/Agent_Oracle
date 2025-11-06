"""
SQLModel data models for session management and message persistence.

This module defines the Session and Message models with proper relationships,
validation rules, and field constraints for data integrity in the Oracle
session management system.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlmodel import SQLModel, Field, Relationship, JSON, Column
from sqlalchemy import String, Text, Index


# Base models for shared fields and validation

class SessionBase(SQLModel):
    """Base model for Session with shared fields and validation."""
    title: str = Field(max_length=200, sa_column=Column(String(200)), description="Session title")
    model_used: str = Field(default="gemini-2.0-flash-exp", max_length=50, sa_column=Column(String(50)), description="AI model used for this session")
    session_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        sa_column=Column(JSON),
        description="Additional session metadata"
    )


class MessageBase(SQLModel):
    """Base model for Message with shared fields and validation."""
    role: str = Field(regex="^(user|assistant)$", sa_column=Column(String(20)), description="Message role: user or assistant")
    content: str = Field(min_length=1, sa_column=Column(Text), description="Message content")
    message_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Additional message metadata"
    )


# Database table models

class Session(SessionBase, table=True):
    """
    Session model representing a chat session in the database.
    
    A session contains multiple messages and tracks conversation metadata
    including creation time, last update, and message count for performance.
    """
    id: Optional[int] = Field(default=None, primary_key=True, description="Unique session identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last session update timestamp")
    message_count: int = Field(default=0, ge=0, description="Cached count of messages in this session")
    
    # Relationship to messages
    messages: List["Message"] = Relationship(
        back_populates="session",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "select"}
    )
    
    # Add indexes for common queries
    __table_args__ = (
        Index('idx_session_updated_at', 'updated_at'),
        Index('idx_session_created_at', 'created_at'),
    )


class Message(MessageBase, table=True):
    """
    Message model representing individual messages within a session.
    
    Each message belongs to a session and contains the conversation content
    along with metadata and timestamps.
    """
    id: Optional[int] = Field(default=None, primary_key=True, description="Unique message identifier")
    session_id: int = Field(foreign_key="session.id", description="Reference to parent session")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message creation timestamp")
    
    # Relationship to session
    session: Session = Relationship(back_populates="messages")
    
    # Add indexes for common queries
    __table_args__ = (
        Index('idx_message_session_id', 'session_id'),
        Index('idx_message_timestamp', 'timestamp'),
        Index('idx_message_session_timestamp', 'session_id', 'timestamp'),
    )


# API models for requests and responses

class SessionCreate(SessionBase):
    """Model for creating a new session."""
    pass


class SessionUpdate(SQLModel):
    """Model for updating an existing session."""
    title: Optional[str] = Field(None, max_length=200, description="Updated session title")
    session_metadata: Optional[Dict[str, Any]] = Field(None, description="Updated session metadata")


class SessionPublic(SessionBase):
    """Public model for session data returned by API."""
    id: int
    created_at: datetime
    updated_at: datetime
    message_count: int


class SessionWithMessages(SessionPublic):
    """Extended session model that includes messages."""
    messages: List["MessagePublic"] = []


class MessageCreate(MessageBase):
    """Model for creating a new message."""
    session_id: int = Field(description="Session ID where message belongs")


class MessagePublic(MessageBase):
    """Public model for message data returned by API."""
    id: int
    session_id: int
    timestamp: datetime


# Chat-specific models for API interactions

class ChatRequest(SQLModel):
    """Model for chat message requests."""
    message: str = Field(min_length=1, description="User message content")


class ChatResponse(SQLModel):
    """Model for chat response including both user and assistant messages."""
    user_message: MessagePublic
    assistant_message: MessagePublic
    session: SessionPublic


# Update forward references for relationships
SessionWithMessages.model_rebuild()