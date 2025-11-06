"""
LangChain chat session wrapper for conversation management.

Provides methods for sending messages, managing history, and handling
responses using LangChain's message system and ChatGoogleGenerativeAI.
Includes comprehensive system instruction handling compatible with existing
system instruction types.
"""

from typing import Optional, List, Dict, Iterator, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.exceptions import LangChainException

from backend.utils.logging_config import get_logger
from backend.exceptions import (
    AIServiceError,
    LangChainError,
    MessageProcessingError,
    LangChainExceptionMapper,
    handle_langchain_exception
)
from backend.config.system_instructions import get_system_instruction, SYSTEM_INSTRUCTIONS
from backend.services.context_optimizer import ContextOptimizer, ContextConfig, SummarizationMiddleware
from backend.services.memory_fallback import MemoryFallbackManager, FallbackConfig, MemoryOperationWrapper


class LangChainChatSession:
    """
    Wrapper for LangChain chat session with conversation management.
    
    Provides methods for sending messages, managing history, and handling
    responses using LangChain's message objects and ChatGoogleGenerativeAI.
    """
    
    def __init__(
        self, 
        chat_model: ChatGoogleGenerativeAI, 
        session_id: Optional[int] = None, 
        system_instruction: Optional[str] = None,
        context_optimizer: Optional[ContextOptimizer] = None
    ):
        """
        Initialize LangChain chat session wrapper.
        
        Args:
            chat_model: The ChatGoogleGenerativeAI instance
            session_id: Optional session ID for tracking
            system_instruction: Optional system instruction for AI personality.
                              Can be a full instruction text or a type name (e.g., "professional", "technical")
            context_optimizer: Optional context optimizer for intelligent context management
        """
        self.chat_model = chat_model
        self.session_id = session_id
        self.logger = get_logger("langchain_chat_session")
        
        # Initialize context optimizer
        if context_optimizer:
            self.context_optimizer = context_optimizer
        else:
            # Create default context optimizer
            context_config = ContextConfig()
            self.context_optimizer = ContextOptimizer(config=context_config, session_id=session_id)
        
        # Initialize summarization middleware
        self.summarization_middleware = SummarizationMiddleware(self.context_optimizer)
        
        # Initialize memory fallback manager
        fallback_config = FallbackConfig()
        self.fallback_manager = MemoryFallbackManager(session_id=session_id, config=fallback_config)
        
        # Initialize conversation history with system message if provided
        self.conversation_history: List[BaseMessage] = []
        
        if system_instruction:
            self._process_system_instruction(system_instruction)
            self.logger.debug(f"Added system instruction to session {session_id}")
        
        self.logger.info(f"LangChain chat session initialized with context optimization for session {session_id}")
    
    def send_message(self, message: str) -> str:
        """
        Send a message to the chat session and get response with context optimization and fallback support.
        
        Args:
            message: The user message to send
            
        Returns:
            str: The model's response text
            
        Raises:
            AIServiceError: If the API call fails
        """
        try:
            # Create human message
            human_message = HumanMessage(content=message)
            
            # Add to conversation history with fallback support
            self._add_message_with_fallback(human_message)
            
            # Apply context optimization through summarization middleware with fallback
            optimized_context = self._get_optimized_context_with_fallback()
            
            # Get response from model using optimized context
            response = self.chat_model.invoke(optimized_context)
            
            # Add AI response to conversation history with fallback support
            ai_message = AIMessage(content=response.content)
            self._add_message_with_fallback(ai_message)
            
            self.logger.debug(
                f"Session {self.session_id}: Sent message and received response "
                f"(context: {len(self.conversation_history)} -> {len(optimized_context)} messages)"
            )
            
            return response.content
            
        except LangChainException as e:
            self.logger.error(f"LangChain error in session {self.session_id}: {str(e)}")
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                f"Failed to send message in session {self.session_id}",
                session_id=self.session_id
            )
            raise mapped_error
        except Exception as e:
            self.logger.error(f"Failed to send message in session {self.session_id}: {str(e)}")
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                f"Failed to send message in session {self.session_id}",
                session_id=self.session_id
            )
            raise mapped_error
    
    def send_message_stream(self, message: str) -> Iterator[str]:
        """
        Send a message and get streaming response with context optimization and fallback support.
        
        Args:
            message: The user message to send
            
        Yields:
            str: Chunks of the model's response as they arrive
            
        Raises:
            AIServiceError: If the API call fails
        """
        try:
            # Create human message
            human_message = HumanMessage(content=message)
            
            # Add to conversation history with fallback support
            self._add_message_with_fallback(human_message)
            
            # Apply context optimization through summarization middleware with fallback
            optimized_context = self._get_optimized_context_with_fallback()
            
            # Stream response from model using optimized context
            response_content = ""
            for chunk in self.chat_model.stream(optimized_context):
                chunk_content = chunk.content
                response_content += chunk_content
                yield chunk_content
            
            # Add complete AI response to conversation history with fallback support
            ai_message = AIMessage(content=response_content)
            self._add_message_with_fallback(ai_message)
            
            self.logger.debug(
                f"Session {self.session_id}: Sent streaming message and received response "
                f"(context: {len(self.conversation_history)} -> {len(optimized_context)} messages)"
            )
            
        except LangChainException as e:
            self.logger.error(f"LangChain streaming error in session {self.session_id}: {str(e)}")
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                f"Failed to send streaming message in session {self.session_id}",
                session_id=self.session_id
            )
            raise mapped_error
        except Exception as e:
            self.logger.error(f"Failed to send streaming message in session {self.session_id}: {str(e)}")
            mapped_error = LangChainExceptionMapper.map_langchain_exception(
                e,
                f"Failed to send streaming message in session {self.session_id}",
                session_id=self.session_id
            )
            raise mapped_error
    
    def get_conversation_history(self) -> List[BaseMessage]:
        """
        Get the conversation history as LangChain message objects.
        
        Returns:
            List[BaseMessage]: List of LangChain message objects in the conversation
        """
        return self.conversation_history.copy()
    
    def get_history(self) -> List[Dict[str, str]]:
        """
        Get the conversation history in dictionary format (compatible with GeminiClient).
        
        Returns:
            List[Dict[str, str]]: List of messages as dictionaries with 'role' and 'content' keys
        """
        history = []
        
        for message in self.conversation_history:
            # Skip system messages in history output (they're applied at session level)
            if isinstance(message, SystemMessage):
                continue
                
            # Convert LangChain message to dictionary format
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                continue  # Skip unknown message types
            
            history.append({
                "role": role,
                "content": message.content
            })
        
        return history
    
    def restore_context(self, messages: List[Dict[str, str]]) -> None:
        """
        Restore conversation context from database message dictionaries with fallback support.
        
        Efficiently converts database message format to LangChain message objects
        with intelligent context selection and memory optimization.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                     Expected format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        try:
            if not messages:
                self.logger.debug(f"Session {self.session_id}: No messages to restore")
                return
            
            # Use fallback-enabled restore context
            success = self._restore_context_with_fallback(messages)
            
            if success:
                self.logger.info(
                    f"Session {self.session_id}: Successfully restored context from {len(messages)} "
                    f"database messages (final context: {len(self.conversation_history)} messages)"
                )
            else:
                self.logger.warning(
                    f"Session {self.session_id}: Context restoration failed, continuing with empty context"
                )
            
        except Exception as e:
            self.logger.warning(f"Failed to restore context for session {self.session_id}: {str(e)}")
            # Continue without restored context - session will still work
    
    def _select_messages_for_restoration(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Intelligently select messages for context restoration.
        
        Uses context optimizer to determine which messages are most relevant
        for restoration while maintaining conversation continuity.
        
        Args:
            messages: All available database messages
            
        Returns:
            List of selected messages for restoration
        """
        if not messages:
            return []
        
        # For initial implementation, use recent messages with smart limits
        # This can be enhanced with semantic relevance scoring later
        
        # Get context optimizer limits
        max_messages = self.context_optimizer.config.messages_to_keep_after_summary
        max_tokens = self.context_optimizer.config.max_tokens_before_summary
        
        # Start with recent messages and work backwards
        selected_messages = []
        estimated_tokens = 0
        
        for message in reversed(messages):
            # Estimate token usage for this message
            content = message.get("content", "")
            message_tokens = self.context_optimizer.calculate_token_usage([
                self._convert_database_message_to_langchain(message)
            ]) if content else 0
            
            # Check if adding this message would exceed limits
            if (len(selected_messages) >= max_messages or 
                estimated_tokens + message_tokens > max_tokens * 0.8):  # Leave 20% buffer
                break
            
            selected_messages.insert(0, message)  # Insert at beginning to maintain order
            estimated_tokens += message_tokens
        
        self.logger.debug(
            f"Session {self.session_id}: Selected {len(selected_messages)} messages "
            f"from {len(messages)} for restoration (estimated tokens: {estimated_tokens})"
        )
        
        return selected_messages
    
    def _convert_database_message_to_langchain(self, message: Dict[str, str]) -> Optional[BaseMessage]:
        """
        Convert a database message dictionary to a LangChain message object.
        
        Args:
            message: Database message dictionary with 'role' and 'content' keys
            
        Returns:
            LangChain message object or None if conversion fails
        """
        try:
            role = message.get("role", "").lower().strip()
            content = message.get("content", "").strip()
            
            if not content:
                self.logger.debug(f"Session {self.session_id}: Skipping empty message content")
                return None
            
            # Convert based on role
            if role == "user":
                return HumanMessage(content=content)
            elif role == "assistant":
                return AIMessage(content=content)
            elif role == "system":
                # System messages should be handled at session creation, but include for completeness
                return SystemMessage(content=content)
            else:
                self.logger.warning(f"Session {self.session_id}: Unknown message role '{role}', skipping")
                return None
                
        except Exception as e:
            # Create detailed error for message processing failures
            error_context = {
                "message_role": message.get("role", "unknown"),
                "content_length": len(message.get("content", "")),
                "message_keys": list(message.keys())
            }
            
            mapped_error = MessageProcessingError(
                f"Failed to convert database message to LangChain format",
                e,
                message_role=message.get("role"),
                session_id=self.session_id
            )
            
            self.logger.warning(
                f"Session {self.session_id}: Message conversion failed: {str(mapped_error)}. "
                f"Context: {error_context}"
            )
            return None
    
    def _optimize_restored_context(self) -> None:
        """
        Apply context optimization after restoring messages from database.
        
        Ensures the restored context is within optimal limits and applies
        summarization if needed.
        """
        try:
            # Check if optimization is needed
            if self.context_optimizer.should_optimize_context(self.conversation_history):
                original_count = len(self.conversation_history)
                
                # Apply optimization through summarization middleware
                optimized_context = self.summarization_middleware.process_messages(self.conversation_history)
                
                # Update conversation history with optimized context
                # Keep system messages and replace the rest
                system_messages = [msg for msg in self.conversation_history if isinstance(msg, SystemMessage)]
                non_system_optimized = [msg for msg in optimized_context if not isinstance(msg, SystemMessage)]
                
                self.conversation_history = system_messages + non_system_optimized
                
                self.logger.info(
                    f"Session {self.session_id}: Optimized restored context "
                    f"({original_count} -> {len(self.conversation_history)} messages)"
                )
        except Exception as e:
            self.logger.warning(f"Session {self.session_id}: Failed to optimize restored context: {str(e)}")
            # Continue with unoptimized context
    
    def _process_system_instruction(self, system_instruction: str) -> None:
        """
        Process and add system instruction to the conversation.
        
        Handles both direct instruction text and instruction type names.
        Maintains compatibility with existing system instruction types.
        
        Args:
            system_instruction: The system instruction text or type name
        """
        if not system_instruction or not system_instruction.strip():
            return
        
        instruction_text = system_instruction.strip()
        
        # Check if this is a system instruction type name
        if instruction_text.lower() in SYSTEM_INSTRUCTIONS:
            try:
                instruction_text = get_system_instruction(instruction_text.lower())
                self.logger.debug(f"Session {self.session_id}: Using system instruction type '{instruction_text.lower()}'")
            except ValueError as e:
                self.logger.warning(f"Session {self.session_id}: Failed to get system instruction type '{instruction_text}': {e}")
                # Fall back to using the original text as-is
        
        # Create and add system message
        system_message = SystemMessage(content=instruction_text)
        # Insert system message at the beginning of conversation
        self.conversation_history.insert(0, system_message)
        
        self.logger.info(f"Session {self.session_id}: Applied system instruction ({len(instruction_text)} characters)")
    
    def _add_system_instruction(self, system_instruction: str) -> None:
        """
        Add system instruction to the conversation (legacy method for compatibility).
        
        Args:
            system_instruction: The system instruction text
        """
        self._process_system_instruction(system_instruction)
    
    def clear_history(self) -> None:
        """
        Clear the conversation history while preserving system instructions.
        """
        # Keep only system messages
        system_messages = [msg for msg in self.conversation_history if isinstance(msg, SystemMessage)]
        self.conversation_history = system_messages
        
        self.logger.debug(f"Session {self.session_id}: Cleared conversation history")
    
    def get_message_count(self) -> int:
        """
        Get the number of messages in the conversation (excluding system messages).
        
        Returns:
            int: Number of user and assistant messages
        """
        return len([msg for msg in self.conversation_history if not isinstance(msg, SystemMessage)])
    
    def get_system_instruction(self) -> Optional[str]:
        """
        Get the current system instruction text.
        
        Returns:
            Optional[str]: The system instruction text if present, None otherwise
        """
        for message in self.conversation_history:
            if isinstance(message, SystemMessage):
                return message.content
        return None
    
    def update_system_instruction(self, system_instruction: str) -> None:
        """
        Update the system instruction for this session.
        
        Replaces any existing system instruction with the new one.
        
        Args:
            system_instruction: The new system instruction text or type name
        """
        # Remove existing system messages
        self.conversation_history = [msg for msg in self.conversation_history if not isinstance(msg, SystemMessage)]
        
        # Add new system instruction
        if system_instruction:
            self._process_system_instruction(system_instruction)
            self.logger.info(f"Session {self.session_id}: Updated system instruction")
    
    def has_system_instruction(self) -> bool:
        """
        Check if this session has a system instruction.
        
        Returns:
            bool: True if a system instruction is present
        """
        return any(isinstance(msg, SystemMessage) for msg in self.conversation_history)    

    def get_context_optimizer(self) -> ContextOptimizer:
        """
        Get the context optimizer instance.
        
        Returns:
            ContextOptimizer: The context optimizer used by this session
        """
        return self.context_optimizer
    
    def get_summarization_middleware(self) -> SummarizationMiddleware:
        """
        Get the summarization middleware instance.
        
        Returns:
            SummarizationMiddleware: The summarization middleware used by this session
        """
        return self.summarization_middleware
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """
        Get context optimization statistics for this session.
        
        Returns:
            Dictionary containing optimization statistics
        """
        optimizer_stats = self.context_optimizer.get_optimization_stats()
        middleware_stats = self.summarization_middleware.get_middleware_stats()
        
        return {
            "session_id": self.session_id,
            "conversation_length": len(self.conversation_history),
            "optimizer": optimizer_stats,
            "middleware": middleware_stats
        }
    
    def update_context_config(self, config: ContextConfig) -> None:
        """
        Update the context optimization configuration.
        
        Args:
            config: New context configuration to apply
        """
        self.context_optimizer.update_config(config)
        self.logger.info(f"Session {self.session_id}: Updated context optimization configuration")
    
    def reset_optimization_stats(self) -> None:
        """Reset optimization statistics for this session."""
        self.context_optimizer.reset_stats()
        self.summarization_middleware.reset_stats()
        self.logger.debug(f"Session {self.session_id}: Reset optimization statistics")
    
    def _add_message_with_fallback(self, message: BaseMessage) -> bool:
        """
        Add message to conversation history with fallback support.
        
        Args:
            message: The message to add
            
        Returns:
            bool: True if message was added successfully
        """
        def primary_add_message(**kwargs):
            msg = kwargs["message"]
            self.conversation_history.append(msg)
            return True
        
        return self.fallback_manager.execute_with_fallback(
            primary_add_message,
            "add_message",
            message=message
        )
    
    def _get_optimized_context_with_fallback(self) -> List[BaseMessage]:
        """
        Get optimized context with fallback support.
        
        Returns:
            List[BaseMessage]: Optimized conversation context
        """
        def primary_get_context(**kwargs):
            return self.summarization_middleware.process_messages(self.conversation_history)
        
        try:
            return self.fallback_manager.execute_with_fallback(
                primary_get_context,
                "get_optimized_context"
            )
        except Exception as e:
            # If optimization fails completely, fall back to basic conversation history
            self.logger.warning(
                f"Session {self.session_id}: Context optimization failed, using basic history: {str(e)}"
            )
            return self.conversation_history.copy()
    
    def _restore_context_with_fallback(self, messages: List[Dict[str, str]]) -> bool:
        """
        Restore context with fallback support.
        
        Args:
            messages: Messages to restore
            
        Returns:
            bool: True if context was restored successfully
        """
        def primary_restore_context(**kwargs):
            msgs = kwargs["messages"]
            if not msgs:
                return True
            
            # Apply intelligent message selection for memory restoration
            selected_messages = self._select_messages_for_restoration(msgs)
            
            # Convert database messages to LangChain message objects
            restored_count = 0
            for message in selected_messages:
                langchain_message = self._convert_database_message_to_langchain(message)
                if langchain_message:
                    self.conversation_history.append(langchain_message)
                    restored_count += 1
            
            # Apply context optimization after restoration if needed
            if restored_count > 0:
                self._optimize_restored_context()
            
            return True
        
        return self.fallback_manager.execute_with_fallback(
            primary_restore_context,
            "restore_context",
            messages=messages
        )
    
    def get_token_usage_details(self) -> Dict[str, Any]:
        """
        Get detailed token usage information for the current conversation.
        
        Returns:
            Dictionary with detailed token usage breakdown
        """
        return self.context_optimizer.calculate_detailed_token_usage(self.conversation_history)
    
    def force_context_optimization(self) -> List[BaseMessage]:
        """
        Force context optimization on the current conversation history.
        
        Returns:
            Optimized conversation context
        """
        optimized_context = self.context_optimizer.optimize_context(self.conversation_history)
        self.logger.info(
            f"Session {self.session_id}: Forced context optimization "
            f"({len(self.conversation_history)} -> {len(optimized_context)} messages)"
        )
        return optimized_context
    
    def get_fallback_status(self) -> Dict[str, Any]:
        """
        Get current fallback status and statistics.
        
        Returns:
            Dictionary with fallback status information
        """
        return self.fallback_manager.get_fallback_status()
    
    def get_fallback_history(self) -> List[Dict[str, Any]]:
        """
        Get detailed fallback history for this session.
        
        Returns:
            List of fallback events with details
        """
        return self.fallback_manager.get_fallback_history()
    
    def is_in_fallback_mode(self) -> bool:
        """
        Check if the session is currently in fallback mode.
        
        Returns:
            bool: True if in fallback mode
        """
        return self.fallback_manager.is_in_fallback_mode()
    
    def reset_fallback_state(self) -> None:
        """Reset fallback state for this session."""
        self.fallback_manager.reset_fallback_manager()
        self.logger.info(f"Session {self.session_id}: Fallback state reset")
    
    def get_memory_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive memory health status including fallback information.
        
        Returns:
            Dictionary with memory health status
        """
        fallback_status = self.get_fallback_status()
        optimization_stats = self.get_optimization_stats()
        
        return {
            "session_id": self.session_id,
            "conversation_length": len(self.conversation_history),
            "memory_health": "degraded" if self.is_in_fallback_mode() else "healthy",
            "fallback_status": fallback_status,
            "optimization_stats": optimization_stats,
            "last_optimization_successful": not self.is_in_fallback_mode()
        }