"""
Memory management system for LangChain integration.

This module provides intelligent memory strategies for conversation management,
including buffer memory, summary memory, and entity extraction capabilities.
"""

from typing import List, Dict, Any, Optional, Union
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class MemoryStrategyType(Enum):
    """Enumeration of available memory strategy types."""
    BUFFER = "buffer"
    SUMMARY = "summary"
    ENTITY = "entity"
    HYBRID = "hybrid"


@dataclass
class MemoryConfig:
    """Configuration for memory management strategies."""
    strategy: MemoryStrategyType = MemoryStrategyType.BUFFER
    max_buffer_size: int = 20
    max_tokens_before_summary: int = 4000
    entity_extraction_enabled: bool = True
    summary_model: str = "gemini-2.5-flash"
    session_isolation: bool = True
    context_window_size: int = 10
    preserve_system_messages: bool = True
    
    # Additional configuration options
    extra_config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MemoryConfig":
        """Create MemoryConfig from dictionary."""
        # Handle strategy conversion
        strategy = config_dict.get("strategy", "buffer")
        if isinstance(strategy, str):
            try:
                strategy = MemoryStrategyType(strategy.lower())
            except ValueError:
                logger.warning(f"Unknown strategy '{strategy}', defaulting to buffer")
                strategy = MemoryStrategyType.BUFFER
        
        # Extract known fields
        known_fields = {
            "strategy": strategy,
            "max_buffer_size": config_dict.get("max_buffer_size", 20),
            "max_tokens_before_summary": config_dict.get("max_tokens_before_summary", 4000),
            "entity_extraction_enabled": config_dict.get("entity_extraction_enabled", True),
            "summary_model": config_dict.get("summary_model", "gemini-2.5-flash"),
            "session_isolation": config_dict.get("session_isolation", True),
            "context_window_size": config_dict.get("context_window_size", 10),
            "preserve_system_messages": config_dict.get("preserve_system_messages", True),
        }
        
        # Store unknown fields in extra_config
        extra_config = {k: v for k, v in config_dict.items() if k not in known_fields}
        known_fields["extra_config"] = extra_config
        
        return cls(**known_fields)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert MemoryConfig to dictionary."""
        result = {
            "strategy": self.strategy.value,
            "max_buffer_size": self.max_buffer_size,
            "max_tokens_before_summary": self.max_tokens_before_summary,
            "entity_extraction_enabled": self.entity_extraction_enabled,
            "summary_model": self.summary_model,
            "session_isolation": self.session_isolation,
            "context_window_size": self.context_window_size,
            "preserve_system_messages": self.preserve_system_messages,
        }
        result.update(self.extra_config)
        return result


class MemoryStrategy(ABC):
    """
    Abstract base class for memory strategies.
    
    Defines the interface that all memory strategies must implement
    for pluggable memory management in conversation sessions.
    """
    
    def __init__(self, config: MemoryConfig, session_id: int):
        """
        Initialize memory strategy.
        
        Args:
            config: Memory configuration
            session_id: Session identifier for isolation
        """
        self.config = config
        self.session_id = session_id
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{session_id}")
    
    @abstractmethod
    def add_message(self, message: BaseMessage) -> None:
        """
        Add a message to memory.
        
        Args:
            message: Message to add to memory
        """
        pass
    
    @abstractmethod
    def get_context(self) -> List[BaseMessage]:
        """
        Get conversation context for the current session.
        
        Returns:
            List of messages representing the conversation context
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all memory for this session."""
        pass
    
    @abstractmethod
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory usage statistics.
        
        Returns:
            Dictionary containing memory statistics
        """
        pass
    
    def should_optimize(self) -> bool:
        """
        Check if memory optimization should be triggered.
        
        Returns:
            True if optimization is needed
        """
        return False
    
    def optimize_memory(self) -> None:
        """Optimize memory usage (e.g., summarization, cleanup)."""
        pass
    
    def restore_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Restore memory state from a list of messages.
        
        Args:
            messages: Messages to restore from
        """
        for message in messages:
            self.add_message(message)


class BufferMemoryStrategy(MemoryStrategy):
    """
    Buffer memory strategy that keeps recent messages in full detail.
    
    This strategy maintains a sliding window of recent messages,
    automatically rotating older messages when the buffer size limit is reached.
    """
    
    def __init__(self, config: MemoryConfig, session_id: int):
        """
        Initialize buffer memory strategy.
        
        Args:
            config: Memory configuration
            session_id: Session identifier for isolation
        """
        super().__init__(config, session_id)
        self.messages: List[BaseMessage] = []
        self.messages_added = 0
        self.messages_rotated = 0
    
    def add_message(self, message: BaseMessage) -> None:
        """
        Add a message to the buffer with automatic rotation.
        
        Args:
            message: Message to add to buffer
        """
        self.messages.append(message)
        self.messages_added += 1
        
        # Enforce buffer size limit with message rotation
        if len(self.messages) > self.config.max_buffer_size:
            self._rotate_messages()
    
    def get_context(self) -> List[BaseMessage]:
        """
        Get all messages in buffer.
        
        Returns:
            Copy of all messages in the buffer
        """
        return self.messages.copy()
    
    def clear(self) -> None:
        """Clear the buffer and reset statistics."""
        self.messages.clear()
        self.messages_added = 0
        self.messages_rotated = 0
        self.logger.debug(f"Cleared buffer memory for session {self.session_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get buffer memory statistics.
        
        Returns:
            Dictionary containing buffer statistics
        """
        system_messages = sum(1 for msg in self.messages if isinstance(msg, SystemMessage))
        user_messages = sum(1 for msg in self.messages if isinstance(msg, HumanMessage))
        ai_messages = sum(1 for msg in self.messages if isinstance(msg, AIMessage))
        
        return {
            "strategy": "buffer",
            "total_messages": len(self.messages),
            "system_messages": system_messages,
            "user_messages": user_messages,
            "ai_messages": ai_messages,
            "messages_added": self.messages_added,
            "messages_rotated": self.messages_rotated,
            "buffer_utilization": len(self.messages) / self.config.max_buffer_size,
            "max_buffer_size": self.config.max_buffer_size
        }
    
    def should_optimize(self) -> bool:
        """
        Check if buffer optimization should be triggered.
        
        Returns:
            True if buffer is at capacity
        """
        return len(self.messages) >= self.config.max_buffer_size
    
    def optimize_memory(self) -> None:
        """Optimize buffer by rotating older messages."""
        if self.should_optimize():
            self._rotate_messages()
    
    def _rotate_messages(self) -> None:
        """
        Rotate messages to maintain buffer size limit.
        
        Preserves system messages and keeps the most recent messages.
        """
        if self.config.preserve_system_messages:
            # Separate system messages from others
            system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
            other_messages = [msg for msg in self.messages if not isinstance(msg, SystemMessage)]
            
            # Calculate how many non-system messages we can keep
            available_slots = self.config.max_buffer_size - len(system_messages)
            if available_slots > 0:
                # Keep the most recent non-system messages
                recent_messages = other_messages[-available_slots:]
                self.messages = system_messages + recent_messages
                self.messages_rotated += len(other_messages) - len(recent_messages)
            else:
                # If we have too many system messages, keep only the most recent ones
                self.messages = system_messages[-self.config.max_buffer_size:]
                self.messages_rotated += len(other_messages)
        else:
            # Simple rotation without preserving system messages
            messages_to_remove = len(self.messages) - self.config.max_buffer_size
            self.messages = self.messages[messages_to_remove:]
            self.messages_rotated += messages_to_remove
        
        self.logger.debug(f"Rotated buffer for session {self.session_id}, now has {len(self.messages)} messages")


