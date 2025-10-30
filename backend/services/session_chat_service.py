"""
Session-based chat service for Oracle conversational AI.

This service handles chat operations within session context, implementing
intelligent conversation context optimization for token reduction and
integrating with the Gemini API for AI response generation.
"""

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
        
        # Configuration for context optimization
        self.max_context_messages = 20  # Maximum messages to include in context
        self.min_context_messages = 4   # Minimum messages to maintain conversation flow
        self.token_estimate_per_message = 50  # Rough estimate for token calculation
    
    async def send_message(self, session_id: int, message: str) -> ChatResponse:
        """
        Send a message within a session context and get AI response.
        
        This method handles the complete chat flow:
        1. Validates session exists
        2. Stores user message
        3. Retrieves optimized conversation context
        4. Sends to Gemini API with minimal context
        5. Stores assistant response
        6. Updates session metadata
        7. Returns complete chat response
        
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
            
            # 2. Retrieve optimized conversation context first
            conversation_context = await self.get_conversation_context(session_id)
            
            # 3. Send to Gemini API with minimal context
            system_instruction = get_system_instruction()
            chat_session = self.gemini_client.create_chat_session(
                system_instruction=system_instruction
            )
            
            # Build context for API call
            context_messages = []
            for ctx_msg in conversation_context:
                if ctx_msg["role"] == "user":
                    context_messages.append(f"User: {ctx_msg['content']}")
                else:
                    context_messages.append(f"Assistant: {ctx_msg['content']}")
            
            # Create the full prompt with context
            if context_messages:
                context_prompt = "Previous conversation:\n" + "\n".join(context_messages) + f"\n\nUser: {message}"
            else:
                context_prompt = message
            
            # Get AI response
            ai_response = chat_session.send_message(context_prompt)
            
            # 4. Store user message (only after successful API call)
            user_message_data = MessageCreate(
                session_id=session_id,
                role="user",
                content=message.strip(),
                message_metadata={"timestamp": datetime.now(timezone.utc).isoformat()}
            )
            
            user_message = await self.session_service.add_message(user_message_data)
            
            # 5. Store assistant response
            assistant_message_data = MessageCreate(
                session_id=session_id,
                role="assistant",
                content=ai_response,
                message_metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model_used": session.model_used,
                    "context_messages_count": len(conversation_context)
                }
            )
            
            assistant_message = await self.session_service.add_message(assistant_message_data)
            
            # 6. Update session metadata (get current count from database)
            current_message_count = await self.session_service.get_message_count(session_id)
            await self._update_session_metadata(session_id, current_message_count)
            
            # Get updated session info
            updated_session = await self.session_service.get_session(session_id)
            
            # 7. Return complete chat response
            return ChatResponse(
                user_message=user_message,
                assistant_message=assistant_message,
                session=updated_session
            )
            
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to send message: {str(e)}")
    
    async def get_conversation_context(self, session_id: int) -> List[Dict[str, Any]]:
        """
        Retrieve and optimize conversation history for API calls.
        
        This method implements intelligent context selection to minimize token usage
        while maintaining conversation quality. It selects the most relevant recent
        messages and ensures conversation flow is preserved.
        
        Args:
            session_id: Unique identifier of the session
            
        Returns:
            List[Dict[str, Any]]: Optimized conversation context with role and content
            
        Raises:
            ValueError: If session doesn't exist
            RuntimeError: If database operation fails
        """
        try:
            # Get recent messages from the session
            messages = await self.session_service.get_session_messages(
                session_id=session_id,
                limit=self.max_context_messages * 2  # Get more to allow for optimization
            )
            
            if not messages:
                return []
            
            # Convert to context format
            context_messages = []
            for message in messages:
                context_messages.append({
                    "role": message.role,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "id": message.id
                })
            
            # Apply intelligent context optimization
            optimized_context = self._optimize_context(context_messages)
            
            return optimized_context
            
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to get conversation context: {str(e)}")
    
    def _optimize_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply intelligent context optimization to minimize token usage.
        
        This method implements several optimization strategies:
        1. Limit total number of messages
        2. Ensure conversation pairs (user-assistant) are preserved
        3. Prioritize recent messages
        4. Maintain minimum context for conversation flow
        5. Apply content-based filtering for relevance
        6. Preserve conversation coherence
        
        Args:
            messages: Full list of conversation messages
            
        Returns:
            List[Dict[str, Any]]: Optimized context messages
        """
        if not messages:
            return []
        
        # If we have fewer messages than the minimum, return all
        if len(messages) <= self.min_context_messages:
            return messages
        
        # If we have fewer messages than the maximum, return all
        if len(messages) <= self.max_context_messages:
            return messages
        
        # Apply multi-stage optimization
        optimized_messages = self._apply_recency_optimization(messages)
        optimized_messages = self._ensure_conversation_pairs(optimized_messages, messages)
        optimized_messages = self._apply_content_filtering(optimized_messages)
        
        return optimized_messages
    
    def _apply_recency_optimization(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply recency-based optimization to prioritize recent messages.
        
        Args:
            messages: Full list of conversation messages
            
        Returns:
            List[Dict[str, Any]]: Messages optimized for recency
        """
        # Take the most recent messages up to max_context_messages
        return messages[-self.max_context_messages:]
    
    def _ensure_conversation_pairs(self, optimized_messages: List[Dict[str, Any]], 
                                 all_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensure conversation pairs (user-assistant) are preserved for coherence.
        
        Args:
            optimized_messages: Currently optimized message list
            all_messages: Full message history for reference
            
        Returns:
            List[Dict[str, Any]]: Messages with preserved conversation pairs
        """
        if not optimized_messages:
            return optimized_messages
        
        # Ensure we start with a user message if possible
        if optimized_messages[0]["role"] == "assistant":
            # Find the user message that precedes this assistant message
            for i, msg in enumerate(all_messages):
                if msg["id"] == optimized_messages[0]["id"] and i > 0:
                    if all_messages[i-1]["role"] == "user":
                        # Replace the first message with the user message
                        optimized_messages[0] = all_messages[i-1]
                    break
        
        # Ensure we end with a complete pair if possible
        if len(optimized_messages) > 1 and optimized_messages[-1]["role"] == "user":
            # If the last message is from user, try to include the assistant response
            for i, msg in enumerate(all_messages):
                if (msg["id"] == optimized_messages[-1]["id"] and 
                    i < len(all_messages) - 1 and 
                    all_messages[i+1]["role"] == "assistant"):
                    # Add the assistant response if we have room
                    if len(optimized_messages) < self.max_context_messages:
                        optimized_messages.append(all_messages[i+1])
                    break
        
        return optimized_messages
    
    def _apply_content_filtering(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply content-based filtering to maintain conversation quality.
        
        This method filters out very short or repetitive messages that don't
        contribute significantly to conversation context.
        
        Args:
            messages: Messages to filter
            
        Returns:
            List[Dict[str, Any]]: Content-filtered messages
        """
        if len(messages) <= self.min_context_messages:
            return messages
        
        filtered_messages = []
        seen_content = set()
        
        for message in messages:
            content = message["content"].strip().lower()
            
            # Always keep messages if we're under minimum
            if len(filtered_messages) < self.min_context_messages:
                filtered_messages.append(message)
                seen_content.add(content)
                continue
            
            # Skip very short messages (less than 10 characters) when over minimum
            if len(content) < 10:
                continue
            
            # Skip exact duplicates when over minimum
            if content in seen_content:
                continue
            
            filtered_messages.append(message)
            seen_content.add(content)
            
            # Stop if we've reached our target
            if len(filtered_messages) >= self.max_context_messages:
                break
        
        return filtered_messages
    
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
                "last_context_optimization": datetime.now(timezone.utc).isoformat(),
                "estimated_token_savings": self._calculate_token_savings(total_messages)
            })
            
            # Update session with new metadata
            from backend.models.session_models import SessionUpdate
            updates = SessionUpdate(session_metadata=current_metadata)
            await self.session_service.update_session(session_id, updates)
            
        except Exception as e:
            # Log error but don't fail the chat operation
            print(f"Warning: Failed to update session metadata: {str(e)}")
    
    def _calculate_token_savings(self, total_messages: int) -> Dict[str, Any]:
        """
        Calculate estimated token savings from context optimization.
        
        This method estimates the token savings achieved by using server-side
        conversation history instead of sending full history with each request.
        
        Args:
            total_messages: Total number of messages in the conversation
            
        Returns:
            Dict[str, Any]: Token savings statistics
        """
        if total_messages <= self.max_context_messages:
            return {
                "messages_saved": 0,
                "estimated_tokens_saved": 0,
                "optimization_percentage": 0
            }
        
        messages_saved = total_messages - self.max_context_messages
        estimated_tokens_saved = messages_saved * self.token_estimate_per_message
        optimization_percentage = (messages_saved / total_messages) * 100
        
        return {
            "messages_saved": messages_saved,
            "estimated_tokens_saved": estimated_tokens_saved,
            "optimization_percentage": round(optimization_percentage, 2)
        }