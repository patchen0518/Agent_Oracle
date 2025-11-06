"""
Context optimization system for LangChain integration.

This module provides intelligent context selection and token management
for efficient conversation handling and improved AI performance.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """Enumeration of context optimization strategies."""
    RECENCY = "recency"
    RELEVANCE = "relevance"
    HYBRID = "hybrid"
    SUMMARIZATION = "summarization"


@dataclass
class ContextConfig:
    """Configuration for context optimization."""
    max_tokens: int = 4000
    messages_to_keep_after_summary: int = 20
    relevance_threshold: float = 0.7
    enable_semantic_search: bool = True
    summarization_trigger_ratio: float = 0.8
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.HYBRID
    preserve_system_messages: bool = True
    min_messages_for_optimization: int = 10
    
    # Token calculation settings
    chars_per_token: int = 4
    system_message_weight: float = 1.5  # System messages are more important
    recent_message_weight: float = 1.2  # Recent messages are more important
    
    # Relevance scoring settings
    keyword_match_weight: float = 2.0
    semantic_similarity_weight: float = 1.0
    position_decay_factor: float = 0.95  # How much to decay relevance by position
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ContextConfig":
        """Create ContextConfig from dictionary."""
        # Handle strategy conversion
        strategy = config_dict.get("optimization_strategy", "hybrid")
        if isinstance(strategy, str):
            try:
                strategy = OptimizationStrategy(strategy.lower())
            except ValueError:
                logger.warning(f"Unknown optimization strategy '{strategy}', defaulting to hybrid")
                strategy = OptimizationStrategy.HYBRID
        
        return cls(
            max_tokens=config_dict.get("max_tokens", 4000),
            messages_to_keep_after_summary=config_dict.get("messages_to_keep_after_summary", 20),
            relevance_threshold=config_dict.get("relevance_threshold", 0.7),
            enable_semantic_search=config_dict.get("enable_semantic_search", True),
            summarization_trigger_ratio=config_dict.get("summarization_trigger_ratio", 0.8),
            optimization_strategy=strategy,
            preserve_system_messages=config_dict.get("preserve_system_messages", True),
            min_messages_for_optimization=config_dict.get("min_messages_for_optimization", 10),
            chars_per_token=config_dict.get("chars_per_token", 4),
            system_message_weight=config_dict.get("system_message_weight", 1.5),
            recent_message_weight=config_dict.get("recent_message_weight", 1.2),
            keyword_match_weight=config_dict.get("keyword_match_weight", 2.0),
            semantic_similarity_weight=config_dict.get("semantic_similarity_weight", 1.0),
            position_decay_factor=config_dict.get("position_decay_factor", 0.95)
        )


@dataclass
class MessageScore:
    """Score and metadata for a message in context optimization."""
    message: BaseMessage
    relevance_score: float
    token_count: int
    position: int
    is_system: bool = False
    is_recent: bool = False
    keywords_matched: List[str] = field(default_factory=list)
    
    @property
    def weighted_score(self) -> float:
        """Calculate weighted score considering position and type."""
        score = self.relevance_score
        
        # Apply position decay
        position_weight = 0.95 ** self.position
        score *= position_weight
        
        # Boost system messages
        if self.is_system:
            score *= 1.5
        
        # Boost recent messages
        if self.is_recent:
            score *= 1.2
        
        return score


class ContextOptimizer:
    """
    Advanced context optimizer for intelligent conversation management.
    
    This class provides sophisticated context optimization including:
    - Token calculation and usage tracking
    - Relevance-based context selection
    - Automatic summarization middleware
    - Configurable optimization strategies
    """
    
    def __init__(
        self, 
        config: Optional[ContextConfig] = None,
        session_id: Optional[int] = None
    ):
        """
        Initialize the context optimizer.
        
        Args:
            config: Context optimization configuration
            session_id: Optional session ID for logging
        """
        self.config = config or ContextConfig()
        self.session_id = session_id
        self.logger = logging.getLogger(f"context_optimizer_{session_id or 'global'}")
        
        # Derived settings
        self.summarization_threshold = int(self.config.max_tokens * self.config.summarization_trigger_ratio)
        
        # Statistics tracking
        self.optimizations_performed = 0
        self.tokens_saved = 0
        self.messages_summarized = 0
        self.relevance_calculations = 0
        
        # Cache for keyword extraction
        self._keyword_cache: Dict[str, List[str]] = {}
        
        self.logger.info(
            f"Context optimizer initialized with max_tokens={self.config.max_tokens}, "
            f"strategy={self.config.optimization_strategy.value}"
        )
    
    def optimize_context(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Optimize conversation context for token efficiency and relevance.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Optimized list of messages
        """
        try:
            if not messages:
                return messages
            
            # Skip optimization if too few messages
            if len(messages) < self.config.min_messages_for_optimization:
                self.logger.debug(f"Too few messages for optimization: {len(messages)}")
                return messages
            
            # Calculate current token usage
            original_token_count = self.calculate_token_usage(messages)
            
            # If within limits, return as-is
            if original_token_count <= self.config.max_tokens:
                self.logger.debug(f"Context within limits: {original_token_count} tokens")
                return messages
            
            # Apply optimization based on configured strategy
            optimized_messages = self._apply_optimization_strategy(messages)
            
            # Update statistics
            optimized_token_count = self.calculate_token_usage(optimized_messages)
            self.optimizations_performed += 1
            self.tokens_saved += max(0, original_token_count - optimized_token_count)
            
            self.logger.info(
                f"Context optimized using {self.config.optimization_strategy.value}: "
                f"{original_token_count} -> {optimized_token_count} tokens "
                f"({len(messages)} -> {len(optimized_messages)} messages)"
            )
            
            return optimized_messages
            
        except Exception as e:
            self.logger.error(f"Error optimizing context: {e}")
            # Return original messages as fallback
            return messages
    
    def calculate_token_usage(self, messages: List[BaseMessage]) -> int:
        """
        Calculate approximate token usage for messages with improved accuracy.
        
        Args:
            messages: List of messages to calculate tokens for
            
        Returns:
            Approximate token count
        """
        if not messages:
            return 0
        
        total_tokens = 0
        
        for message in messages:
            if not hasattr(message, 'content') or not message.content:
                continue
            
            content = str(message.content)
            
            # Basic character-based estimation
            char_count = len(content)
            base_tokens = char_count // self.config.chars_per_token
            
            # Adjust for message type and structure
            if isinstance(message, SystemMessage):
                # System messages tend to be more token-dense
                tokens = int(base_tokens * self.config.system_message_weight)
            else:
                tokens = base_tokens
            
            # Add overhead for message structure (role, metadata, etc.)
            tokens += 5  # Approximate overhead per message
            
            total_tokens += tokens
        
        self.logger.debug(f"Calculated tokens: {total_tokens} for {len(messages)} messages")
        return total_tokens
    
    def calculate_detailed_token_usage(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        Calculate detailed token usage statistics.
        
        Args:
            messages: List of messages to analyze
            
        Returns:
            Dictionary with detailed token usage breakdown
        """
        if not messages:
            return {"total_tokens": 0, "message_breakdown": []}
        
        breakdown = []
        total_tokens = 0
        
        for i, message in enumerate(messages):
            if not hasattr(message, 'content') or not message.content:
                continue
            
            content = str(message.content)
            char_count = len(content)
            base_tokens = char_count // self.config.chars_per_token
            
            # Apply message type weighting
            if isinstance(message, SystemMessage):
                tokens = int(base_tokens * self.config.system_message_weight)
                message_type = "system"
            elif isinstance(message, HumanMessage):
                tokens = base_tokens
                message_type = "human"
            elif isinstance(message, AIMessage):
                tokens = base_tokens
                message_type = "ai"
            else:
                tokens = base_tokens
                message_type = "unknown"
            
            # Add message overhead
            tokens += 5
            
            breakdown.append({
                "position": i,
                "type": message_type,
                "char_count": char_count,
                "token_count": tokens,
                "content_preview": content[:50] + "..." if len(content) > 50 else content
            })
            
            total_tokens += tokens
        
        return {
            "total_tokens": total_tokens,
            "message_count": len(messages),
            "average_tokens_per_message": total_tokens / len(messages) if messages else 0,
            "message_breakdown": breakdown
        }
    
    def should_summarize(self, messages: List[BaseMessage]) -> bool:
        """
        Determine if conversation should be summarized based on multiple criteria.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            True if summarization should be applied
        """
        if not messages:
            return False
        
        # Check token threshold
        token_count = self.calculate_token_usage(messages)
        token_threshold_met = token_count >= self.summarization_threshold
        
        # Check message count threshold
        non_system_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        message_threshold_met = len(non_system_messages) > self.config.messages_to_keep_after_summary * 2
        
        # Require both conditions for summarization
        should_summarize = token_threshold_met and message_threshold_met
        
        self.logger.debug(
            f"Should summarize: {should_summarize} "
            f"(tokens: {token_count}/{self.summarization_threshold}, "
            f"messages: {len(non_system_messages)})"
        )
        
        return should_summarize
    
    def apply_summarization(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply intelligent summarization to reduce context size.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Messages with summarization applied
        """
        if not messages:
            return messages
        
        try:
            # Separate system messages from conversation messages
            system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
            conversation_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
            
            if len(conversation_messages) <= self.config.messages_to_keep_after_summary:
                return messages
            
            # Determine messages to summarize vs keep
            messages_to_keep = self.config.messages_to_keep_after_summary
            messages_to_summarize = conversation_messages[:-messages_to_keep]
            recent_messages = conversation_messages[-messages_to_keep:]
            
            # Create summary of older messages
            summary_text = self._create_conversation_summary(messages_to_summarize)
            
            # Create summary message
            summary_message = AIMessage(
                content=f"[CONVERSATION SUMMARY: {summary_text}]"
            )
            
            # Combine system messages, summary, and recent messages
            result = system_messages + [summary_message] + recent_messages
            
            # Update statistics
            self.messages_summarized += len(messages_to_summarize)
            
            self.logger.info(
                f"Applied summarization: {len(messages)} -> {len(result)} messages "
                f"(summarized {len(messages_to_summarize)} messages)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error during summarization: {e}")
            # Fallback to simple truncation
            return self._apply_simple_truncation(messages)
    
    def _apply_optimization_strategy(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply the configured optimization strategy.
        
        Args:
            messages: Messages to optimize
            
        Returns:
            Optimized messages
        """
        strategy = self.config.optimization_strategy
        
        if strategy == OptimizationStrategy.RECENCY:
            return self._apply_recency_optimization(messages)
        elif strategy == OptimizationStrategy.RELEVANCE:
            return self._apply_relevance_optimization(messages)
        elif strategy == OptimizationStrategy.HYBRID:
            return self._apply_hybrid_optimization(messages)
        elif strategy == OptimizationStrategy.SUMMARIZATION:
            return self._apply_summarization_optimization(messages)
        else:
            # Default to hybrid strategy
            return self._apply_hybrid_optimization(messages)
    
    def _apply_recency_optimization(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply recency-based optimization (keep most recent messages).
        
        Args:
            messages: Messages to optimize
            
        Returns:
            Optimized messages prioritizing recent messages
        """
        if self.config.preserve_system_messages:
            system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
            other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        else:
            system_messages = []
            other_messages = messages
        
        # Calculate how many messages we can keep within token limit
        target_tokens = self.config.max_tokens
        current_tokens = self.calculate_token_usage(system_messages)
        
        # Add recent messages until we hit the token limit
        selected_messages = []
        for message in reversed(other_messages):
            message_tokens = self.calculate_token_usage([message])
            if current_tokens + message_tokens <= target_tokens:
                selected_messages.insert(0, message)
                current_tokens += message_tokens
            else:
                break
        
        result = system_messages + selected_messages
        self.logger.debug(f"Recency optimization: {len(messages)} -> {len(result)} messages")
        return result
    
    def _apply_relevance_optimization(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply relevance-based optimization using intelligent message scoring and selection.
        
        Args:
            messages: Messages to optimize
            
        Returns:
            Optimized messages prioritizing relevant messages
        """
        if not messages:
            return messages
        
        # Score all messages for relevance
        scored_messages = self._score_messages_for_relevance(messages)
        
        # Always include system messages
        system_messages = [sm.message for sm in scored_messages if sm.is_system]
        non_system_scored = [sm for sm in scored_messages if not sm.is_system]
        
        if not non_system_scored:
            return system_messages
        
        # Apply intelligent message selection
        selected_messages = self._select_relevant_messages(non_system_scored, messages)
        
        # Combine system messages with selected relevant messages
        result = system_messages + selected_messages
        
        # Calculate statistics
        avg_relevance = sum(sm.relevance_score for sm in non_system_scored if sm.message in selected_messages) / max(1, len(selected_messages))
        
        self.logger.debug(
            f"Relevance optimization: {len(messages)} -> {len(result)} messages "
            f"(avg relevance: {avg_relevance:.2f}, threshold: {self.config.relevance_threshold})"
        )
        
        return result
    
    def _select_relevant_messages(self, scored_messages: List[MessageScore], original_messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Intelligently select relevant messages within token budget.
        
        Args:
            scored_messages: List of scored messages
            original_messages: Original message list for position reference
            
        Returns:
            Selected relevant messages
        """
        # Sort by weighted score (descending)
        scored_messages.sort(key=lambda x: x.weighted_score, reverse=True)
        
        # Calculate token budget
        system_token_usage = sum(
            sm.token_count for sm in scored_messages 
            if sm.is_system
        )
        available_tokens = self.config.max_tokens - system_token_usage
        
        # Phase 1: Select high-relevance messages above threshold
        high_relevance_messages = []
        current_tokens = 0
        
        for scored_msg in scored_messages:
            if scored_msg.relevance_score >= self.config.relevance_threshold:
                if current_tokens + scored_msg.token_count <= available_tokens:
                    high_relevance_messages.append(scored_msg)
                    current_tokens += scored_msg.token_count
        
        # Phase 2: Fill remaining space with recent messages if needed
        remaining_tokens = available_tokens - current_tokens
        recent_messages = [
            sm for sm in scored_messages 
            if sm.is_recent and sm not in high_relevance_messages
        ]
        
        # Sort recent messages by position (most recent first)
        recent_messages.sort(key=lambda x: x.position, reverse=True)
        
        for scored_msg in recent_messages:
            if remaining_tokens >= scored_msg.token_count:
                high_relevance_messages.append(scored_msg)
                remaining_tokens -= scored_msg.token_count
        
        # Phase 3: Ensure conversation continuity
        selected_messages = self._ensure_conversation_continuity(
            high_relevance_messages, 
            original_messages,
            remaining_tokens
        )
        
        # Sort by original position to maintain conversation flow
        message_positions = {id(msg): i for i, msg in enumerate(original_messages)}
        selected_messages.sort(key=lambda x: message_positions.get(id(x), 0))
        
        return selected_messages
    
    def _ensure_conversation_continuity(
        self, 
        selected_scored: List[MessageScore], 
        original_messages: List[BaseMessage],
        remaining_tokens: int
    ) -> List[BaseMessage]:
        """
        Ensure conversation continuity by filling gaps in selected messages.
        
        Args:
            selected_scored: Already selected scored messages
            original_messages: Original message list
            remaining_tokens: Remaining token budget
            
        Returns:
            Messages with improved continuity
        """
        selected_messages = [sm.message for sm in selected_scored]
        message_positions = {id(msg): i for i, msg in enumerate(original_messages)}
        
        # Find gaps in conversation flow
        selected_positions = sorted([
            message_positions.get(id(msg), -1) 
            for msg in selected_messages 
            if message_positions.get(id(msg), -1) >= 0
        ])
        
        # Fill small gaps (1-2 messages) if we have token budget
        gap_fillers = []
        for i in range(len(selected_positions) - 1):
            current_pos = selected_positions[i]
            next_pos = selected_positions[i + 1]
            gap_size = next_pos - current_pos - 1
            
            # Fill gaps of 1-2 messages if they're not too expensive
            if 1 <= gap_size <= 2 and remaining_tokens > 0:
                for pos in range(current_pos + 1, next_pos):
                    if pos < len(original_messages):
                        gap_message = original_messages[pos]
                        gap_tokens = self.calculate_token_usage([gap_message])
                        
                        if gap_tokens <= remaining_tokens:
                            gap_fillers.append(gap_message)
                            remaining_tokens -= gap_tokens
        
        return selected_messages + gap_fillers
    
    def _apply_hybrid_optimization(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply hybrid optimization combining recency and relevance.
        
        Args:
            messages: Messages to optimize
            
        Returns:
            Optimized messages using hybrid approach
        """
        # First check if summarization is needed
        if self.should_summarize(messages):
            return self.apply_summarization(messages)
        
        # Score messages for relevance
        scored_messages = self._score_messages_for_relevance(messages)
        
        # Separate system and non-system messages
        system_messages = [sm.message for sm in scored_messages if sm.is_system]
        non_system_scored = [sm for sm in scored_messages if not sm.is_system]
        
        # Apply hybrid scoring (relevance + recency)
        for scored_msg in non_system_scored:
            # Boost recent messages
            if scored_msg.position >= len(messages) - self.config.messages_to_keep_after_summary:
                scored_msg.is_recent = True
        
        # Sort by weighted score
        non_system_scored.sort(key=lambda x: x.weighted_score, reverse=True)
        
        # Select messages within token budget
        target_tokens = self.config.max_tokens
        current_tokens = self.calculate_token_usage(system_messages)
        
        selected_messages = []
        for scored_msg in non_system_scored:
            if current_tokens + scored_msg.token_count <= target_tokens:
                selected_messages.append(scored_msg.message)
                current_tokens += scored_msg.token_count
        
        # Maintain conversation order
        message_positions = {id(msg): i for i, msg in enumerate(messages)}
        selected_messages.sort(key=lambda x: message_positions.get(id(x), 0))
        
        result = system_messages + selected_messages
        self.logger.debug(f"Hybrid optimization: {len(messages)} -> {len(result)} messages")
        return result
    
    def _apply_summarization_optimization(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply summarization-focused optimization.
        
        Args:
            messages: Messages to optimize
            
        Returns:
            Optimized messages with aggressive summarization
        """
        return self.apply_summarization(messages)
    
    def _apply_simple_truncation(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Apply simple truncation as a fallback optimization.
        
        Args:
            messages: Messages to optimize
            
        Returns:
            Truncated messages
        """
        if self.config.preserve_system_messages:
            system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
            other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
            
            # Keep recent messages
            recent_count = min(self.config.messages_to_keep_after_summary, len(other_messages))
            recent_messages = other_messages[-recent_count:]
            
            result = system_messages + recent_messages
        else:
            # Simple truncation
            result = messages[-self.config.messages_to_keep_after_summary:]
        
        self.logger.debug(f"Simple truncation: {len(messages)} -> {len(result)} messages")
        return result
    
    def _score_messages_for_relevance(self, messages: List[BaseMessage]) -> List[MessageScore]:
        """
        Score messages for relevance based on content and context.
        
        Args:
            messages: Messages to score
            
        Returns:
            List of MessageScore objects with relevance scores
        """
        if not messages:
            return []
        
        scored_messages = []
        
        # Extract keywords from recent messages for relevance scoring
        recent_keywords = self._extract_conversation_keywords(messages[-5:])
        
        for i, message in enumerate(messages):
            if not hasattr(message, 'content') or not message.content:
                continue
            
            # Calculate base relevance score
            relevance_score = self._calculate_message_relevance(message, recent_keywords)
            
            # Calculate token count for this message
            token_count = self.calculate_token_usage([message])
            
            # Create message score
            scored_message = MessageScore(
                message=message,
                relevance_score=relevance_score,
                token_count=token_count,
                position=i,
                is_system=isinstance(message, SystemMessage),
                is_recent=i >= len(messages) - self.config.messages_to_keep_after_summary
            )
            
            scored_messages.append(scored_message)
        
        self.relevance_calculations += len(scored_messages)
        return scored_messages
    
    def _calculate_message_relevance(self, message: BaseMessage, context_keywords: List[str]) -> float:
        """
        Calculate relevance score for a single message using multiple criteria.
        
        Args:
            message: Message to score
            context_keywords: Keywords from recent conversation context
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not hasattr(message, 'content') or not message.content:
            return 0.0
        
        content = str(message.content).lower()
        original_content = str(message.content)
        
        # Base score
        score = 0.1
        
        # System messages are always highly relevant
        if isinstance(message, SystemMessage):
            return 0.95
        
        # Keyword matching score with fuzzy matching
        if context_keywords:
            matched_keywords = []
            keyword_score = 0.0
            
            for keyword in context_keywords:
                keyword_lower = keyword.lower()
                
                # Exact match
                if keyword_lower in content:
                    matched_keywords.append(keyword)
                    keyword_score += self.config.keyword_match_weight
                # Partial match (for compound words)
                elif any(part in content for part in keyword_lower.split() if len(part) > 2):
                    matched_keywords.append(keyword)
                    keyword_score += self.config.keyword_match_weight * 0.7
                # Stem matching (simple approach)
                elif self._has_stem_match(keyword_lower, content):
                    matched_keywords.append(keyword)
                    keyword_score += self.config.keyword_match_weight * 0.5
            
            # Normalize keyword score
            if context_keywords:
                keyword_score = keyword_score / len(context_keywords)
                score += min(0.4, keyword_score)  # Cap keyword contribution
            
            # Store matched keywords for debugging
            if hasattr(message, '_matched_keywords'):
                message._matched_keywords = matched_keywords
        
        # Content quality indicators
        score += self._calculate_content_quality_score(original_content)
        
        # Semantic patterns
        score += self._calculate_semantic_pattern_score(content)
        
        # Message type bonuses
        if isinstance(message, HumanMessage):
            # User questions are often important
            if any(pattern in content for pattern in ['?', 'how', 'what', 'why', 'when', 'where', 'can you', 'could you']):
                score += 0.15
        elif isinstance(message, AIMessage):
            # AI responses with explanations are valuable
            if any(pattern in content for pattern in ['because', 'therefore', 'however', 'for example', 'specifically']):
                score += 0.1
        
        # Normalize score to 0-1 range
        return min(1.0, score)
    
    def _has_stem_match(self, keyword: str, content: str) -> bool:
        """
        Check for stem-based matching (simple implementation).
        
        Args:
            keyword: Keyword to match
            content: Content to search in
            
        Returns:
            True if stem match found
        """
        # Simple stemming: remove common suffixes
        def simple_stem(word: str) -> str:
            suffixes = ['ing', 'ed', 'er', 'est', 'ly', 's']
            for suffix in suffixes:
                if word.endswith(suffix) and len(word) > len(suffix) + 2:
                    return word[:-len(suffix)]
            return word
        
        keyword_stem = simple_stem(keyword)
        if len(keyword_stem) < 3:
            return False
        
        # Check if stem appears in content
        content_words = re.findall(r'\b\w+\b', content)
        for word in content_words:
            if simple_stem(word) == keyword_stem:
                return True
        
        return False
    
    def _calculate_content_quality_score(self, content: str) -> float:
        """
        Calculate content quality score based on various indicators.
        
        Args:
            content: Message content to analyze
            
        Returns:
            Quality score contribution (0.0 to 0.3)
        """
        score = 0.0
        
        # Content length bonus (longer messages often contain more information)
        length_bonus = min(0.15, len(content) / 1000)
        score += length_bonus
        
        # Code or technical content bonus
        if any(pattern in content for pattern in ['def ', 'function', 'class ', 'import ', '```', 'error', 'exception', 'TypeError', 'ValueError']):
            score += 0.1
        
        # Structured content (lists, numbered items)
        if any(pattern in content for pattern in ['\n1.', '\n2.', '\n-', '\n*', '• ']):
            score += 0.05
        
        # URLs or references (often contain important information)
        if any(pattern in content for pattern in ['http', 'www.', '.com', '.org', 'github']):
            score += 0.05
        
        # Mathematical or scientific content
        if any(pattern in content for pattern in ['=', '+', '-', '*', '/', '%', '>', '<', '≥', '≤']):
            score += 0.03
        
        return min(0.3, score)
    
    def _calculate_semantic_pattern_score(self, content: str) -> float:
        """
        Calculate score based on semantic patterns in the content.
        
        Args:
            content: Message content (lowercase)
            
        Returns:
            Semantic pattern score contribution (0.0 to 0.2)
        """
        score = 0.0
        
        # Question patterns (high engagement)
        question_patterns = ['?', 'how', 'what', 'why', 'when', 'where', 'which', 'who']
        question_count = sum(1 for pattern in question_patterns if pattern in content)
        score += min(0.1, question_count * 0.03)
        
        # Explanation patterns (valuable content)
        explanation_patterns = ['because', 'therefore', 'however', 'for example', 'specifically', 'in other words', 'that is']
        explanation_count = sum(1 for pattern in explanation_patterns if pattern in content)
        score += min(0.05, explanation_count * 0.02)
        
        # Problem-solving patterns
        problem_patterns = ['problem', 'issue', 'error', 'bug', 'fix', 'solve', 'solution', 'resolve']
        problem_count = sum(1 for pattern in problem_patterns if pattern in content)
        score += min(0.05, problem_count * 0.02)
        
        # Decision or conclusion patterns
        decision_patterns = ['decided', 'conclusion', 'result', 'outcome', 'final', 'summary']
        decision_count = sum(1 for pattern in decision_patterns if pattern in content)
        score += min(0.03, decision_count * 0.015)
        
        return min(0.2, score)
    
    def _extract_conversation_keywords(self, messages: List[BaseMessage]) -> List[str]:
        """
        Extract important keywords from conversation messages.
        
        Args:
            messages: Messages to extract keywords from
            
        Returns:
            List of important keywords
        """
        if not messages:
            return []
        
        # Combine all message content
        combined_content = ""
        for message in messages:
            if hasattr(message, 'content') and message.content:
                combined_content += " " + str(message.content)
        
        if not combined_content.strip():
            return []
        
        # Use cache if available
        content_hash = str(hash(combined_content))
        if content_hash in self._keyword_cache:
            return self._keyword_cache[content_hash]
        
        # Simple keyword extraction (in a full implementation, this could use NLP libraries)
        keywords = self._extract_keywords_simple(combined_content)
        
        # Cache the result
        self._keyword_cache[content_hash] = keywords
        
        return keywords
    
    def _extract_keywords_simple(self, text: str) -> List[str]:
        """
        Simple keyword extraction using basic text processing.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of extracted keywords
        """
        # Convert to lowercase and split into words
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Common stop words to filter out
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
            'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'
        }
        
        # Filter words
        filtered_words = [
            word for word in words 
            if len(word) > 2 and word not in stop_words
        ]
        
        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Sort by frequency and return top keywords
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, count in sorted_words[:20]]  # Top 20 keywords
        
        return keywords
    
    def _create_conversation_summary(self, messages: List[BaseMessage]) -> str:
        """
        Create a summary of conversation messages.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Summary text
        """
        if not messages:
            return "No messages to summarize"
        
        # Extract key information
        user_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
        ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        
        summary_parts = []
        
        # Summarize user topics
        if user_messages:
            user_keywords = self._extract_conversation_keywords(user_messages[:5])
            if user_keywords:
                summary_parts.append(f"User discussed: {', '.join(user_keywords[:5])}")
        
        # Count interactions
        if user_messages and ai_messages:
            summary_parts.append(f"{len(user_messages)} user messages, {len(ai_messages)} AI responses")
        
        # Extract any code or technical content
        code_messages = [
            msg for msg in messages 
            if hasattr(msg, 'content') and msg.content and 
            any(pattern in str(msg.content) for pattern in ['```', 'def ', 'function', 'class ', 'import '])
        ]
        if code_messages:
            summary_parts.append(f"Technical discussion with {len(code_messages)} code-related messages")
        
        # Create final summary
        if summary_parts:
            summary = f"Previous conversation: {'. '.join(summary_parts)}"
        else:
            summary = f"Previous conversation with {len(messages)} messages"
        
        return summary
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """
        Get optimization statistics.
        
        Returns:
            Dictionary containing optimization statistics
        """
        return {
            "optimizations_performed": self.optimizations_performed,
            "tokens_saved": self.tokens_saved,
            "messages_summarized": self.messages_summarized,
            "relevance_calculations": self.relevance_calculations,
            "config": {
                "max_tokens": self.config.max_tokens,
                "strategy": self.config.optimization_strategy.value,
                "summarization_threshold": self.summarization_threshold
            }
        }
    
    def reset_stats(self) -> None:
        """Reset optimization statistics."""
        self.optimizations_performed = 0
        self.tokens_saved = 0
        self.messages_summarized = 0
        self.relevance_calculations = 0
        self._keyword_cache.clear()
        
        self.logger.debug("Reset optimization statistics")
    
    def update_config(self, new_config: ContextConfig) -> None:
        """
        Update optimization configuration.
        
        Args:
            new_config: New configuration to apply
        """
        self.config = new_config
        self.summarization_threshold = int(self.config.max_tokens * self.config.summarization_trigger_ratio)
        
        # Clear cache since configuration changed
        self._keyword_cache.clear()
        
        self.logger.info(f"Updated configuration: strategy={self.config.optimization_strategy.value}")
    
    def analyze_message_relevance(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        Analyze message relevance for debugging and monitoring purposes.
        
        Args:
            messages: Messages to analyze
            
        Returns:
            Dictionary with detailed relevance analysis
        """
        if not messages:
            return {"error": "No messages to analyze"}
        
        # Score all messages
        scored_messages = self._score_messages_for_relevance(messages)
        
        # Calculate statistics
        relevance_scores = [sm.relevance_score for sm in scored_messages if not sm.is_system]
        
        if not relevance_scores:
            return {"error": "No non-system messages to analyze"}
        
        analysis = {
            "total_messages": len(messages),
            "non_system_messages": len(relevance_scores),
            "relevance_stats": {
                "mean": sum(relevance_scores) / len(relevance_scores),
                "min": min(relevance_scores),
                "max": max(relevance_scores),
                "above_threshold": sum(1 for score in relevance_scores if score >= self.config.relevance_threshold),
                "threshold": self.config.relevance_threshold
            },
            "message_breakdown": []
        }
        
        # Add detailed breakdown for each message
        for i, scored_msg in enumerate(scored_messages):
            if scored_msg.is_system:
                continue
                
            breakdown = {
                "position": scored_msg.position,
                "relevance_score": scored_msg.relevance_score,
                "weighted_score": scored_msg.weighted_score,
                "token_count": scored_msg.token_count,
                "is_recent": scored_msg.is_recent,
                "content_preview": str(scored_msg.message.content)[:100] + "..." if len(str(scored_msg.message.content)) > 100 else str(scored_msg.message.content),
                "matched_keywords": getattr(scored_msg.message, '_matched_keywords', [])
            }
            
            analysis["message_breakdown"].append(breakdown)
        
        return analysis
    
    def get_context_compression_ratio(self, original_messages: List[BaseMessage]) -> Dict[str, float]:
        """
        Calculate context compression ratios for different optimization strategies.
        
        Args:
            original_messages: Original message list
            
        Returns:
            Dictionary with compression ratios for each strategy
        """
        if not original_messages:
            return {}
        
        original_tokens = self.calculate_token_usage(original_messages)
        
        ratios = {}
        
        # Test each optimization strategy
        for strategy in OptimizationStrategy:
            # Temporarily change strategy
            original_strategy = self.config.optimization_strategy
            self.config.optimization_strategy = strategy
            
            try:
                optimized_messages = self._apply_optimization_strategy(original_messages)
                optimized_tokens = self.calculate_token_usage(optimized_messages)
                
                compression_ratio = optimized_tokens / original_tokens if original_tokens > 0 else 1.0
                ratios[strategy.value] = {
                    "compression_ratio": compression_ratio,
                    "tokens_saved": original_tokens - optimized_tokens,
                    "messages_kept": len(optimized_messages),
                    "messages_original": len(original_messages)
                }
            except Exception as e:
                ratios[strategy.value] = {"error": str(e)}
            finally:
                # Restore original strategy
                self.config.optimization_strategy = original_strategy
        
        return ratios


class SummarizationMiddleware:
    """
    Middleware for automatic conversation summarization.
    
    This class provides automatic summarization triggers and integration
    with memory strategies for seamless context management.
    """
    
    def __init__(self, context_optimizer: ContextOptimizer):
        """
        Initialize summarization middleware.
        
        Args:
            context_optimizer: Context optimizer instance to use
        """
        self.context_optimizer = context_optimizer
        self.logger = logging.getLogger(f"summarization_middleware_{context_optimizer.session_id or 'global'}")
        
        # Middleware statistics
        self.auto_summarizations = 0
        self.middleware_invocations = 0
    
    def process_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Process messages through summarization middleware.
        
        Args:
            messages: Messages to process
            
        Returns:
            Processed messages (potentially summarized)
        """
        self.middleware_invocations += 1
        
        try:
            # Check if automatic summarization should be triggered
            if self.context_optimizer.should_summarize(messages):
                self.logger.info("Automatic summarization triggered by middleware")
                summarized_messages = self.context_optimizer.apply_summarization(messages)
                self.auto_summarizations += 1
                return summarized_messages
            
            # If no summarization needed, apply regular optimization
            return self.context_optimizer.optimize_context(messages)
            
        except Exception as e:
            self.logger.error(f"Error in summarization middleware: {e}")
            # Return original messages as fallback
            return messages
    
    def get_middleware_stats(self) -> Dict[str, Any]:
        """
        Get middleware statistics.
        
        Returns:
            Dictionary containing middleware statistics
        """
        return {
            "auto_summarizations": self.auto_summarizations,
            "middleware_invocations": self.middleware_invocations,
            "summarization_rate": self.auto_summarizations / max(1, self.middleware_invocations)
        }
    
    def reset_stats(self) -> None:
        """Reset middleware statistics."""
        self.auto_summarizations = 0
        self.middleware_invocations = 0
        
        self.logger.debug("Reset middleware statistics")