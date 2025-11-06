"""
Context optimization system for LangChain integration.

This module provides intelligent context selection and token management
for efficient conversation handling and improved AI performance.
"""

from typing import List, Dict, Any
import logging
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class ContextOptimizer:
    """
    Context optimizer for intelligent conversation management.
    
    This class optimizes conversation context for token efficiency
    and relevance while maintaining conversation continuity.
    """
    
    def __init__(
        self, 
        max_tokens: int = 4000, 
        messages_to_keep: int = 20,
        summarization_trigger_ratio: float = 0.8
    ):
        """
        Initialize the context optimizer.
        
        Args:
            max_tokens: Maximum token limit for context
            messages_to_keep: Number of recent messages to keep after optimization
            summarization_trigger_ratio: Ratio of max_tokens that triggers summarization
        """
        self.max_tokens = max_tokens
        self.messages_to_keep = messages_to_keep
        self.summarization_trigger_ratio = summarization_trigger_ratio
        self.summarization_threshold = int(max_tokens * summarization_trigger_ratio)
        
        logger.info(f"Context optimizer initialized with max_tokens={max_tokens}")
    
    def optimize_context(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Optimize conversation context for token efficiency.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Optimized list of messages
        """
        try:
            if not messages:
                return messages
            
            # Calculate approximate token usage
            token_count = self.calculate_token_usage(messages)
            
            # If within limits, return as-is
            if token_count <= self.max_tokens:
                logger.debug(f"Context within limits: {token_count} tokens")
                return messages
            
            # Apply optimization strategies
            optimized_messages = self._apply_optimization_strategies(messages)
            
            optimized_token_count = self.calculate_token_usage(optimized_messages)
            logger.info(f"Context optimized: {token_count} -> {optimized_token_count} tokens")
            
            return optimized_messages
            
        except Exception as e:
            logger.error(f"Error optimizing context: {e}")
            # Return original messages as fallback
            return messages
    
    def calculate_token_usage(self, messages: List[BaseMessage]) -> int:
        """
        Calculate approximate token usage for messages.
        
        Args:
            messages: List of messages to calculate tokens for
            
        Returns:
            Approximate token count
            
        Note:
            This is a simplified token calculation. More accurate
            tokenization will be implemented in future tasks.
        """
        total_chars = 0
        for message in messages:
            if hasattr(message, 'content') and message.content:
                total_chars += len(str(message.content))
        
        # Rough approximation: 4 characters per token
        approximate_tokens = total_chars // 4
        
        logger.debug(f"Calculated approximate tokens: {approximate_tokens}")
        return approximate_tokens
    
    def should_summarize(self, messages: List[BaseMessage]) -> bool:
        """
        Determine if conversation should be summarized.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            True if summarization should be applied
        """
        token_count = self.calculate_token_usage(messages)
        should_summarize = token_count >= self.summarization_threshold
        
        logger.debug(f"Should summarize: {should_summarize} (tokens: {token_count})")
        return should_summarize
    
    def apply_summarization(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply summarization to reduce context size.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Messages with summarization applied
            
        Note:
            This is a placeholder implementation. Full summarization
            will be implemented in future tasks.
        """
        # Placeholder implementation - keep system messages and recent messages
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        # Keep the most recent messages
        recent_messages = other_messages[-self.messages_to_keep:]
        
        result = system_messages + recent_messages
        logger.debug(f"Applied placeholder summarization: {len(messages)} -> {len(result)} messages")
        
        return result
    
    def _apply_optimization_strategies(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply various optimization strategies to reduce context size.
        
        Args:
            messages: Messages to optimize
            
        Returns:
            Optimized messages
        """
        # Strategy 1: Keep system messages and recent messages
        if self.should_summarize(messages):
            return self.apply_summarization(messages)
        
        # Strategy 2: Simple truncation if still over limit
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        # Keep recent messages within token limit
        recent_messages = other_messages[-self.messages_to_keep:]
        result = system_messages + recent_messages
        
        # If still over limit, further reduce
        while self.calculate_token_usage(result) > self.max_tokens and len(recent_messages) > 5:
            recent_messages = recent_messages[1:]  # Remove oldest non-system message
            result = system_messages + recent_messages
        
        logger.debug(f"Applied optimization strategies: {len(messages)} -> {len(result)} messages")
        return result