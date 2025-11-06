"""
Session-based chat service for Oracle conversational AI.

This service handles chat operations within session context, leveraging
LangChain's ChatGoogleGenerativeAI with intelligent memory management
instead of manually reconstructing context.
"""

from typing import Optional
from sqlmodel import Session
from datetime import datetime, timezone

from backend.services.langchain_client import LangChainClient
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
from backend.exceptions import (
    ValidationError,
    NotFoundError,
    AIServiceError,
    DatabaseError
)


class SessionChatService:
    """
    Service class for handling chat operations within session context.
    
    Leverages LangChain's ChatGoogleGenerativeAI with intelligent memory management -
    each session maintains its own conversation history with smart context optimization.
    """
    
    def __init__(self, db_session: Session, langchain_client: LangChainClient):
        """
        Initialize the session chat service.
        
        Args:
            db_session: SQLModel database session for operations
            langchain_client: LangChain client for AI response generation
        """
        self.db = db_session
        self.langchain_client = langchain_client
        self.session_service = SessionService(db_session)
        self.logger = get_logger("session_chat_service")
    
    async def send_message(self, session_id: int, message: str) -> ChatResponse:
        """
        Send a message within a session context using LangChain with intelligent memory management.
        
        This method uses recent message context for efficient session restoration
        while maintaining conversation continuity through LangChain's memory strategies.
        
        Args:
            session_id: Unique identifier of the session
            message: User message content
            
        Returns:
            ChatResponse: Complete response including user message, assistant response, and session info
            
        Raises:
            ValidationError: If message is invalid
            NotFoundError: If session doesn't exist
            AIServiceError: If AI service operations fail
            DatabaseError: If database operations fail
        """
        try:
            # 1. Validate session exists
            session = await self.session_service.get_session(session_id)
            if not session:
                raise NotFoundError(f"Session {session_id} not found")
            
            # Validate message content
            if not message or not message.strip():
                raise ValidationError("Message content cannot be empty")
            
            # 2. Get recent messages for context restoration with intelligent selection
            recent_messages = await self._get_messages_for_context_restoration(session_id)
            
            # Convert database messages to format expected by Gemini client
            conversation_history = []
            for msg in recent_messages:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 3. Get or create LangChain chat session with recent conversation history
            system_instruction = get_system_instruction()
            try:
                chat_session = self.langchain_client.get_or_create_session(
                    session_id=session_id,
                    system_instruction=system_instruction,
                    recent_messages=conversation_history if conversation_history else None
                )
            except Exception as e:
                raise AIServiceError(f"Failed to create or retrieve chat session: {str(e)}", e)
            
            # 4. Store user message in database FIRST for guaranteed persistence
            user_message_data = MessageCreate(
                session_id=session_id,
                role="user",
                content=message.strip(),
                message_metadata={"timestamp": datetime.now(timezone.utc).isoformat()}
            )
            user_message = await self.session_service.add_message(user_message_data)
            
            # 5. Send message to LangChain session with hybrid persistence handling
            ai_response = None
            memory_operation_failed = False
            
            try:
                ai_response = chat_session.send_message(message.strip())
            except Exception as e:
                memory_operation_failed = True
                self.logger.warning(
                    f"LangChain memory operation failed for session {session_id}: {str(e)}. "
                    "Attempting fallback to direct model call."
                )
                
                # Fallback: try direct model call without memory context
                try:
                    ai_response = await self._fallback_direct_model_call(message.strip(), session)
                except Exception as fallback_error:
                    raise AIServiceError(f"Both LangChain and fallback failed: {str(e)} | {str(fallback_error)}", e)
            
            # 6. Store assistant response in database (guaranteed persistence)
            assistant_message_data = MessageCreate(
                session_id=session_id,
                role="assistant",
                content=ai_response,
                message_metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model_used": session.model_used,
                    "memory_operation_failed": memory_operation_failed
                }
            )
            assistant_message = await self.session_service.add_message(assistant_message_data)
            
            # 7. Attempt to synchronize memory with database if memory operation failed
            if memory_operation_failed:
                await self._attempt_memory_synchronization(session_id, chat_session)
            
            # 8. Get updated session info
            updated_session = await self.session_service.get_session(session_id)
            
            # 9. Return complete chat response
            return ChatResponse(
                user_message=user_message,
                assistant_message=assistant_message,
                session=updated_session
            )
            
        except (ValidationError, NotFoundError, AIServiceError, DatabaseError):
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending message for session {session_id}: {str(e)}")
            raise DatabaseError(f"Failed to send message: {str(e)}")
    
    async def _get_messages_for_context_restoration(self, session_id: int, max_messages: int = 30) -> List[dict]:
        """
        Get messages from database for context restoration with intelligent selection.
        
        Loads recent messages efficiently and converts them to the format expected
        by LangChain memory restoration.
        
        Args:
            session_id: The session ID to load messages for
            max_messages: Maximum number of messages to load (default: 30)
            
        Returns:
            List of message dictionaries in format expected by LangChain restoration
        """
        try:
            # Get recent messages from database
            recent_messages = await self.session_service.get_recent_messages(
                session_id, 
                limit=max_messages
            )
            
            if not recent_messages:
                self.logger.debug(f"No recent messages found for session {session_id}")
                return []
            
            # Convert database message objects to dictionaries for LangChain restoration
            conversation_history = []
            for msg in recent_messages:
                # Ensure we have the required fields
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    message_dict = {
                        "role": msg.role,
                        "content": msg.content
                    }
                    
                    # Add optional metadata if available
                    if hasattr(msg, 'message_metadata') and msg.message_metadata:
                        message_dict["metadata"] = msg.message_metadata
                    
                    conversation_history.append(message_dict)
            
            self.logger.debug(
                f"Loaded {len(conversation_history)} messages for context restoration "
                f"in session {session_id}"
            )
            
            return conversation_history
            
        except Exception as e:
            self.logger.warning(
                f"Failed to load messages for context restoration in session {session_id}: {str(e)}"
            )
            # Return empty list to allow session to continue without context
            return []
    
    async def restore_session_memory(self, session_id: int) -> bool:
        """
        Restore memory for an existing session from database messages.
        
        This method can be used to restore memory for sessions that have been
        inactive and need their context restored from persistent storage.
        
        Args:
            session_id: The session ID to restore memory for
            
        Returns:
            bool: True if memory restoration was successful, False otherwise
        """
        try:
            # Check if session exists
            session = await self.session_service.get_session(session_id)
            if not session:
                self.logger.warning(f"Cannot restore memory: session {session_id} not found")
                return False
            
            # Get the LangChain chat session if it exists
            chat_session = self.langchain_client.active_sessions.get(session_id)
            if not chat_session:
                self.logger.debug(f"No active chat session found for {session_id}, creating new one")
                
                # Create new session with memory restoration
                system_instruction = get_system_instruction()
                recent_messages = await self._get_messages_for_context_restoration(session_id)
                
                chat_session = self.langchain_client.get_or_create_session(
                    session_id=session_id,
                    system_instruction=system_instruction,
                    recent_messages=recent_messages
                )
                
                return True
            else:
                # Restore memory for existing session
                recent_messages = await self._get_messages_for_context_restoration(session_id)
                
                if recent_messages:
                    # Clear existing context and restore from database
                    chat_session.clear_history()
                    
                    # Re-apply system instruction if needed
                    system_instruction = get_system_instruction()
                    if system_instruction:
                        chat_session._process_system_instruction(system_instruction)
                    
                    # Restore context from database
                    chat_session.restore_context(recent_messages)
                    
                    self.logger.info(f"Successfully restored memory for session {session_id}")
                    return True
                else:
                    self.logger.debug(f"No messages to restore for session {session_id}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to restore session memory for {session_id}: {str(e)}")
            return False
    
    async def _fallback_direct_model_call(self, message: str, session) -> str:
        """
        Fallback method for direct model call when LangChain memory operations fail.
        
        Creates a temporary LangChain session without memory to get a response,
        ensuring the user still gets an AI response even if memory operations fail.
        
        Args:
            message: The user message to send
            session: The session object for context
            
        Returns:
            str: AI response from direct model call
        """
        try:
            # Create a temporary standalone chat session without memory
            system_instruction = get_system_instruction()
            temp_chat_session = self.langchain_client.create_chat_session(
                system_instruction=system_instruction
            )
            
            # Send message to temporary session
            response = temp_chat_session.send_message(message)
            
            self.logger.info(f"Fallback direct model call successful for session {session.id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Fallback direct model call failed for session {session.id}: {str(e)}")
            raise AIServiceError(f"Fallback model call failed: {str(e)}", e)
    
    async def _attempt_memory_synchronization(self, session_id: int, chat_session) -> None:
        """
        Attempt to synchronize LangChain memory with database state.
        
        This method tries to restore the memory state from the database
        when memory operations have failed, ensuring consistency between
        memory and persistent storage.
        
        Args:
            session_id: The session ID to synchronize
            chat_session: The LangChain chat session to synchronize
        """
        try:
            self.logger.info(f"Attempting memory synchronization for session {session_id}")
            
            # Get recent messages from database
            recent_messages = await self._get_messages_for_context_restoration(session_id, max_messages=20)
            
            if recent_messages:
                # Clear the potentially corrupted memory state
                chat_session.clear_history()
                
                # Re-apply system instruction
                system_instruction = get_system_instruction()
                if system_instruction:
                    chat_session._process_system_instruction(system_instruction)
                
                # Restore context from database
                chat_session.restore_context(recent_messages)
                
                self.logger.info(f"Memory synchronization successful for session {session_id}")
            else:
                self.logger.debug(f"No messages to synchronize for session {session_id}")
                
        except Exception as e:
            self.logger.warning(f"Memory synchronization failed for session {session_id}: {str(e)}")
            # Don't raise exception - the database persistence is still intact
    
    async def ensure_memory_database_consistency(self, session_id: int) -> bool:
        """
        Ensure consistency between LangChain memory and database persistence.
        
        This method checks if the memory state matches the database state
        and attempts to fix any inconsistencies.
        
        Args:
            session_id: The session ID to check consistency for
            
        Returns:
            bool: True if consistency is ensured, False if issues remain
        """
        try:
            # Get the active chat session
            chat_session = self.langchain_client.active_sessions.get(session_id)
            if not chat_session:
                self.logger.debug(f"No active chat session for {session_id}, consistency check skipped")
                return True
            
            # Get memory state
            memory_history = chat_session.get_history()
            memory_message_count = len(memory_history)
            
            # Get database state
            db_messages = await self._get_messages_for_context_restoration(session_id, max_messages=50)
            db_message_count = len(db_messages)
            
            # Check for significant discrepancies
            if abs(memory_message_count - db_message_count) > 5:  # Allow some difference due to optimization
                self.logger.warning(
                    f"Memory-database inconsistency detected for session {session_id}: "
                    f"memory={memory_message_count}, database={db_message_count}"
                )
                
                # Attempt to synchronize
                await self._attempt_memory_synchronization(session_id, chat_session)
                return True
            
            self.logger.debug(f"Memory-database consistency verified for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to ensure memory-database consistency for session {session_id}: {str(e)}")
            return False
    
    async def get_hybrid_session_stats(self, session_id: int) -> Dict[str, Any]:
        """
        Get statistics about hybrid memory-database persistence for a session.
        
        Args:
            session_id: The session ID to get stats for
            
        Returns:
            Dictionary containing hybrid persistence statistics
        """
        try:
            stats = {
                "session_id": session_id,
                "database_messages": 0,
                "memory_messages": 0,
                "memory_active": False,
                "consistency_status": "unknown"
            }
            
            # Get database message count
            db_messages = await self.session_service.get_session_messages(session_id, limit=1000)
            stats["database_messages"] = len(db_messages)
            
            # Get memory state if session is active
            chat_session = self.langchain_client.active_sessions.get(session_id)
            if chat_session:
                stats["memory_active"] = True
                memory_history = chat_session.get_history()
                stats["memory_messages"] = len(memory_history)
                
                # Check consistency
                consistency_ok = await self.ensure_memory_database_consistency(session_id)
                stats["consistency_status"] = "consistent" if consistency_ok else "inconsistent"
                
                # Add optimization stats if available
                if hasattr(chat_session, 'get_optimization_stats'):
                    stats["optimization"] = chat_session.get_optimization_stats()
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get hybrid session stats for {session_id}: {str(e)}")
            return {"session_id": session_id, "error": str(e)}