"""
LangChain chat session implementation for Oracle Chat AI.

This module provides the LangChainChatSession class that wraps LangChain's
conversation management with intelligent memory and context optimization.
"""

from typing import Iterator, List, Dict, Any
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .memory_manager import MemoryManager
from .context_optimizer import ContextOptimizer

logger = logging.getLogger(__name__)


class LangChainChatSession:
    """
    LangChain-based chat session with intelligent memory management.
    
    This class wraps LangChain's ChatGoogleGenerativeAI with enhanced
    memory strategies and context optimization for better conversation
    continuity and token efficiency.
    """
    
    def __init__(
        self,
        chat_model: ChatGoogleGenerativeAI,
        memory_manager: MemoryManager,
        context_optimizer: ContextOptimizer
    ):
        """
        Initialize the LangChain chat session.
        
        Args:
            chat_model: LangChain ChatGoogleGenerativeAI instance
            memory_manager: Memory management component
            context_optimizer: Context optimization component
        """
        self.chat_model = chat_model
        self.memory_manager = memory_manager
        self.context_optimizer = context_optimizer
        logger.info("LangChain chat session initialized")
    
    def send_message(self, message: str) -> str:
        """
        Send a message and get the AI response.
        
        Args:
            message: User message content
            
        Returns:
            AI response as string
        """
        try:
            # Create user message
            user_message = HumanMessage(content=message)
            self.memory_manager.add_message(user_message)
            
            # Get optimized conversation context
            context_messages = self.memory_manager.get_conversation_context()
            optimized_context = self.context_optimizer.optimize_context(context_messages)
            
            # Generate AI response
            response = self.chat_model.invoke(optimized_context)
            
            # Store AI response in memory
            ai_message = AIMessage(content=response.content)
            self.memory_manager.add_message(ai_message)
            
            logger.info(f"Generated response with {len(optimized_context)} context messages")
            return response.content
            
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            raise
    
    def send_message_stream(self, message: str) -> Iterator[str]:
        """
        Send a message and get streaming AI response.
        
        Args:
            message: User message content
            
        Yields:
            AI response chunks as strings
        """
        try:
            # Create user message
            user_message = HumanMessage(content=message)
            self.memory_manager.add_message(user_message)
            
            # Get optimized conversation context
            context_messages = self.memory_manager.get_conversation_context()
            optimized_context = self.context_optimizer.optimize_context(context_messages)
            
            # Generate streaming AI response
            response_chunks = []
            for chunk in self.chat_model.stream(optimized_context):
                chunk_content = chunk.content
                response_chunks.append(chunk_content)
                yield chunk_content
            
            # Store complete AI response in memory
            complete_response = "".join(response_chunks)
            ai_message = AIMessage(content=complete_response)
            self.memory_manager.add_message(ai_message)
            
            logger.info(f"Generated streaming response with {len(optimized_context)} context messages")
            
        except Exception as e:
            logger.error(f"Error in send_message_stream: {e}")
            raise
    
    def get_conversation_history(self) -> List[BaseMessage]:
        """
        Get the current conversation history.
        
        Returns:
            List of conversation messages
        """
        return self.memory_manager.get_conversation_context()
    
    def restore_context(self, messages: List[dict]) -> None:
        """
        Restore conversation context from database messages.
        
        Args:
            messages: List of message dictionaries from database
        """
        try:
            for msg_data in messages:
                role = msg_data.get("role", "")
                content = msg_data.get("content", "")
                
                if role == "user":
                    message = HumanMessage(content=content)
                elif role == "assistant":
                    message = AIMessage(content=content)
                else:
                    # Skip system messages as they're handled separately
                    continue
                
                self.memory_manager.add_message(message)
            
            logger.info(f"Restored context with {len(messages)} messages")
            
        except Exception as e:
            logger.error(f"Error restoring context: {e}")
            raise