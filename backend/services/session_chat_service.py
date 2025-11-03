"""
Session-based chat service for Oracle conversational AI.

This service handles chat operations within session context, implementing
intelligent conversation context optimization for token reduction and
integrating with the Gemini API for AI response generation.
"""

import os
import hashlib
from typing import List, Dict, Any, Optional
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


class SessionChatService:
    """
    Service class for handling chat operations within session context.
    
    This service provides session-aware chat functionality with intelligent
    conversation context optimization to minimize API token usage while
    maintaining conversation quality and coherence.
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
    
    def _use_persistent_sessions(self, session_id: int) -> bool:
        """
        Determine if persistent sessions should be used for this request.
        
        This method implements feature flag logic with gradual rollout capability:
        1. Check if persistent sessions are globally enabled
        2. Apply percentage-based rollout logic using session ID hash
        3. Log feature flag decisions for monitoring
        
        Args:
            session_id: Session ID used for consistent rollout decisions
            
        Returns:
            bool: True if persistent sessions should be used, False otherwise
        """
        # Check global feature flag
        use_persistent = os.getenv("USE_PERSISTENT_SESSIONS", "false").lower() == "true"
        if not use_persistent:
            print(f"Persistent sessions disabled globally for session {session_id}")
            return False
        
        # Apply gradual rollout percentage
        rollout_percentage = int(os.getenv("GRADUAL_ROLLOUT_PERCENTAGE", "0"))
        if rollout_percentage <= 0:
            print(f"Gradual rollout at 0% for session {session_id}")
            return False
        
        if rollout_percentage >= 100:
            print(f"Persistent sessions enabled (100% rollout) for session {session_id}")
            return True
        
        # Use session ID hash for consistent rollout decisions
        session_hash = int(hashlib.md5(str(session_id).encode()).hexdigest(), 16)
        session_percentage = session_hash % 100
        
        enabled = session_percentage < rollout_percentage
        print(f"Gradual rollout decision for session {session_id}: {enabled} (rollout: {rollout_percentage}%, session hash: {session_percentage}%)")
        
        return enabled

    async def send_message(self, session_id: int, message: str) -> ChatResponse:
        """
        Send a message within a session context with feature flag routing.
        
        This method routes to either persistent sessions or stateless implementation
        based on feature flag configuration and gradual rollout settings.
        
        Args:
            session_id: Unique identifier of the session
            message: User message content
            
        Returns:
            ChatResponse: Complete response including user message, assistant response, and session info
            
        Raises:
            ValueError: If session doesn't exist or message is invalid
            RuntimeError: If database or API operations fail
        """
        # Route based on feature flag
        if self._use_persistent_sessions(session_id):
            return await self._send_with_persistent_sessions(session_id, message)
        else:
            return await self._send_with_stateless_implementation(session_id, message)

    async def _send_with_persistent_sessions(self, session_id: int, message: str) -> ChatResponse:
        """
        Send a message using persistent Gemini sessions.
        
        This method handles the complete chat flow with persistent sessions:
        1. Validates session exists
        2. Gets or creates persistent Gemini session
        3. Sends message directly to persistent session
        4. Stores user and assistant messages
        5. Updates session metadata
        6. Returns complete chat response
        
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
            
            # 2. Get or create persistent Gemini session
            system_instruction = get_system_instruction()
            
            # Try persistent session approach with comprehensive error handling
            ai_response = None
            persistent_session_used = True
            
            try:
                chat_session = self.gemini_client.get_or_create_session(
                    session_id=session_id,
                    system_instruction=system_instruction
                )
                
                # 3. Send message directly to persistent session (no manual context!)
                ai_response = chat_session.send_message(message.strip())
                
            except Exception as session_error:
                print(f"Persistent session failed for session {session_id}: {str(session_error)}")
                
                # If session creation fails, attempt recovery from database
                try:
                    chat_session = await self.recover_session_from_database(
                        session_id=session_id,
                        system_instruction=system_instruction
                    )
                    # Add recovered session to cache
                    now = datetime.now()
                    self.gemini_client.active_sessions[session_id] = (chat_session, now, now)
                    self.gemini_client.sessions_recovered += 1
                    
                    # Try sending message with recovered session
                    ai_response = chat_session.send_message(message.strip())
                    print(f"Session recovery successful for session {session_id}")
                    
                except Exception as recovery_error:
                    print(f"Session recovery failed for session {session_id}: {str(recovery_error)}")
                    
                    # Ultimate fallback: use stateless implementation
                    try:
                        ai_response = await self._send_with_stateless_fallback(session_id, message.strip())
                        persistent_session_used = False
                        print(f"Fallback to stateless mode successful for session {session_id}")
                        
                    except Exception as fallback_error:
                        # All approaches failed, raise comprehensive error
                        raise RuntimeError(
                            f"All session approaches failed for session {session_id}. "
                            f"Persistent session error: {str(session_error)}. "
                            f"Recovery error: {str(recovery_error)}. "
                            f"Fallback error: {str(fallback_error)}"
                        )
            
            # 4. Store user message (only after successful AI response)
            try:
                user_message_data = MessageCreate(
                    session_id=session_id,
                    role="user",
                    content=message.strip(),
                    message_metadata={"timestamp": datetime.now(timezone.utc).isoformat()}
                )
                
                user_message = await self.session_service.add_message(user_message_data)
            except Exception as db_error:
                print(f"Warning: Failed to store user message for session {session_id}: {str(db_error)}")
                # Continue with a placeholder message to maintain flow
                user_message = None
            
            # 5. Store assistant response
            try:
                assistant_message_data = MessageCreate(
                    session_id=session_id,
                    role="assistant",
                    content=ai_response,
                    message_metadata={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "model_used": session.model_used,
                        "persistent_session": persistent_session_used
                    }
                )
                
                assistant_message = await self.session_service.add_message(assistant_message_data)
            except Exception as db_error:
                print(f"Warning: Failed to store assistant message for session {session_id}: {str(db_error)}")
                # Continue with a placeholder message to maintain flow
                assistant_message = None
            
            # 6. Update session metadata (get current count from database)
            try:
                current_message_count = await self.session_service.get_message_count(session_id)
                await self._update_session_metadata(session_id, current_message_count)
            except Exception as metadata_error:
                print(f"Warning: Failed to update session metadata for session {session_id}: {str(metadata_error)}")
                # Continue without metadata update
            
            # Get updated session info
            try:
                updated_session = await self.session_service.get_session(session_id)
            except Exception as session_error:
                print(f"Warning: Failed to get updated session info for session {session_id}: {str(session_error)}")
                updated_session = session  # Use original session info
            
            # 7. Return complete chat response (even if some database operations failed)
            # Create placeholder messages if database storage failed
            if user_message is None:
                user_message = MessagePublic(
                    id=0,
                    session_id=session_id,
                    role="user",
                    content=message.strip(),
                    timestamp=datetime.now(timezone.utc),
                    message_metadata={"timestamp": datetime.now(timezone.utc).isoformat()}
                )
            
            if assistant_message is None:
                assistant_message = MessagePublic(
                    id=0,
                    session_id=session_id,
                    role="assistant",
                    content=ai_response,
                    timestamp=datetime.now(timezone.utc),
                    message_metadata={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "model_used": session.model_used,
                        "persistent_session": persistent_session_used
                    }
                )
            
            return ChatResponse(
                user_message=user_message,
                assistant_message=assistant_message,
                session=updated_session
            )
            
        except ValueError:
            raise
        except Exception as e:
            # Log detailed error context for debugging
            print(f"Critical error in send_message for session {session_id}: {str(e)}")
            print(f"Message content length: {len(message) if message else 0}")
            print(f"Session service available: {self.session_service is not None}")
            print(f"Gemini client available: {self.gemini_client is not None}")
            raise RuntimeError(f"Failed to send message: {str(e)}")
    
    async def recover_session_from_database(self, session_id: int, system_instruction: str) -> "ChatSession":
        """
        Rebuild Gemini session from database message history for cache miss scenarios.
        
        This method reconstructs a persistent Gemini session by replaying the conversation
        history from the database. It creates a fresh session and sends historical messages
        to rebuild the proper conversation context.
        
        Args:
            session_id: The session ID to recover
            system_instruction: System instruction for the new session
            
        Returns:
            ChatSession: Recovered session with conversation history rebuilt
            
        Raises:
            ValueError: If session doesn't exist in database
            RuntimeError: If recovery fails due to API or database errors
        """
        try:
            # 1. Validate session exists in database
            session = await self.session_service.get_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found in database")
            
            # 2. Get recent messages from database (limit to last 50 for performance)
            messages = await self.session_service.get_session_messages(
                session_id=session_id,
                limit=50  # Last 50 messages for context
            )
            
            if not messages:
                # No history to recover, create fresh session
                return self.gemini_client._create_fresh_session(session_id, system_instruction)
            
            # 3. Create fresh Gemini session
            chat_session = self.gemini_client._create_fresh_session(session_id, system_instruction)
            
            # 4. Rebuild conversation history in proper Gemini format
            # Process messages in chronological order to maintain conversation flow
            recovered_messages = 0
            for i in range(0, len(messages), 2):
                if i < len(messages) and messages[i].role == "user":
                    user_msg = messages[i].content
                    
                    try:
                        # Send user message to rebuild history
                        response = chat_session.send_message(user_msg)
                        recovered_messages += 1
                        
                        # Optional: Verify assistant response matches database for consistency
                        if i + 1 < len(messages) and messages[i + 1].role == "assistant":
                            expected_response = messages[i + 1].content
                            # Log discrepancies for monitoring (but don't fail recovery)
                            if response.strip() != expected_response.strip():
                                print(f"Warning: Recovery response mismatch for session {session_id}, message pair {i//2 + 1}")
                    
                    except Exception as msg_error:
                        # Log individual message errors but continue recovery
                        print(f"Warning: Failed to recover message {i} for session {session_id}: {str(msg_error)}")
                        # If we can't recover early messages, we can still use the session
                        continue
            
            # 5. Update recovery statistics
            self.gemini_client.sessions_recovered += 1
            
            print(f"Successfully recovered session {session_id} with {recovered_messages} message pairs from {len(messages)} total messages")
            return chat_session
            
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to recover session {session_id} from database: {str(e)}")
    
    async def _send_with_stateless_fallback(self, session_id: int, message: str) -> str:
        """
        Fallback to current stateless implementation when persistent sessions fail.
        
        This method provides graceful degradation by using the original approach
        of creating a fresh session and manually building context from database.
        
        Args:
            session_id: The session ID
            message: User message content
            
        Returns:
            str: AI response from stateless session
            
        Raises:
            RuntimeError: If fallback also fails
        """
        try:
            print(f"Using stateless fallback for session {session_id}")
            
            # Get system instruction
            system_instruction = get_system_instruction()
            
            # Create temporary session (original behavior)
            chat_session = self.gemini_client.create_chat_session(system_instruction)
            
            # Get recent messages for context (simplified version)
            messages = await self.session_service.get_session_messages(
                session_id=session_id,
                limit=10  # Limit context for fallback
            )
            
            # Build context manually (original behavior)
            context_messages = []
            for msg in messages:
                if msg.role == "user":
                    context_messages.append(f"User: {msg.content}")
                else:
                    context_messages.append(f"Assistant: {msg.content}")
            
            # Create the full prompt with context
            if context_messages:
                context_prompt = "Previous conversation:\n" + "\n".join(context_messages) + f"\n\nUser: {message}"
            else:
                context_prompt = message
            
            # Send with manual context
            ai_response = chat_session.send_message(context_prompt)
            
            print(f"Stateless fallback successful for session {session_id}")
            return ai_response
            
        except Exception as e:
            raise RuntimeError(f"Stateless fallback also failed for session {session_id}: {str(e)}")
    
    async def _update_session_metadata(self, session_id: int, total_messages: int) -> None:
        """
        Update session metadata after chat operations.
        
        This method updates session metadata to track usage patterns,
        performance metrics, and conversation statistics for analytics.
        
        Args:
            session_id: Unique identifier of the session
            total_messages: Total number of messages in the conversation
            
        Raises:
            RuntimeError: If database operation fails
        """
        try:
            session = await self.session_service.get_session(session_id)
            if not session:
                return
            
            # Calculate usage metrics
            current_metadata = session.session_metadata or {}
            
            # Update conversation statistics
            current_metadata.update({
                "last_activity": datetime.now(timezone.utc).isoformat(),
                "total_messages": total_messages,
                "persistent_sessions_enabled": True
            })
            
            # Update session with new metadata
            from backend.models.session_models import SessionUpdate
            updates = SessionUpdate(session_metadata=current_metadata)
            await self.session_service.update_session(session_id, updates)
            
        except Exception as e:
            # Log error but don't fail the chat operation
            print(f"Warning: Failed to update session metadata: {str(e)}")

    async def _send_with_stateless_implementation(self, session_id: int, message: str) -> ChatResponse:
        """
        Send a message using the current stateless implementation.
        
        This method provides the original behavior when persistent sessions are disabled:
        1. Creates a fresh Gemini session for each message
        2. Manually builds conversation context from database
        3. Sends message with reconstructed context
        4. Stores messages and updates session metadata
        
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
            
            # 2. Get system instruction and create fresh session
            system_instruction = get_system_instruction()
            chat_session = self.gemini_client.create_chat_session(system_instruction)
            
            # 3. Build conversation context from database
            messages = await self.session_service.get_session_messages(
                session_id=session_id,
                limit=20  # Reasonable context limit for stateless mode
            )
            
            # Build context manually (original behavior)
            context_messages = []
            for msg in messages:
                if msg.role == "user":
                    context_messages.append(f"User: {msg.content}")
                else:
                    context_messages.append(f"Assistant: {msg.content}")
            
            # Create the full prompt with context
            if context_messages:
                context_prompt = "Previous conversation:\n" + "\n".join(context_messages) + f"\n\nUser: {message.strip()}"
            else:
                context_prompt = message.strip()
            
            # 4. Send message with manual context
            ai_response = chat_session.send_message(context_prompt)
            
            # 5. Store user message
            user_message_data = MessageCreate(
                session_id=session_id,
                role="user",
                content=message.strip(),
                message_metadata={"timestamp": datetime.now(timezone.utc).isoformat()}
            )
            
            user_message = await self.session_service.add_message(user_message_data)
            
            # 6. Store assistant response
            assistant_message_data = MessageCreate(
                session_id=session_id,
                role="assistant",
                content=ai_response,
                message_metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model_used": session.model_used,
                    "persistent_session": False
                }
            )
            
            assistant_message = await self.session_service.add_message(assistant_message_data)
            
            # 7. Update session metadata
            current_message_count = await self.session_service.get_message_count(session_id)
            await self._update_session_metadata(session_id, current_message_count)
            
            # Get updated session info
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
            print(f"Error in stateless implementation for session {session_id}: {str(e)}")
            raise RuntimeError(f"Failed to send message with stateless implementation: {str(e)}")