"""
Unit tests for memory management system.

Tests different memory strategies (buffer, summary, entity, hybrid),
session isolation and cross-session information prevention,
and entity extraction and fact retention within sessions.
"""

import pytest
from unittest.mock import Mock, patch
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from backend.services.memory_manager import (
    MemoryManager,
    MemoryConfig,
    MemoryStrategyType,
    BufferMemoryStrategy,
    SummaryMemoryStrategy,
    EntityMemoryStrategy
)


class TestMemoryConfig:
    """Test MemoryConfig functionality."""
    
    def test_default_config(self):
        """Test default memory configuration."""
        config = MemoryConfig()
        
        assert config.strategy == MemoryStrategyType.BUFFER
        assert config.max_buffer_size == 20
        assert config.max_tokens_before_summary == 4000
        assert config.entity_extraction_enabled is True
        assert config.summary_model == "gemini-2.5-flash"
        assert config.session_isolation is True
        assert config.context_window_size == 10
        assert config.preserve_system_messages is True
    
    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "strategy": "summary",
            "max_buffer_size": 15,
            "max_tokens_before_summary": 3000,
            "entity_extraction_enabled": False,
            "custom_field": "custom_value"
        }
        
        config = MemoryConfig.from_dict(config_dict)
        
        assert config.strategy == MemoryStrategyType.SUMMARY
        assert config.max_buffer_size == 15
        assert config.max_tokens_before_summary == 3000
        assert config.entity_extraction_enabled is False
        assert config.extra_config["custom_field"] == "custom_value"
    
    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = MemoryConfig(
            strategy=MemoryStrategyType.ENTITY,
            max_buffer_size=25,
            extra_config={"test": "value"}
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["strategy"] == "entity"
        assert config_dict["max_buffer_size"] == 25
        assert config_dict["test"] == "value"
    
    def test_invalid_strategy_fallback(self):
        """Test fallback to buffer strategy for invalid strategy."""
        config_dict = {"strategy": "invalid_strategy"}
        
        config = MemoryConfig.from_dict(config_dict)
        
        assert config.strategy == MemoryStrategyType.BUFFER


class TestBufferMemoryStrategy:
    """Test buffer memory strategy functionality."""
    
    @pytest.fixture
    def buffer_strategy(self):
        """Create a buffer memory strategy for testing."""
        config = MemoryConfig(strategy=MemoryStrategyType.BUFFER, max_buffer_size=5)
        return BufferMemoryStrategy(config, session_id=123)
    
    def test_add_message(self, buffer_strategy):
        """Test adding messages to buffer."""
        message1 = HumanMessage(content="Hello")
        message2 = AIMessage(content="Hi there!")
        
        buffer_strategy.add_message(message1)
        buffer_strategy.add_message(message2)
        
        assert len(buffer_strategy.messages) == 2
        assert buffer_strategy.messages[0] == message1
        assert buffer_strategy.messages[1] == message2
        assert buffer_strategy.messages_added == 2
    
    def test_get_context(self, buffer_strategy):
        """Test getting context from buffer."""
        message1 = HumanMessage(content="Hello")
        message2 = AIMessage(content="Hi there!")
        
        buffer_strategy.add_message(message1)
        buffer_strategy.add_message(message2)
        
        context = buffer_strategy.get_context()
        
        assert len(context) == 2
        assert context[0] == message1
        assert context[1] == message2
        # Verify it's a copy
        assert context is not buffer_strategy.messages
    
    def test_buffer_rotation(self, buffer_strategy):
        """Test automatic buffer rotation when size limit exceeded."""
        # Add more messages than buffer size
        for i in range(7):
            message = HumanMessage(content=f"Message {i}")
            buffer_strategy.add_message(message)
        
        # Should have rotated to keep only max_buffer_size messages
        assert len(buffer_strategy.messages) == 5
        assert buffer_strategy.messages_rotated > 0
        
        # Should keep the most recent messages
        assert buffer_strategy.messages[-1].content == "Message 6"
    
    def test_system_message_preservation(self, buffer_strategy):
        """Test that system messages are preserved during rotation."""
        # Add system message
        system_msg = SystemMessage(content="You are helpful")
        buffer_strategy.add_message(system_msg)
        
        # Add many user/AI messages to trigger rotation
        for i in range(6):
            buffer_strategy.add_message(HumanMessage(content=f"Message {i}"))
        
        # System message should still be present
        system_messages = [msg for msg in buffer_strategy.messages if isinstance(msg, SystemMessage)]
        assert len(system_messages) == 1
        assert system_messages[0].content == "You are helpful"
    
    def test_clear_buffer(self, buffer_strategy):
        """Test clearing buffer memory."""
        buffer_strategy.add_message(HumanMessage(content="Hello"))
        buffer_strategy.add_message(AIMessage(content="Hi"))
        
        buffer_strategy.clear()
        
        assert len(buffer_strategy.messages) == 0
        assert buffer_strategy.messages_added == 0
        assert buffer_strategy.messages_rotated == 0
    
    def test_memory_stats(self, buffer_strategy):
        """Test getting buffer memory statistics."""
        buffer_strategy.add_message(SystemMessage(content="System"))
        buffer_strategy.add_message(HumanMessage(content="User"))
        buffer_strategy.add_message(AIMessage(content="AI"))
        
        stats = buffer_strategy.get_memory_stats()
        
        assert stats["strategy"] == "buffer"
        assert stats["total_messages"] == 3
        assert stats["system_messages"] == 1
        assert stats["user_messages"] == 1
        assert stats["ai_messages"] == 1
        assert stats["messages_added"] == 3
        assert stats["buffer_utilization"] == 3 / 5  # 3 messages out of 5 max
    
    def test_should_optimize(self, buffer_strategy):
        """Test optimization trigger logic."""
        # Should not optimize when buffer is not full
        assert buffer_strategy.should_optimize() is False
        
        # Fill buffer to capacity
        for i in range(5):
            buffer_strategy.add_message(HumanMessage(content=f"Message {i}"))
        
        # Should optimize when at capacity
        assert buffer_strategy.should_optimize() is True


class TestSummaryMemoryStrategy:
    """Test summary memory strategy functionality."""
    
    @pytest.fixture
    def summary_strategy(self):
        """Create a summary memory strategy for testing."""
        config = MemoryConfig(
            strategy=MemoryStrategyType.SUMMARY,
            max_buffer_size=5,
            context_window_size=3
        )
        return SummaryMemoryStrategy(config, session_id=123)
    
    def test_add_message(self, summary_strategy):
        """Test adding messages to summary strategy."""
        message1 = HumanMessage(content="Hello")
        message2 = AIMessage(content="Hi there!")
        
        summary_strategy.add_message(message1)
        summary_strategy.add_message(message2)
        
        assert len(summary_strategy.messages) == 2
        assert len(summary_strategy.recent_messages) == 2
        assert summary_strategy.messages_added == 2
    
    def test_get_context_with_summaries(self, summary_strategy):
        """Test getting context that includes summaries."""
        # Add system message
        system_msg = SystemMessage(content="You are helpful")
        summary_strategy.add_message(system_msg)
        
        # Add some messages
        summary_strategy.add_message(HumanMessage(content="Hello"))
        summary_strategy.add_message(AIMessage(content="Hi"))
        
        # Add a summary message manually for testing
        summary_msg = AIMessage(content="[CONVERSATION SUMMARY: Previous discussion]")
        summary_strategy.summary_messages.append(summary_msg)
        
        context = summary_strategy.get_context()
        
        # Should include system message, summary, and recent messages
        assert len(context) >= 3
        assert any(isinstance(msg, SystemMessage) for msg in context)
        assert any("[CONVERSATION SUMMARY:" in msg.content for msg in context)
    
    def test_summarization_trigger(self, summary_strategy):
        """Test that summarization is triggered when buffer exceeds limit."""
        # Add messages beyond buffer limit to trigger summarization
        for i in range(7):  # More than max_buffer_size (5)
            summary_strategy.add_message(HumanMessage(content=f"Message {i}"))
        
        # Should have created summaries
        assert len(summary_strategy.summary_messages) > 0 or len(summary_strategy.recent_messages) <= summary_strategy.config.max_buffer_size
    
    def test_clear_summary_memory(self, summary_strategy):
        """Test clearing summary memory."""
        summary_strategy.add_message(HumanMessage(content="Hello"))
        summary_strategy.summary_messages.append(AIMessage(content="Summary"))
        
        summary_strategy.clear()
        
        assert len(summary_strategy.messages) == 0
        assert len(summary_strategy.summary_messages) == 0
        assert len(summary_strategy.recent_messages) == 0
        assert summary_strategy.messages_added == 0
        assert summary_strategy.summaries_created == 0
    
    def test_memory_stats(self, summary_strategy):
        """Test getting summary memory statistics."""
        summary_strategy.add_message(HumanMessage(content="Hello"))
        summary_strategy.add_message(AIMessage(content="Hi"))
        summary_strategy.summary_messages.append(AIMessage(content="Summary"))
        
        stats = summary_strategy.get_memory_stats()
        
        assert stats["strategy"] == "summary"
        assert stats["total_messages"] == 2
        assert stats["summary_messages"] == 1
        assert stats["recent_messages"] == 2
        assert stats["messages_added"] == 2
    
    def test_restore_from_messages(self, summary_strategy):
        """Test restoring summary strategy from messages."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm good")
        ]
        
        summary_strategy.restore_from_messages(messages)
        
        assert len(summary_strategy.messages) == 4
        assert summary_strategy.messages_added == 4


class TestEntityMemoryStrategy:
    """Test entity memory strategy functionality."""
    
    @pytest.fixture
    def entity_strategy(self):
        """Create an entity memory strategy for testing."""
        config = MemoryConfig(
            strategy=MemoryStrategyType.ENTITY,
            max_buffer_size=5
        )
        return EntityMemoryStrategy(config, session_id=123)
    
    def test_add_message_and_extract_entities(self, entity_strategy):
        """Test adding messages and extracting entities."""
        # Message with name
        message1 = HumanMessage(content="My name is John and I like programming")
        entity_strategy.add_message(message1)
        
        # Message with preference
        message2 = HumanMessage(content="I prefer Python over JavaScript")
        entity_strategy.add_message(message2)
        
        assert len(entity_strategy.messages) == 2
        assert entity_strategy.entities_extracted > 0
        
        # Check extracted entities
        entities = entity_strategy.get_entities()
        assert "john" in [name.lower() for name in entities["names"]]
        assert "programming" in entities["topics"]
    
    def test_entity_extraction_patterns(self, entity_strategy):
        """Test various entity extraction patterns."""
        # Test name patterns
        entity_strategy.add_message(HumanMessage(content="My name is Alice"))
        entity_strategy.add_message(HumanMessage(content="I'm Bob"))
        entity_strategy.add_message(HumanMessage(content="Call me Charlie"))
        
        # Test date patterns
        entity_strategy.add_message(HumanMessage(content="I was born on 12/25/1990"))
        entity_strategy.add_message(HumanMessage(content="The meeting is on January 15, 2024"))
        
        # Test preferences
        entity_strategy.add_message(HumanMessage(content="I love coffee and tea"))
        entity_strategy.add_message(HumanMessage(content="My favorite color is blue"))
        
        # Test locations
        entity_strategy.add_message(HumanMessage(content="I live in New York"))
        entity_strategy.add_message(HumanMessage(content="I'm from California"))
        
        entities = entity_strategy.get_entities()
        
        # Verify extractions
        names = [name.lower() for name in entities["names"]]
        assert "alice" in names
        assert "bob" in names
        assert "charlie" in names
        
        assert len(entities["dates"]) > 0
        assert len(entities["preferences"]) > 0
        assert len(entities["locations"]) > 0
    
    def test_get_context_with_entities(self, entity_strategy):
        """Test getting context that includes entity information."""
        # Add messages with entities
        entity_strategy.add_message(HumanMessage(content="My name is David"))
        entity_strategy.add_message(HumanMessage(content="I like machine learning"))
        entity_strategy.add_message(AIMessage(content="That's interesting!"))
        
        context = entity_strategy.get_context()
        
        # Should include entity context message and recent messages
        assert len(context) >= 2
        
        # Check for entity context message
        entity_context_found = any(
            "[ENTITY CONTEXT:" in msg.content 
            for msg in context 
            if isinstance(msg, AIMessage)
        )
        assert entity_context_found
    
    def test_recent_message_rotation(self, entity_strategy):
        """Test rotation of recent messages while preserving entities."""
        # Add more messages than buffer size
        for i in range(7):
            entity_strategy.add_message(HumanMessage(content=f"Message {i} with topic programming"))
        
        # Should have rotated recent messages
        assert len(entity_strategy.recent_messages) <= entity_strategy.config.max_buffer_size
        
        # Should have extracted entities from rotated messages
        entities = entity_strategy.get_entities()
        assert "programming" in entities["topics"]
    
    def test_clear_entity_memory(self, entity_strategy):
        """Test clearing entity memory."""
        entity_strategy.add_message(HumanMessage(content="My name is Eve"))
        
        entity_strategy.clear()
        
        assert len(entity_strategy.messages) == 0
        assert len(entity_strategy.recent_messages) == 0
        assert len(entity_strategy.entities["names"]) == 0
        assert entity_strategy.messages_added == 0
        assert entity_strategy.entities_extracted == 0
    
    def test_memory_stats(self, entity_strategy):
        """Test getting entity memory statistics."""
        entity_strategy.add_message(HumanMessage(content="My name is Frank, I like AI"))
        
        stats = entity_strategy.get_memory_stats()
        
        assert stats["strategy"] == "entity"
        assert stats["total_messages"] == 1
        assert stats["recent_messages"] == 1
        assert stats["messages_added"] == 1
        assert stats["entities_extracted"] > 0
        assert "entity_counts" in stats
        assert stats["entity_counts"]["names"] > 0
    
    def test_has_significant_entities(self, entity_strategy):
        """Test checking for significant entities."""
        # Initially should not have significant entities
        assert entity_strategy._has_significant_entities() is False
        
        # Add message with entities
        entity_strategy.add_message(HumanMessage(content="My name is Grace"))
        
        # Should now have significant entities
        assert entity_strategy._has_significant_entities() is True


class TestMemoryManager:
    """Test MemoryManager functionality and session isolation."""
    
    def test_initialization_with_default_config(self):
        """Test memory manager initialization with default config."""
        manager = MemoryManager(session_id=123)
        
        assert manager.session_id == 123
        assert manager.config.strategy == MemoryStrategyType.BUFFER
        assert isinstance(manager.strategy, BufferMemoryStrategy)
        assert manager.is_session_active() is True
    
    def test_initialization_with_dict_config(self):
        """Test memory manager initialization with dictionary config."""
        config_dict = {
            "strategy": "summary",
            "max_buffer_size": 15
        }
        
        manager = MemoryManager(session_id=123, config=config_dict)
        
        assert manager.config.strategy == MemoryStrategyType.SUMMARY
        assert manager.config.max_buffer_size == 15
        assert isinstance(manager.strategy, SummaryMemoryStrategy)
    
    def test_initialization_with_memory_config(self):
        """Test memory manager initialization with MemoryConfig object."""
        config = MemoryConfig(strategy=MemoryStrategyType.ENTITY, max_buffer_size=25)
        
        manager = MemoryManager(session_id=123, config=config)
        
        assert manager.config.strategy == MemoryStrategyType.ENTITY
        assert manager.config.max_buffer_size == 25
        assert isinstance(manager.strategy, EntityMemoryStrategy)
    
    def test_add_message_success(self):
        """Test successful message addition."""
        manager = MemoryManager(session_id=123)
        message = HumanMessage(content="Hello")
        
        manager.add_message(message)
        
        context = manager.get_conversation_context()
        assert len(context) == 1
        assert context[0] == message
    
    def test_add_message_inactive_session(self):
        """Test adding message to inactive session raises error."""
        manager = MemoryManager(session_id=123)
        manager.deactivate_session()
        
        with pytest.raises(RuntimeError, match="Session 123 is not active"):
            manager.add_message(HumanMessage(content="Hello"))
    
    def test_get_conversation_context_inactive_session(self):
        """Test getting context from inactive session raises error."""
        manager = MemoryManager(session_id=123)
        manager.deactivate_session()
        
        with pytest.raises(RuntimeError, match="Session 123 is not active"):
            manager.get_conversation_context()
    
    def test_session_isolation(self):
        """Test that different sessions maintain isolated memory."""
        manager1 = MemoryManager(session_id=123)
        manager2 = MemoryManager(session_id=456)
        
        # Add different messages to each session
        manager1.add_message(HumanMessage(content="Hello from session 123"))
        manager2.add_message(HumanMessage(content="Hello from session 456"))
        
        # Verify isolation
        context1 = manager1.get_conversation_context()
        context2 = manager2.get_conversation_context()
        
        assert len(context1) == 1
        assert len(context2) == 1
        assert context1[0].content == "Hello from session 123"
        assert context2[0].content == "Hello from session 456"
    
    def test_cross_session_information_prevention(self):
        """Test that sessions cannot access each other's information."""
        manager1 = MemoryManager(session_id=123, config={"strategy": "entity"})
        manager2 = MemoryManager(session_id=456, config={"strategy": "entity"})
        
        # Add entity information to session 1
        manager1.add_message(HumanMessage(content="My name is Alice"))
        
        # Add different entity information to session 2
        manager2.add_message(HumanMessage(content="My name is Bob"))
        
        # Verify each session only has its own entities
        entities1 = manager1.get_entities()
        entities2 = manager2.get_entities()
        
        names1 = [name.lower() for name in entities1["names"]]
        names2 = [name.lower() for name in entities2["names"]]
        
        assert "alice" in names1
        assert "alice" not in names2
        assert "bob" in names2
        assert "bob" not in names1
    
    def test_get_memory_stats(self):
        """Test getting comprehensive memory statistics."""
        manager = MemoryManager(session_id=123)
        manager.add_message(HumanMessage(content="Hello"))
        
        stats = manager.get_memory_stats()
        
        assert stats["session_id"] == 123
        assert stats["session_active"] is True
        assert "config" in stats
        assert stats["strategy"] == "buffer"
        assert stats["total_messages"] == 1
    
    def test_clear_memory(self):
        """Test clearing memory."""
        manager = MemoryManager(session_id=123)
        manager.add_message(HumanMessage(content="Hello"))
        
        manager.clear_memory()
        
        context = manager.get_conversation_context()
        assert len(context) == 0
    
    def test_session_activation_deactivation(self):
        """Test session activation and deactivation."""
        manager = MemoryManager(session_id=123)
        
        # Initially active
        assert manager.is_session_active() is True
        
        # Deactivate
        manager.deactivate_session()
        assert manager.is_session_active() is False
        
        # Reactivate
        manager.reactivate_session()
        assert manager.is_session_active() is True
    
    def test_update_config_same_strategy(self):
        """Test updating config without changing strategy."""
        manager = MemoryManager(session_id=123)
        manager.add_message(HumanMessage(content="Hello"))
        
        new_config = {"strategy": "buffer", "max_buffer_size": 30}
        manager.update_config(new_config)
        
        assert manager.config.max_buffer_size == 30
        assert isinstance(manager.strategy, BufferMemoryStrategy)
        
        # Context should be preserved
        context = manager.get_conversation_context()
        assert len(context) == 1
    
    def test_update_config_different_strategy(self):
        """Test updating config with different strategy."""
        manager = MemoryManager(session_id=123)
        manager.add_message(HumanMessage(content="Hello"))
        
        new_config = MemoryConfig(strategy=MemoryStrategyType.ENTITY)
        manager.update_config(new_config)
        
        assert manager.config.strategy == MemoryStrategyType.ENTITY
        assert isinstance(manager.strategy, EntityMemoryStrategy)
        
        # Context should be restored to new strategy
        context = manager.get_conversation_context()
        assert len(context) >= 1  # May include entity context
    
    def test_restore_from_messages(self):
        """Test restoring memory from message list."""
        manager = MemoryManager(session_id=123)
        
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?")
        ]
        
        manager.restore_from_messages(messages)
        
        context = manager.get_conversation_context()
        assert len(context) == 3
        assert context[0].content == "Hello"
        assert context[2].content == "How are you?"
    
    def test_get_entities_with_entity_strategy(self):
        """Test getting entities with entity strategy."""
        manager = MemoryManager(session_id=123, config={"strategy": "entity"})
        manager.add_message(HumanMessage(content="My name is Helen"))
        
        entities = manager.get_entities()
        
        assert "names" in entities
        names = [name.lower() for name in entities["names"]]
        assert "helen" in names
    
    def test_get_entities_with_non_entity_strategy(self):
        """Test getting entities with non-entity strategy returns empty."""
        manager = MemoryManager(session_id=123, config={"strategy": "buffer"})
        manager.add_message(HumanMessage(content="My name is Ivan"))
        
        entities = manager.get_entities()
        
        # Should return empty entities for non-entity strategies
        assert entities["names"] == []
        assert entities["preferences"] == {}
        assert entities["facts"] == []
    
    def test_extract_entities_legacy_method(self):
        """Test legacy extract_entities method."""
        manager = MemoryManager(session_id=123, config={"strategy": "entity"})
        
        messages = [
            HumanMessage(content="My name is Jack"),
            HumanMessage(content="I like Python programming")
        ]
        
        entities = manager.extract_entities(messages)
        
        assert "names" in entities
        assert "topics" in entities
        names = [name.lower() for name in entities["names"]]
        assert "jack" in names
    
    def test_summarize_conversation_placeholder(self):
        """Test conversation summarization placeholder method."""
        manager = MemoryManager(session_id=123)
        
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        
        summary = manager.summarize_conversation(messages)
        
        assert isinstance(summary, str)
        assert "2 messages" in summary
    
    def test_error_handling_in_memory_operations(self):
        """Test error handling in memory operations."""
        manager = MemoryManager(session_id=123)
        
        # Mock strategy to raise exception
        manager.strategy.add_message = Mock(side_effect=Exception("Memory error"))
        
        with pytest.raises(Exception, match="Memory error"):
            manager.add_message(HumanMessage(content="Hello"))
    
    def test_memory_stats_error_handling(self):
        """Test error handling in memory stats retrieval."""
        manager = MemoryManager(session_id=123)
        
        # Mock strategy to raise exception
        manager.strategy.get_memory_stats = Mock(side_effect=Exception("Stats error"))
        
        stats = manager.get_memory_stats()
        
        assert "error" in stats
        assert stats["session_id"] == 123
    
    def test_invalid_config_type_raises_error(self):
        """Test that invalid config type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid config type"):
            MemoryManager(session_id=123, config="invalid_config")


class TestMemoryStrategyIntegration:
    """Test integration between different memory strategies."""
    
    def test_strategy_switching_preserves_context(self):
        """Test that switching strategies preserves conversation context."""
        # Start with buffer strategy
        manager = MemoryManager(session_id=123, config={"strategy": "buffer"})
        
        # Add some messages
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="My name is Kate")
        ]
        
        for msg in messages:
            manager.add_message(msg)
        
        # Switch to entity strategy
        manager.update_config({"strategy": "entity"})
        
        # Context should be preserved and entities extracted
        context = manager.get_conversation_context()
        entities = manager.get_entities()
        
        assert len(context) >= 3  # Original messages plus possible entity context
        names = [name.lower() for name in entities["names"]]
        assert "kate" in names
    
    def test_memory_optimization_across_strategies(self):
        """Test memory optimization behavior across different strategies."""
        configs = [
            {"strategy": "buffer", "max_buffer_size": 3},
            {"strategy": "summary", "max_buffer_size": 3},
            {"strategy": "entity", "max_buffer_size": 3}
        ]
        
        for config in configs:
            manager = MemoryManager(session_id=123, config=config)
            
            # Add more messages than buffer size
            for i in range(5):
                manager.add_message(HumanMessage(content=f"Message {i}"))
            
            # All strategies should handle optimization
            context = manager.get_conversation_context()
            stats = manager.get_memory_stats()
            
            # Context should be managed within reasonable limits
            assert len(context) <= 10  # Reasonable upper bound
            assert stats["total_messages"] == 5
    
    def test_session_isolation_across_strategies(self):
        """Test session isolation works across different memory strategies."""
        # Create managers with different strategies
        buffer_manager = MemoryManager(session_id=123, config={"strategy": "buffer"})
        entity_manager = MemoryManager(session_id=456, config={"strategy": "entity"})
        summary_manager = MemoryManager(session_id=789, config={"strategy": "summary"})
        
        # Add session-specific information
        buffer_manager.add_message(HumanMessage(content="Buffer session message"))
        entity_manager.add_message(HumanMessage(content="My name is Lisa, entity session"))
        summary_manager.add_message(HumanMessage(content="Summary session message"))
        
        # Verify isolation
        buffer_context = buffer_manager.get_conversation_context()
        entity_context = entity_manager.get_conversation_context()
        summary_context = summary_manager.get_conversation_context()
        
        # Each should only contain its own messages
        buffer_contents = [msg.content for msg in buffer_context]
        entity_contents = [msg.content for msg in entity_context]
        summary_contents = [msg.content for msg in summary_context]
        
        assert any("Buffer session" in content for content in buffer_contents)
        assert not any("Buffer session" in content for content in entity_contents)
        assert not any("Buffer session" in content for content in summary_contents)
        
        # Entity manager should have extracted entities only from its session
        entities = entity_manager.get_entities()
        names = [name.lower() for name in entities["names"]]
        assert "lisa" in names
        
        # Other managers should not have Lisa's information
        buffer_entities = buffer_manager.get_entities()
        summary_entities = summary_manager.get_entities()
        
        buffer_names = [name.lower() for name in buffer_entities["names"]]
        summary_names = [name.lower() for name in summary_entities["names"]]
        
        assert "lisa" not in buffer_names
        assert "lisa" not in summary_names