class SummaryMemoryStrategy(MemoryStrategy):
    """
    Summary memory strategy using LangChain's summarization capabilities.
    
    This strategy automatically summarizes older conversation parts when
    the buffer exceeds limits, maintaining conversation continuity while
    reducing token usage.
    """
    
    def __init__(self, config: MemoryConfig, session_id: int):
        """
        Initialize summary memory strategy.
        
        Args:
            config: Memory configuration
            session_id: Session identifier for isolation
        """
        super().__init__(config, session_id)
        self.messages: List[BaseMessage] = []
        self.summary_messages: List[BaseMessage] = []  # Summarized older messages
        self.recent_messages: List[BaseMessage] = []   # Recent detailed messages
        
        # Statistics
        self.messages_added = 0
        self.summaries_created = 0
        self.tokens_saved_estimate = 0
        
        # Initialize LangChain summarization (placeholder for now)
        self._summary_model = None  # Will be initialized when needed
    
    def add_message(self, message: BaseMessage) -> None:
        """
        Add a message to memory with automatic summarization.
        
        Args:
            message: Message to add to memory
        """
        self.messages.append(message)
        self.recent_messages.append(message)
        self.messages_added += 1
        
        # Check if summarization is needed
        if self.should_optimize():
            self.optimize_memory()
    
    def get_context(self) -> List[BaseMessage]:
        """
        Get conversation context including summaries and recent messages.
        
        Returns:
            Combined context with summaries and recent detailed messages
        """
        # Combine summary messages with recent messages
        context = []
        
        # Add system messages first (if preserving them)
        if self.config.preserve_system_messages:
            system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
            context.extend(system_messages)
        
        # Add summary messages
        context.extend(self.summary_messages)
        
        # Add recent detailed messages (excluding system messages if already added)
        if self.config.preserve_system_messages:
            recent_non_system = [msg for msg in self.recent_messages if not isinstance(msg, SystemMessage)]
            context.extend(recent_non_system)
        else:
            context.extend(self.recent_messages)
        
        return context
    
    def clear(self) -> None:
        """Clear all memory and reset statistics."""
        self.messages.clear()
        self.summary_messages.clear()
        self.recent_messages.clear()
        self.messages_added = 0
        self.summaries_created = 0
        self.tokens_saved_estimate = 0
        self.logger.debug(f"Cleared summary memory for session {self.session_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get summary memory statistics.
        
        Returns:
            Dictionary containing summary memory statistics
        """
        total_context_messages = len(self.get_context())
        
        return {
            "strategy": "summary",
            "total_messages": len(self.messages),
            "summary_messages": len(self.summary_messages),
            "recent_messages": len(self.recent_messages),
            "context_messages": total_context_messages,
            "messages_added": self.messages_added,
            "summaries_created": self.summaries_created,
            "tokens_saved_estimate": self.tokens_saved_estimate,
            "max_buffer_size": self.config.max_buffer_size,
            "max_tokens_before_summary": self.config.max_tokens_before_summary
        }
    
    def should_optimize(self) -> bool:
        """
        Check if summarization should be triggered.
        
        Returns:
            True if recent messages exceed the buffer limit
        """
        return len(self.recent_messages) > self.config.max_buffer_size
    
    def optimize_memory(self) -> None:
        """
        Optimize memory by summarizing older messages.
        
        Moves older messages from recent_messages to summary_messages
        after creating a summary.
        """
        if not self.should_optimize():
            return
        
        try:
            # Determine how many messages to summarize
            messages_to_summarize_count = len(self.recent_messages) - self.config.context_window_size
            if messages_to_summarize_count <= 0:
                return
            
            # Extract messages to summarize (excluding system messages if preserving them)
            messages_to_summarize = []
            remaining_messages = []
            
            for i, message in enumerate(self.recent_messages):
                if self.config.preserve_system_messages and isinstance(message, SystemMessage):
                    # Keep system messages in recent
                    remaining_messages.append(message)
                elif i < messages_to_summarize_count:
                    messages_to_summarize.append(message)
                else:
                    remaining_messages.append(message)
            
            if not messages_to_summarize:
                return
            
            # Create summary of older messages
            summary_text = self._create_summary(messages_to_summarize)
            
            # Create summary message
            summary_message = AIMessage(
                content=f"[CONVERSATION SUMMARY: {summary_text}]"
            )
            
            # Update memory structure
            self.summary_messages.append(summary_message)
            self.recent_messages = remaining_messages
            
            # Update statistics
            self.summaries_created += 1
            self.tokens_saved_estimate += self._estimate_tokens_saved(messages_to_summarize, summary_text)
            
            self.logger.info(
                f"Created summary for session {self.session_id}: "
                f"summarized {len(messages_to_summarize)} messages"
            )
            
        except Exception as e:
            self.logger.error(f"Error during memory optimization: {e}")
            # Continue without summarization if it fails
    
    def restore_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Restore memory state from a list of messages.
        
        Args:
            messages: Messages to restore from
        """
        # Clear current state
        self.clear()
        
        # Add messages and let automatic summarization handle optimization
        for message in messages:
            self.add_message(message)
    
    def _create_summary(self, messages: List[BaseMessage]) -> str:
        """
        Create a summary of the given messages.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Summary text
            
        Note:
            This is a placeholder implementation. In a full implementation,
            this would use LangChain's summarization capabilities with
            the configured summary model.
        """
        if not messages:
            return "No messages to summarize"
        
        # Placeholder implementation - create a simple summary
        user_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
        ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        
        summary_parts = []
        
        if user_messages:
            # Extract key topics from user messages
            user_topics = []
            for msg in user_messages[:3]:  # Sample first few messages
                content = msg.content[:100]  # First 100 chars
                user_topics.append(content)
            
            if user_topics:
                summary_parts.append(f"User discussed: {'; '.join(user_topics)}")
        
        if ai_messages:
            summary_parts.append(f"Assistant provided {len(ai_messages)} responses")
        
        summary = f"Conversation from {len(messages)} messages: " + ". ".join(summary_parts)
        
        # In a real implementation, this would use LangChain's summarization:
        # from langchain.chains.summarize import load_summarize_chain
        # summary_chain = load_summarize_chain(self._get_summary_model(), chain_type="stuff")
        # summary = summary_chain.run(messages)
        
        return summary
    
    def _estimate_tokens_saved(self, original_messages: List[BaseMessage], summary_text: str) -> int:
        """
        Estimate tokens saved by summarization.
        
        Args:
            original_messages: Original messages that were summarized
            summary_text: The summary text
            
        Returns:
            Estimated number of tokens saved
        """
        # Simple estimation: assume ~4 characters per token
        original_chars = sum(len(msg.content) for msg in original_messages)
        summary_chars = len(summary_text)
        
        original_tokens = original_chars // 4
        summary_tokens = summary_chars // 4
        
        return max(0, original_tokens - summary_tokens)
    
    def _get_summary_model(self):
        """
        Get or initialize the summary model.
        
        Returns:
            LangChain model for summarization
            
        Note:
            This is a placeholder. In a full implementation, this would
            initialize and return a ChatGoogleGenerativeAI instance
            configured for summarization.
        """
        if self._summary_model is None:
            # Placeholder - would initialize actual model here
            # from langchain_google_genai import ChatGoogleGenerativeAI
            # self._summary_model = ChatGoogleGenerativeAI(
            #     model=self.config.summary_model,
            #     temperature=0.3  # Lower temperature for consistent summaries
            # )
            pass
        
        return self._summary_model


class EntityMemoryStrategy(MemoryStrategy):
    """
    Entity memory strategy for extracting and maintaining important facts.
    
    This strategy extracts entities (names, dates, preferences, facts) from
    conversation messages and maintains them for context retrieval while
    keeping only recent detailed messages.
    """
    
    def __init__(self, config: MemoryConfig, session_id: int):
        """
        Initialize entity memory strategy.
        
        Args:
            config: Memory configuration
            session_id: Session identifier for isolation
        """
        super().__init__(config, session_id)
        self.messages: List[BaseMessage] = []
        self.recent_messages: List[BaseMessage] = []
        
        # Entity storage
        self.entities: Dict[str, Any] = {
            "names": set(),
            "dates": set(),
            "preferences": {},
            "facts": [],
            "topics": set(),
            "locations": set()
        }
        
        # Statistics
        self.messages_added = 0
        self.entities_extracted = 0
        self.facts_retained = 0
    
    def add_message(self, message: BaseMessage) -> None:
        """
        Add a message to memory and extract entities.
        
        Args:
            message: Message to add to memory
        """
        self.messages.append(message)
        self.recent_messages.append(message)
        self.messages_added += 1
        
        # Extract entities from the message
        if not isinstance(message, SystemMessage):
            self._extract_entities_from_message(message)
        
        # Manage recent messages buffer
        if len(self.recent_messages) > self.config.max_buffer_size:
            self._rotate_recent_messages()
    
    def get_context(self) -> List[BaseMessage]:
        """
        Get conversation context including entity facts and recent messages.
        
        Returns:
            Context with entity information and recent detailed messages
        """
        context = []
        
        # Add system messages first (if preserving them)
        if self.config.preserve_system_messages:
            system_messages = [msg for msg in self.messages if isinstance(msg, SystemMessage)]
            context.extend(system_messages)
        
        # Add entity context as an AI message if we have entities
        if self._has_significant_entities():
            entity_context = self._create_entity_context_message()
            context.append(entity_context)
        
        # Add recent detailed messages (excluding system messages if already added)
        if self.config.preserve_system_messages:
            recent_non_system = [msg for msg in self.recent_messages if not isinstance(msg, SystemMessage)]
            context.extend(recent_non_system)
        else:
            context.extend(self.recent_messages)
        
        return context
    
    def clear(self) -> None:
        """Clear all memory and entities."""
        self.messages.clear()
        self.recent_messages.clear()
        self.entities = {
            "names": set(),
            "dates": set(),
            "preferences": {},
            "facts": [],
            "topics": set(),
            "locations": set()
        }
        self.messages_added = 0
        self.entities_extracted = 0
        self.facts_retained = 0
        self.logger.debug(f"Cleared entity memory for session {self.session_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get entity memory statistics.
        
        Returns:
            Dictionary containing entity memory statistics
        """
        return {
            "strategy": "entity",
            "total_messages": len(self.messages),
            "recent_messages": len(self.recent_messages),
            "messages_added": self.messages_added,
            "entities_extracted": self.entities_extracted,
            "facts_retained": self.facts_retained,
            "entity_counts": {
                "names": len(self.entities["names"]),
                "dates": len(self.entities["dates"]),
                "preferences": len(self.entities["preferences"]),
                "facts": len(self.entities["facts"]),
                "topics": len(self.entities["topics"]),
                "locations": len(self.entities["locations"])
            },
            "max_buffer_size": self.config.max_buffer_size
        }
    
    def should_optimize(self) -> bool:
        """
        Check if entity optimization should be triggered.
        
        Returns:
            True if recent messages exceed buffer limit
        """
        return len(self.recent_messages) > self.config.max_buffer_size
    
    def optimize_memory(self) -> None:
        """
        Optimize memory by extracting entities from older messages.
        
        Moves information from older messages into entity storage.
        """
        if not self.should_optimize():
            return
        
        # Extract entities from messages that will be rotated out
        messages_to_rotate = len(self.recent_messages) - self.config.context_window_size
        if messages_to_rotate > 0:
            for i in range(messages_to_rotate):
                if i < len(self.recent_messages):
                    message = self.recent_messages[i]
                    if not isinstance(message, SystemMessage):
                        self._extract_entities_from_message(message)
        
        self._rotate_recent_messages()
    
    def restore_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Restore memory state from a list of messages.
        
        Args:
            messages: Messages to restore from
        """
        # Clear current state
        self.clear()
        
        # Add messages and extract entities
        for message in messages:
            self.add_message(message)
    
    def get_entities(self) -> Dict[str, Any]:
        """
        Get extracted entities.
        
        Returns:
            Dictionary of extracted entities
        """
        # Convert sets to lists for JSON serialization
        return {
            "names": list(self.entities["names"]),
            "dates": list(self.entities["dates"]),
            "preferences": dict(self.entities["preferences"]),
            "facts": list(self.entities["facts"]),
            "topics": list(self.entities["topics"]),
            "locations": list(self.entities["locations"])
        }
    
    def _extract_entities_from_message(self, message: BaseMessage) -> None:
        """
        Extract entities from a single message.
        
        Args:
            message: Message to extract entities from
            
        Note:
            This is a simplified implementation. In a full implementation,
            this would use NLP libraries or LangChain's entity extraction
            capabilities for more sophisticated entity recognition.
        """
        if not message.content:
            return
        
        content = message.content.lower()
        
        # Simple pattern-based entity extraction (placeholder implementation)
        
        # Extract potential names (capitalized words)
        import re
        
        # Names: Look for "my name is X" or "I'm X" patterns
        name_patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"call me (\w+)",
            r"i am (\w+)"
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) > 1:  # Avoid single letters
                    self.entities["names"].add(match.title())
                    self.entities_extracted += 1
        
        # Dates: Look for date patterns
        date_patterns = [
            r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
            r"\b(\d{4}-\d{2}-\d{2})\b",
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b"
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                self.entities["dates"].add(match)
                self.entities_extracted += 1
        
        # Preferences: Look for "I like/prefer/love" patterns
        preference_patterns = [
            r"i (like|love|prefer|enjoy) ([^.!?]+)",
            r"my favorite ([^.!?]+) is ([^.!?]+)"
        ]
        
        for pattern in preference_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) == 2:
                    preference_type = match[0]
                    preference_value = match[1].strip()
                    if preference_type not in self.entities["preferences"]:
                        self.entities["preferences"][preference_type] = []
                    self.entities["preferences"][preference_type].append(preference_value)
                    self.entities_extracted += 1
        
        # Topics: Extract key topics (simplified)
        topic_keywords = [
            "programming", "python", "javascript", "ai", "machine learning",
            "data science", "web development", "mobile", "database", "api",
            "frontend", "backend", "devops", "cloud", "security"
        ]
        
        for keyword in topic_keywords:
            if keyword in content:
                self.entities["topics"].add(keyword)
                self.entities_extracted += 1
        
        # Facts: Store important statements (simplified)
        fact_patterns = [
            r"i work (at|for) ([^.!?]+)",
            r"i live in ([^.!?]+)",
            r"i have ([^.!?]+)",
            r"i studied ([^.!?]+)"
        ]
        
        for pattern in fact_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    fact = " ".join(match).strip()
                else:
                    fact = match.strip()
                
                if fact and len(fact) > 3:
                    self.entities["facts"].append(fact)
                    self.facts_retained += 1
        
        # Locations: Extract location mentions
        location_patterns = [
            r"in ([A-Z][a-z]+ ?[A-Z]?[a-z]*)",  # City names
            r"from ([A-Z][a-z]+ ?[A-Z]?[a-z]*)",
            r"live in ([^.!?]+)",
            r"located in ([^.!?]+)"
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, message.content)  # Use original case
            for match in matches:
                location = match.strip()
                if len(location) > 2 and not location.lower() in ["the", "and", "or"]:
                    self.entities["locations"].add(location)
                    self.entities_extracted += 1
    
    def _has_significant_entities(self) -> bool:
        """
        Check if we have significant entities worth including in context.
        
        Returns:
            True if we have meaningful entities to include
        """
        return (
            len(self.entities["names"]) > 0 or
            len(self.entities["preferences"]) > 0 or
            len(self.entities["facts"]) > 0 or
            len(self.entities["topics"]) > 2  # Only if we have several topics
        )
    
    def _create_entity_context_message(self) -> AIMessage:
        """
        Create a context message containing entity information.
        
        Returns:
            AIMessage containing entity context
        """
        context_parts = []
        
        if self.entities["names"]:
            names = list(self.entities["names"])[:3]  # Limit to avoid too much context
            context_parts.append(f"Names mentioned: {', '.join(names)}")
        
        if self.entities["preferences"]:
            prefs = []
            for pref_type, values in list(self.entities["preferences"].items())[:2]:
                prefs.append(f"{pref_type}: {', '.join(values[:2])}")
            if prefs:
                context_parts.append(f"Preferences: {'; '.join(prefs)}")
        
        if self.entities["facts"]:
            facts = self.entities["facts"][-3:]  # Most recent facts
            context_parts.append(f"Key facts: {'; '.join(facts)}")
        
        if len(self.entities["topics"]) > 2:
            topics = list(self.entities["topics"])[:5]  # Limit topics
            context_parts.append(f"Topics discussed: {', '.join(topics)}")
        
        context_text = "[ENTITY CONTEXT: " + " | ".join(context_parts) + "]"
        
        return AIMessage(content=context_text)
    
    def _rotate_recent_messages(self) -> None:
        """
        Rotate recent messages to maintain buffer size.
        
        Keeps the most recent messages while extracting entities from older ones.
        """
        if len(self.recent_messages) <= self.config.max_buffer_size:
            return
        
        # Keep system messages and most recent messages
        if self.config.preserve_system_messages:
            system_messages = [msg for msg in self.recent_messages if isinstance(msg, SystemMessage)]
            other_messages = [msg for msg in self.recent_messages if not isinstance(msg, SystemMessage)]
            
            # Keep the most recent non-system messages
            available_slots = self.config.max_buffer_size - len(system_messages)
            if available_slots > 0:
                recent_messages = other_messages[-available_slots:]
                self.recent_messages = system_messages + recent_messages
            else:
                # If too many system messages, keep only the most recent ones
                self.recent_messages = system_messages[-self.config.max_buffer_size:]
        else:
            # Simple rotation without preserving system messages
            self.recent_messages = self.recent_messages[-self.config.max_buffer_size:]
        
        self.logger.debug(f"Rotated recent messages for session {self.session_id}, now has {len(self.recent_messages)} messages")


class MemoryManager:
    """
    Intelligent memory manager for conversation context.
    
    This class manages conversation memory using configurable strategies
    and provides session-specific context isolation. It serves as the main
    interface for memory operations and strategy management.
    """
    
    def __init__(
        self, 
        session_id: int, 
        config: Optional[Union[MemoryConfig, Dict[str, Any]]] = None
    ):
        """
        Initialize the memory manager with pluggable strategy support.
        
        Args:
            session_id: Unique session identifier for context isolation
            config: Memory configuration (MemoryConfig object or dict)
        """
        self.session_id = session_id
        self.logger = logging.getLogger(f"memory_manager_{session_id}")
        
        # Process configuration
        if config is None:
            self.config = MemoryConfig()
        elif isinstance(config, dict):
            self.config = MemoryConfig.from_dict(config)
        elif isinstance(config, MemoryConfig):
            self.config = config
        else:
            raise ValueError(f"Invalid config type: {type(config)}")
        
        # Initialize memory strategy based on configuration
        self.strategy = self._create_strategy(self.config.strategy)
        
        # Session isolation tracking
        self._session_active = True
        
        self.logger.info(
            f"Memory manager initialized for session {session_id} "
            f"with {self.config.strategy.value} strategy"
        )
    
    def add_message(self, message: BaseMessage) -> None:
        """
        Add a message to memory with session isolation.
        
        Args:
            message: Message to add to memory
            
        Raises:
            RuntimeError: If session is not active
            Exception: If memory operation fails
        """
        if not self._session_active:
            raise RuntimeError(f"Session {self.session_id} is not active")
        
        try:
            self.strategy.add_message(message)
            self.logger.debug(f"Added message to memory for session {self.session_id}")
            
            # Check if optimization is needed
            if self.strategy.should_optimize():
                self.strategy.optimize_memory()
                
        except Exception as e:
            self.logger.error(f"Error adding message to memory: {e}")
            raise
    
    def get_conversation_context(self) -> List[BaseMessage]:
        """
        Get the current conversation context for this session.
        
        Returns:
            List of messages representing the conversation context
            
        Raises:
            RuntimeError: If session is not active
            Exception: If memory retrieval fails
        """
        if not self._session_active:
            raise RuntimeError(f"Session {self.session_id} is not active")
        
        try:
            context = self.strategy.get_context()
            self.logger.debug(f"Retrieved {len(context)} messages from memory for session {self.session_id}")
            return context
        except Exception as e:
            self.logger.error(f"Error retrieving conversation context: {e}")
            raise
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive memory statistics for this session.
        
        Returns:
            Dictionary containing memory usage statistics
        """
        try:
            stats = self.strategy.get_memory_stats()
            stats.update({
                "session_id": self.session_id,
                "session_active": self._session_active,
                "config": self.config.to_dict()
            })
            return stats
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {e}")
            return {"error": str(e), "session_id": self.session_id}
    
    def clear_memory(self) -> None:
        """
        Clear all memory for this session.
        
        Raises:
            Exception: If memory clearing fails
        """
        try:
            self.strategy.clear()
            self.logger.info(f"Cleared memory for session {self.session_id}")
        except Exception as e:
            self.logger.error(f"Error clearing memory: {e}")
            raise
    
    def deactivate_session(self) -> None:
        """
        Deactivate this session to prevent further memory operations.
        
        This enforces session isolation by preventing operations on
        inactive sessions.
        """
        self._session_active = False
        self.logger.info(f"Deactivated session {self.session_id}")
    
    def reactivate_session(self) -> None:
        """Reactivate this session for memory operations."""
        self._session_active = True
        self.logger.info(f"Reactivated session {self.session_id}")
    
    def is_session_active(self) -> bool:
        """Check if this session is active."""
        return self._session_active
    
    def update_config(self, new_config: Union[MemoryConfig, Dict[str, Any]]) -> None:
        """
        Update memory configuration and recreate strategy if needed.
        
        Args:
            new_config: New memory configuration
        """
        # Process new configuration
        if isinstance(new_config, dict):
            new_config = MemoryConfig.from_dict(new_config)
        elif not isinstance(new_config, MemoryConfig):
            raise ValueError(f"Invalid config type: {type(new_config)}")
        
        # Check if strategy needs to change
        if new_config.strategy != self.config.strategy:
            # Save current context
            current_context = self.get_conversation_context()
            
            # Update config and recreate strategy
            self.config = new_config
            self.strategy = self._create_strategy(self.config.strategy)
            
            # Restore context to new strategy
            self.strategy.restore_from_messages(current_context)
            
            self.logger.info(f"Updated strategy to {self.config.strategy.value} for session {self.session_id}")
        else:
            # Just update config
            self.config = new_config
            self.logger.info(f"Updated configuration for session {self.session_id}")
    
    def restore_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Restore memory state from a list of messages.
        
        Args:
            messages: Messages to restore from
        """
        try:
            self.strategy.restore_from_messages(messages)
            self.logger.info(f"Restored {len(messages)} messages for session {self.session_id}")
        except Exception as e:
            self.logger.error(f"Error restoring messages: {e}")
            raise
    
    def _create_strategy(self, strategy_type: MemoryStrategyType) -> MemoryStrategy:
        """
        Create a memory strategy instance based on type.
        
        Args:
            strategy_type: Type of strategy to create
            
        Returns:
            Memory strategy instance
        """
        if strategy_type == MemoryStrategyType.BUFFER:
            return BufferMemoryStrategy(self.config, self.session_id)
        elif strategy_type == MemoryStrategyType.SUMMARY:
            return SummaryMemoryStrategy(self.config, self.session_id)
        elif strategy_type == MemoryStrategyType.ENTITY:
            return EntityMemoryStrategy(self.config, self.session_id)
        else:
            # For now, default to buffer strategy for unimplemented strategies
            # Hybrid strategy will be implemented in future tasks
            self.logger.warning(
                f"Strategy '{strategy_type.value}' not implemented, using buffer"
            )
            return BufferMemoryStrategy(self.config, self.session_id)
    
    def get_entities(self) -> Dict[str, Any]:
        """
        Get extracted entities from the current memory strategy.
        
        Returns:
            Dictionary of extracted entities
        """
        if isinstance(self.strategy, EntityMemoryStrategy):
            return self.strategy.get_entities()
        else:
            # For non-entity strategies, return empty entities
            return {
                "names": [],
                "dates": [],
                "preferences": {},
                "facts": [],
                "topics": [],
                "locations": []
            }
    
    # Legacy methods for backward compatibility
    def extract_entities(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        Extract entities from conversation messages.
        
        Args:
            messages: Messages to extract entities from
            
        Returns:
            Dictionary of extracted entities
            
        Note:
            This method is for backward compatibility. For entity extraction,
            use the EntityMemoryStrategy directly through get_entities().
        """
        if isinstance(self.strategy, EntityMemoryStrategy):
            # If using entity strategy, return current entities
            return self.strategy.get_entities()
        else:
            # For other strategies, create a temporary entity strategy to extract entities
            temp_strategy = EntityMemoryStrategy(self.config, self.session_id)
            for message in messages:
                temp_strategy.add_message(message)
            return temp_strategy.get_entities()
    
    def summarize_conversation(self, messages: List[BaseMessage]) -> str:
        """
        Summarize conversation messages.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Summary of the conversation
            
        Note:
            This is a placeholder implementation. Summarization
            will be implemented in future tasks.
        """
        # Placeholder implementation
        summary = f"Conversation summary for {len(messages)} messages"
        self.logger.debug(f"Conversation summarization placeholder called")
        return summary