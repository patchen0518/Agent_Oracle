"""
Session-based chat service for Oracle conversational AI.

This service handles chat operations within session context, properly leveraging
Gemini's native conversation management instead of manually reconstructing context.
"""

from typing import Optional
from sqlmodel import Session
from datetime import datetime, timezone

from backend.services.gemini_client import GeminiClient
from backend.services.session_service import SessionService
from backend.models.session_models import (
    MessageCreate,
    MessagePublic,
    SessionPublic,
    ChatRequest,
    ChatResponse
)
from backend.config.system_instructions import get_system_instruction
from backend.utils.logging_config import get_logger


class SessionChatService:
    """
    Service class for handling chat operations within session context.
    
    Leverages Gemini's native conversation management - each session maintains
    its own conversation history automatically without manual context reconstruction.
    """
    
    def __init__(self, db_session: Session, gemini_client: GeminiClient):
        """
        Initialize the session chat service.
        
        Args:
            db_session: SQLModel database session for operations
            gemini_client: Gemini API client for AI response generation
        """
        self.db = db_session
        self.gemini_client = gemini_client
        self.session_service = SessionService(db_session)
        self.logger = get_logger("session_chat_service")
    
    async def send_message(self, session_id: int, message: str) -> ChatResponse:
        """
        Send a message within a session context using Gemini's native conversation management.
        
        This method leverages Gemini's built-in conversation history instead of
        manually reconstructing context, making it much simpler and more efficient.
        
        Args:
            session_id: Unique identifier of the session
            message: User message content
            
        Returns:
            ChatResponse: Complete response including user message, assistant response, and session info
            
        Raises:
            ValueError: If session doesn't exist or message is invalid
            RuntimeError: If database or API operations fail
        """
        try:
            # 1. Validate session exists
            session = await self.session_service.get_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Validate message content
            if not message or not message.strip():
                raise ValueError("Message content cannot be empty")
            
            # 2. Get conversation history from database for context restoration
            existing_messages = await self.session_service.get_session_messages(session_id)
            
            # Convert database messages to format expected by Gemini client
            conversation_history = []
            for msg in existing_messages:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 3. Get or create Gemini chat session with restored conversation history
            system_instruction = get_system_instruction()
            chat_session = self.gemini_client.get_or_create_session(
                session_id=session_id,
                system_instruction=system_instruction,
                conversation_history=conversation_history if conversation_history else None
            )
            
            # 4. Send message directly to Gemini session
            # Gemini automatically maintains conversation context with restored history!
            ai_response = chat_session.send_message(message.strip())
            
            # 5. Store user message in database for persistence
            user_message_data = MessageCreate(
                session_id=session_id,
                role="user",
                content=message.strip(),
                message_metadata={"timestamp": datetime.now(timezone.utc).isoformat()}
            )
            user_message = await self.session_service.add_message(user_message_data)
            
            # 6. Store assistant response in database
            assistant_message_data = MessageCreate(
                session_id=session_id,
                role="assistant",
                content=ai_response,
                message_metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model_used": session.model_used
                }
            )
            assistant_message = await self.session_service.add_message(assistant_message_data)
            
            # 7. Get updated session info
            updated_session = await self.session_service.get_session(session_id)
            
            # 8. Return complete chat response
            return ChatResponse(
                user_message=user_message,
                assistant_message=assistant_message,
                session=updated_session
            )
            
        except ValueError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to send message for session {session_id}: {str(e)}")
            raise RuntimeError(f"Failed to send message: {str(e)}")