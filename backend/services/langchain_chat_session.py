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
from backend.exceptions import AIServiceError
from backend.config.system_instructions import get_system_instruction, SYSTEM_INSTRUCTIONS
from backend.services.context_optimizer import ContextOptimizer, ContextConfig, SummarizationMiddleware


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
        
        # Initialize conversation history with system message if provided
        self.conversation_history: List[BaseMessage] = []
        
        if system_instruction:
            self._process_system_instruction(system_instruction)
            self.logger.debug(f"Added system instruction to session {session_id}")
        
        self.logger.info(f"LangChain chat session initialized with context optimization for session {session_id}")
    
    def send_message(self, message: str) -> str:
        """
        Send a message to the chat session and get response with context optimization.
        
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
            
            # Add to conversation history
            self.conversation_history.append(human_message)
            
            # Apply context optimization through summarization middleware
            optimized_context = self.summarization_middleware.process_messages(self.conversation_history)
            
            # Get response from model using optimized context
            response = self.chat_model.invoke(optimized_context)
            
            # Add AI response to conversation history
            ai_message = AIMessage(content=response.content)
            self.conversation_history.append(ai_message)
            
            self.logger.debug(
                f"Session {self.session_id}: Sent message and received response "
                f"(context: {len(self.conversation_history)} -> {len(optimized_context)} messages)"
            )
            
            return response.content
            
        except LangChainException as e:
            self.logger.error(f"LangChain error in session {self.session_id}: {str(e)}")
            raise AIServiceError(f"LangChain error: {str(e)}", e)
        except Exception as e:
            self.logger.error(f"Failed to send message in session {self.session_id}: {str(e)}")
            raise AIServiceError(f"Failed to send message: {str(e)}", e)
    
    def send_message_stream(self, message: str) -> Iterator[str]:
        """
        Send a message and get streaming response with context optimization.
        
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
            
            # Add to conversation history
            self.conversation_history.append(human_message)
            
            # Apply context optimization through summarization middleware
            optimized_context = self.summarization_middleware.process_messages(self.conversation_history)
            
            # Stream response from model using optimized context
            response_content = ""
            for chunk in self.chat_model.stream(optimized_context):
                chunk_content = chunk.content
                response_content += chunk_content
                yield chunk_content
            
            # Add complete AI response to conversation history
            ai_message = AIMessage(content=response_content)
            self.conversation_history.append(ai_message)
            
            self.logger.debug(
                f"Session {self.session_id}: Sent streaming message and received response "
                f"(context: {len(self.conversation_history)} -> {len(optimized_context)} messages)"
            )
            
        except LangChainException as e:
            self.logger.error(f"LangChain streaming error in session {self.session_id}: {str(e)}")
            raise AIServiceError(f"LangChain streaming error: {str(e)}", e)
        except Exception as e:
            self.logger.error(f"Failed to send streaming message in session {self.session_id}: {str(e)}")
            raise AIServiceError(f"Failed to send streaming message: {str(e)}", e)
    
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
        Restore conversation context from message dictionaries.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                     Expected format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        try:
            if not messages:
                return
            
            # Limit to recent messages for performance (last 20 messages)
            recent_messages = messages[-20:] if len(messages) > 20 else messages
            
            # Convert dictionary messages to LangChain message objects
            for message in recent_messages:
                role = message.get("role", "").lower()
                content = message.get("content", "")
                
                if not content:
                    continue
                
                if role == "user":
                    self.conversation_history.append(HumanMessage(content=content))
                elif role == "assistant":
                    self.conversation_history.append(AIMessage(content=content))
                # Skip system messages as they should be handled at session creation
            
            self.logger.info(f"Session {self.session_id}: Restored {len(recent_messages)} messages to context")
            
        except Exception as e:
            self.logger.warning(f"Failed to restore context for session {self.session_id}: {str(e)}")
            # Continue without restored context - session will still work
    
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