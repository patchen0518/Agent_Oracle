"""
Session management service for Oracle chat application.

This service provides CRUD operations for sessions including creation,
retrieval, update, and deletion with proper error handling and validation.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Session, select, desc
from sqlalchemy.exc import SQLAlchemyError

from backend.models.session_models import (
    Session as SessionModel,
    Message as MessageModel,
    SessionCreate,
    SessionUpdate,
    SessionPublic,
    MessagePublic,
    MessageCreate
)


class SessionService:
    """
    Service class for managing chat sessions with CRUD operations.
    
    This service handles all session-related database operations including
    session creation with title generation, retrieval, updates, and deletion
    with proper cascade operations for associated messages.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize the session service with a database session.
        
        Args:
            db_session: SQLModel database session for operations
        """
        self.db = db_session
    
    async def create_session(self, session_data: SessionCreate) -> SessionPublic:
        """
        Create a new chat session with validation and title generation.
        
        Args:
            session_data: Session creation data including title and metadata
            
        Returns:
            SessionPublic: Created session with generated ID and timestamps
            
        Raises:
            ValueError: If session data is invalid
            RuntimeError: If database operation fails
        """
        try:
            # Generate title if not provided
            title = session_data.title
            if not title or title.strip() == "":
                title = self._generate_session_title()
            
            # Create new session instance
            db_session = SessionModel(
                title=title.strip(),
                model_used=session_data.model_used,
                session_metadata=session_data.session_metadata or {}
            )
            
            # Add to database
            self.db.add(db_session)
            self.db.commit()
            self.db.refresh(db_session)
            
            return SessionPublic.model_validate(db_session)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RuntimeError(f"Failed to create session: {str(e)}")
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Invalid session data: {str(e)}")
    
    async def get_session(self, session_id: int) -> Optional[SessionPublic]:
        """
        Retrieve a session by ID with validation.
        
        Args:
            session_id: Unique identifier of the session
            
        Returns:
            SessionPublic: Session data if found, None otherwise
            
        Raises:
            ValueError: If session_id is invalid
            RuntimeError: If database operation fails
        """
        try:
            if session_id <= 0:
                raise ValueError("Session ID must be a positive integer")
            
            statement = select(SessionModel).where(SessionModel.id == session_id)
            session = self.db.exec(statement).first()
            
            if session:
                return SessionPublic.model_validate(session)
            return None
            
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to retrieve session: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Unexpected error retrieving session: {str(e)}")
    
    async def list_sessions(self, limit: int = 50, offset: int = 0) -> List[SessionPublic]:
        """
        List all sessions with proper ordering and pagination support.
        
        Args:
            limit: Maximum number of sessions to return (default: 50)
            offset: Number of sessions to skip for pagination (default: 0)
            
        Returns:
            List[SessionPublic]: List of sessions ordered by updated_at desc
            
        Raises:
            ValueError: If limit or offset parameters are invalid
            RuntimeError: If database operation fails
        """
        try:
            if limit <= 0 or limit > 100:
                raise ValueError("Limit must be between 1 and 100")
            if offset < 0:
                raise ValueError("Offset must be non-negative")
            
            statement = (
                select(SessionModel)
                .order_by(desc(SessionModel.updated_at))
                .offset(offset)
                .limit(limit)
            )
            
            sessions = self.db.exec(statement).all()
            return [SessionPublic.model_validate(session) for session in sessions]
            
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to list sessions: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Unexpected error listing sessions: {str(e)}")
    
    async def update_session(self, session_id: int, updates: SessionUpdate) -> Optional[SessionPublic]:
        """
        Update session metadata and title with validation.
        
        Args:
            session_id: Unique identifier of the session to update
            updates: Session update data containing new title and/or metadata
            
        Returns:
            SessionPublic: Updated session data if found, None if session doesn't exist
            
        Raises:
            ValueError: If session_id or update data is invalid
            RuntimeError: If database operation fails
        """
        try:
            if session_id <= 0:
                raise ValueError("Session ID must be a positive integer")
            
            # Get existing session
            statement = select(SessionModel).where(SessionModel.id == session_id)
            session = self.db.exec(statement).first()
            
            if not session:
                return None
            
            # Apply updates
            update_data = updates.model_dump(exclude_unset=True)
            if not update_data:
                # No updates provided, return current session
                return SessionPublic.model_validate(session)
            
            for field, value in update_data.items():
                if field == "title" and value:
                    session.title = value.strip()
                elif field == "session_metadata" and value is not None:
                    session.session_metadata = value
            
            # Update timestamp
            session.updated_at = datetime.now(timezone.utc)
            
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            return SessionPublic.model_validate(session)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RuntimeError(f"Failed to update session: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"Unexpected error updating session: {str(e)}")
    
    async def delete_session(self, session_id: int) -> bool:
        """
        Delete session and all associated messages with cascade operations.
        
        Args:
            session_id: Unique identifier of the session to delete
            
        Returns:
            bool: True if session was deleted, False if session didn't exist
            
        Raises:
            ValueError: If session_id is invalid
            RuntimeError: If database operation fails
        """
        try:
            if session_id <= 0:
                raise ValueError("Session ID must be a positive integer")
            
            # Get session to delete
            statement = select(SessionModel).where(SessionModel.id == session_id)
            session = self.db.exec(statement).first()
            
            if not session:
                return False
            
            # Delete session (messages will be cascade deleted due to relationship)
            self.db.delete(session)
            self.db.commit()
            
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RuntimeError(f"Failed to delete session: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"Unexpected error deleting session: {str(e)}")
    
    async def get_session_messages(self, session_id: int, limit: int = 100, offset: int = 0) -> List[MessagePublic]:
        """
        Retrieve conversation history for a session with proper ordering.
        
        Args:
            session_id: Unique identifier of the session
            limit: Maximum number of messages to return (default: 100)
            offset: Number of messages to skip for pagination (default: 0)
            
        Returns:
            List[MessagePublic]: List of messages ordered by timestamp asc
            
        Raises:
            ValueError: If session_id, limit, or offset parameters are invalid
            RuntimeError: If database operation fails
        """
        try:
            if session_id <= 0:
                raise ValueError("Session ID must be a positive integer")
            if limit <= 0 or limit > 1000:
                raise ValueError("Limit must be between 1 and 1000")
            if offset < 0:
                raise ValueError("Offset must be non-negative")
            
            # Verify session exists
            session_exists = await self.get_session(session_id)
            if not session_exists:
                raise ValueError(f"Session {session_id} not found")
            
            # Get messages for the session
            statement = (
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.timestamp.asc())
                .offset(offset)
                .limit(limit)
            )
            
            messages = self.db.exec(statement).all()
            return [MessagePublic.model_validate(message) for message in messages]
            
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to retrieve session messages: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Unexpected error retrieving session messages: {str(e)}")
    
    async def add_message(self, message_data: MessageCreate) -> MessagePublic:
        """
        Add a new message to a session with metadata and timestamp management.
        
        Args:
            message_data: Message creation data including session_id, role, and content
            
        Returns:
            MessagePublic: Created message with generated ID and timestamp
            
        Raises:
            ValueError: If message data is invalid or session doesn't exist
            RuntimeError: If database operation fails
        """
        try:
            # Validate session exists
            session_exists = await self.get_session(message_data.session_id)
            if not session_exists:
                raise ValueError(f"Session {message_data.session_id} not found")
            
            # Create new message instance
            db_message = MessageModel(
                session_id=message_data.session_id,
                role=message_data.role,
                content=message_data.content.strip(),
                message_metadata=message_data.message_metadata or {}
            )
            
            # Add message to database
            self.db.add(db_message)
            
            # Update session message count and timestamp
            await self._update_session_after_message(message_data.session_id)
            
            self.db.commit()
            self.db.refresh(db_message)
            
            return MessagePublic.model_validate(db_message)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RuntimeError(f"Failed to add message: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"Unexpected error adding message: {str(e)}")
    
    async def get_message_count(self, session_id: int) -> int:
        """
        Get the total number of messages in a session.
        
        Args:
            session_id: Unique identifier of the session
            
        Returns:
            int: Total number of messages in the session
            
        Raises:
            ValueError: If session_id is invalid
            RuntimeError: If database operation fails
        """
        try:
            if session_id <= 0:
                raise ValueError("Session ID must be a positive integer")
            
            statement = select(MessageModel).where(MessageModel.session_id == session_id)
            messages = self.db.exec(statement).all()
            return len(messages)
            
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to count messages: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Unexpected error counting messages: {str(e)}")
    
    async def _update_session_after_message(self, session_id: int) -> None:
        """
        Update session metadata after adding a message.
        
        This method updates the message count and updated_at timestamp
        for the session after a new message is added.
        
        Args:
            session_id: Unique identifier of the session to update
            
        Raises:
            RuntimeError: If database operation fails
        """
        try:
            statement = select(SessionModel).where(SessionModel.id == session_id)
            session = self.db.exec(statement).first()
            
            if session:
                # Update message count
                message_count = await self.get_message_count(session_id)
                session.message_count = message_count
                session.updated_at = datetime.now(timezone.utc)
                
                self.db.add(session)
                
        except Exception as e:
            raise RuntimeError(f"Failed to update session after message: {str(e)}")
    
    def _generate_session_title(self) -> str:
        """
        Generate a default session title based on current timestamp.
        
        Returns:
            str: Generated session title
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"Chat Session {timestamp}"