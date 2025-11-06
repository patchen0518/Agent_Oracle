"""
Unit tests for context optimization system.

Tests token calculation and usage optimization, automatic summarization
triggers and context compression, and relevance scoring and message prioritization.
"""

import pytest
from unittest.mock import Mock, patch
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from backend.services.context_optimizer import (
    ContextOptimizer,
    ContextConfig,
    OptimizationStrategy,
    MessageScore,
    SummarizationMiddleware
)


class TestContextConfig:
    """Test ContextConfig functionality."""
    
    def test_default_config(self):
        """Test default context configuration."""
        config = ContextConfig()
        
        assert config.max_tokens == 4000
        assert config.messages_to_keep_after_summary == 20
        assert config.relevance_threshold == 0.7
        assert config.enable_semantic_search is True
        assert config.summarization_trigger_ratio == 0.8
        assert config.optimization_strategy == OptimizationStrategy.HYBRID
        assert config.preserve_system_messages is True
        assert config.min_messages_for_optimization == 10
    
    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "max_tokens": 3000,
            "optimization_strategy": "relevance",
            "relevance_threshold": 0.8,
            "enable_semantic_search": False
        }
        
        config = ContextConfig.from_dict(config_dict)
        
        assert config.max_tokens == 3000
        assert config.optimization_strategy == OptimizationStrategy.RELEVANCE
        assert config.relevance_threshold == 0.8
        assert config.enable_semantic_search is False
    
    def test_invalid_strategy_fallback(self):
        """Test fallback to hybrid strategy for invalid strategy."""
        config_dict = {"optimization_strategy": "invalid_strategy"}
        
        config = ContextConfig.from_dict(config_dict)
        
        assert config.optimization_strategy == OptimizationStrategy.HYBRID


class TestMessageScore:
    """Test MessageScore functionality."""
    
    def test_message_score_creation(self):
        """Test creating MessageScore objects."""
        message = HumanMessage(content="Test message")
        score = MessageScore(
            message=message,
            relevance_score=0.8,
            token_count=10,
            position=5,
            is_system=False,
            is_recent=True
        )
        
        assert score.message == message
        assert score.relevance_score == 0.8
        assert score.token_count == 10
        assert score.position == 5
        assert score.is_system is False
        assert score.is_recent is True
    
    def test_weighted_score_calculation(self):
        """Test weighted score calculation with various factors."""
        message = HumanMessage(content="Test message")
        
        # Test basic score
        score = MessageScore(
            message=message,
            relevance_score=0.8,
            token_count=10,
            position=0,
            is_system=False,
            is_recent=False
        )
        
        # Base weighted score (0.8 * 0.95^0 = 0.8)
        assert abs(score.weighted_score - 0.8) < 0.01
        
        # Test system message boost
        score.is_system = True
        assert score.weighted_score > 0.8 * 1.5 * 0.9  # Should be boosted
        
        # Test recent message boost
        score.is_system = False
        score.is_recent = True
        assert score.weighted_score > 0.8 * 1.2 * 0.9  # Should be boosted
    
    def test_position_decay(self):
        """Test position decay in weighted score."""
        message = HumanMessage(content="Test message")
        
        # Earlier position (higher decay)
        score1 = MessageScore(
            message=message,
            relevance_score=0.8,
            token_count=10,
            position=10,
            is_system=False,
            is_recent=False
        )
        
        # Later position (lower decay)
        score2 = MessageScore(
            message=message,
            relevance_score=0.8,
            token_count=10,
            position=2,
            is_system=False,
            is_recent=False
        )
        
        # Later position should have higher weighted score
        assert score2.weighted_score > score1.weighted_score


class TestContextOptimizerInitialization:
    """Test ContextOptimizer initialization and configuration."""
    
    def test_default_initialization(self):
        """Test initialization with default configuration."""
        optimizer = ContextOptimizer()
        
        assert optimizer.config.max_tokens == 4000
        assert optimizer.config.optimization_strategy == OptimizationStrategy.HYBRID
        assert optimizer.session_id is None
        assert optimizer.optimizations_performed == 0
        assert optimizer.tokens_saved == 0
    
    def test_initialization_with_config(self):
        """Test initialization with custom configuration."""
        config = ContextConfig(max_tokens=3000, optimization_strategy=OptimizationStrategy.RELEVANCE)
        optimizer = ContextOptimizer(config=config, session_id=123)
        
        assert optimizer.config.max_tokens == 3000
        assert optimizer.config.optimization_strategy == OptimizationStrategy.RELEVANCE
        assert optimizer.session_id == 123
    
    def test_summarization_threshold_calculation(self):
        """Test automatic calculation of summarization threshold."""
        config = ContextConfig(max_tokens=4000, summarization_trigger_ratio=0.8)
        optimizer = ContextOptimizer(config=config)
        
        expected_threshold = int(4000 * 0.8)
        assert optimizer.summarization_threshold == expected_threshold


class TestTokenCalculation:
    """Test token calculation and usage optimization."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a context optimizer for testing."""
        config = ContextConfig(chars_per_token=4, system_message_weight=1.5)
        return ContextOptimizer(config=config)
    
    def test_calculate_token_usage_empty_messages(self, optimizer):
        """Test token calculation with empty message list."""
        tokens = optimizer.calculate_token_usage([])
        assert tokens == 0
    
    def test_calculate_token_usage_basic(self, optimizer):
        """Test basic token calculation."""
        messages = [
            HumanMessage(content="Hello world"),  # 11 chars / 4 + 5 overhead = 7.75 -> 7 tokens
            AIMessage(content="Hi there!")       # 9 chars / 4 + 5 overhead = 7.25 -> 7 tokens
        ]
        
        tokens = optimizer.calculate_token_usage(messages)
        
        # Should be approximately 14 tokens (7 + 7)
        assert 12 <= tokens <= 16
    
    def test_calculate_token_usage_system_message_weight(self, optimizer):
        """Test token calculation with system message weighting."""
        messages = [
            SystemMessage(content="You are helpful"),  # Should be weighted by 1.5
            HumanMessage(content="Hello world")
        ]
        
        tokens = optimizer.calculate_token_usage(messages)
        
        # System message should contribute more tokens due to weighting
        system_tokens = int((len("You are helpful") // 4) * 1.5) + 5
        user_tokens = len("Hello world") // 4 + 5
        expected_total = system_tokens + user_tokens
        
        assert abs(tokens - expected_total) <= 2  # Allow small variance
    
    def test_calculate_detailed_token_usage(self, optimizer):
        """Test detailed token usage calculation."""
        messages = [
            SystemMessage(content="System message"),
            HumanMessage(content="User message"),
            AIMessage(content="AI response")
        ]
        
        details = optimizer.calculate_detailed_token_usage(messages)
        
        assert details["total_tokens"] > 0
        assert details["message_count"] == 3
        assert details["average_tokens_per_message"] > 0
        assert len(details["message_breakdown"]) == 3
        
        # Check breakdown structure
        breakdown = details["message_breakdown"]
        assert breakdown[0]["type"] == "system"
        assert breakdown[1]["type"] == "human"
        assert breakdown[2]["type"] == "ai"
        
        for item in breakdown:
            assert "position" in item
            assert "char_count" in item
            assert "token_count" in item
            assert "content_preview" in item
    
    def test_calculate_token_usage_with_empty_content(self, optimizer):
        """Test token calculation with messages that have empty content."""
        messages = [
            HumanMessage(content=""),
            HumanMessage(content="Valid message"),
            HumanMessage(content=None)  # This should be handled gracefully
        ]
        
        # Should not raise an exception
        tokens = optimizer.calculate_token_usage(messages)
        
        # Should only count the valid message
        assert tokens > 0


class TestContextOptimization:
    """Test context optimization strategies."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a context optimizer for testing."""
        config = ContextConfig(
            max_tokens=100,  # Low limit to trigger optimization
            messages_to_keep_after_summary=5,
            min_messages_for_optimization=3
        )
        return ContextOptimizer(config=config)
    
    def test_optimize_context_empty_messages(self, optimizer):
        """Test optimization with empty message list."""
        result = optimizer.optimize_context([])
        assert result == []
    
    def test_optimize_context_too_few_messages(self, optimizer):
        """Test optimization with too few messages (below minimum)."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi")
        ]
        
        result = optimizer.optimize_context(messages)
        
        # Should return original messages unchanged
        assert result == messages
    
    def test_optimize_context_within_limits(self, optimizer):
        """Test optimization when messages are within token limits."""
        # Create short messages that won't exceed the token limit
        messages = [
            HumanMessage(content="Hi"),
            AIMessage(content="Hello"),
            HumanMessage(content="How are you?")
        ]
        
        result = optimizer.optimize_context(messages)
        
        # Should return original messages if within limits
        assert len(result) == len(messages)
    
    def test_optimize_context_exceeds_limits(self, optimizer):
        """Test optimization when messages exceed token limits."""
        # Create messages that will exceed the 100 token limit
        long_content = "This is a very long message that should exceed the token limit " * 10
        messages = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content=long_content),
            AIMessage(content=long_content),
            HumanMessage(content=long_content),
            AIMessage(content=long_content)
        ]
        
        result = optimizer.optimize_context(messages)
        
        # Should have fewer messages or shorter content
        assert len(result) <= len(messages)
        
        # Should preserve system messages
        system_messages = [msg for msg in result if isinstance(msg, SystemMessage)]
        assert len(system_messages) > 0
    
    def test_recency_optimization_strategy(self, optimizer):
        """Test recency-based optimization strategy."""
        optimizer.config.optimization_strategy = OptimizationStrategy.RECENCY
        
        # Create messages that exceed token limit
        long_content = "Long message content " * 20
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content=long_content),
            AIMessage(content=long_content),
            HumanMessage(content=long_content),
            AIMessage(content="Recent message")  # This should be kept
        ]
        
        result = optimizer._apply_recency_optimization(messages)
        
        # Should keep system messages and most recent messages
        assert any(isinstance(msg, SystemMessage) for msg in result)
        assert any("Recent message" in str(msg.content) for msg in result)
    
    def test_relevance_optimization_strategy(self, optimizer):
        """Test relevance-based optimization strategy."""
        optimizer.config.optimization_strategy = OptimizationStrategy.RELEVANCE
        
        messages = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="What is Python programming?"),
            AIMessage(content="Python is a programming language"),
            HumanMessage(content="Tell me about cats"),  # Less relevant
            AIMessage(content="Cats are animals"),
            HumanMessage(content="More about Python programming please")  # More relevant
        ]
        
        result = optimizer._apply_relevance_optimization(messages)
        
        # Should keep system messages and relevant messages
        assert any(isinstance(msg, SystemMessage) for msg in result)
        # Should prioritize Python-related messages
        python_messages = [msg for msg in result if "python" in str(msg.content).lower()]
        assert len(python_messages) > 0
    
    def test_hybrid_optimization_strategy(self, optimizer):
        """Test hybrid optimization strategy."""
        optimizer.config.optimization_strategy = OptimizationStrategy.HYBRID
        
        long_content = "Long message content " * 15
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content=long_content),
            AIMessage(content=long_content),
            HumanMessage(content=long_content),
            AIMessage(content="Recent relevant message")
        ]
        
        result = optimizer._apply_hybrid_optimization(messages)
        
        # Should apply intelligent selection
        assert len(result) <= len(messages)
        assert any(isinstance(msg, SystemMessage) for msg in result)


class TestSummarizationTriggers:
    """Test automatic summarization triggers and context compression."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a context optimizer for testing."""
        config = ContextConfig(
            max_tokens=200,
            summarization_trigger_ratio=0.8,  # Trigger at 160 tokens
            messages_to_keep_after_summary=3
        )
        return ContextOptimizer(config=config)
    
    def test_should_summarize_empty_messages(self, optimizer):
        """Test summarization trigger with empty messages."""
        assert optimizer.should_summarize([]) is False
    
    def test_should_summarize_below_threshold(self, optimizer):
        """Test summarization trigger below token threshold."""
        messages = [
            HumanMessage(content="Short message"),
            AIMessage(content="Short response")
        ]
        
        assert optimizer.should_summarize(messages) is False
    
    def test_should_summarize_above_threshold(self, optimizer):
        """Test summarization trigger above token threshold."""
        # Create messages that exceed the summarization threshold
        long_content = "This is a long message that will exceed the token threshold " * 10
        messages = [
            HumanMessage(content=long_content),
            AIMessage(content=long_content),
            HumanMessage(content=long_content),
            AIMessage(content=long_content),
            HumanMessage(content=long_content),
            AIMessage(content=long_content)
        ]
        
        assert optimizer.should_summarize(messages) is True
    
    def test_apply_summarization(self, optimizer):
        """Test applying summarization to messages."""
        # Create messages that need summarization
        messages = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="Question 1"),
            AIMessage(content="Answer 1"),
            HumanMessage(content="Question 2"),
            AIMessage(content="Answer 2"),
            HumanMessage(content="Question 3"),
            AIMessage(content="Answer 3"),
            HumanMessage(content="Recent question"),
            AIMessage(content="Recent answer")
        ]
        
        result = optimizer.apply_summarization(messages)
        
        # Should have fewer messages
        assert len(result) < len(messages)
        
        # Should preserve system messages
        system_messages = [msg for msg in result if isinstance(msg, SystemMessage)]
        assert len(system_messages) == 1
        
        # Should have a summary message
        summary_messages = [
            msg for msg in result 
            if isinstance(msg, AIMessage) and "[CONVERSATION SUMMARY:" in str(msg.content)
        ]
        assert len(summary_messages) == 1
        
        # Should keep recent messages
        assert any("Recent" in str(msg.content) for msg in result)
    
    def test_summarization_preserves_system_messages(self, optimizer):
        """Test that summarization preserves system messages."""
        messages = [
            SystemMessage(content="System instruction 1"),
            SystemMessage(content="System instruction 2"),
            HumanMessage(content="User message " * 20),
            AIMessage(content="AI response " * 20),
            HumanMessage(content="Another user message " * 20),
            AIMessage(content="Another AI response " * 20)
        ]
        
        result = optimizer.apply_summarization(messages)
        
        # Should preserve all system messages
        system_messages = [msg for msg in result if isinstance(msg, SystemMessage)]
        original_system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        assert len(system_messages) == len(original_system_messages)
    
    def test_create_conversation_summary(self, optimizer):
        """Test conversation summary creation."""
        messages = [
            HumanMessage(content="I want to learn Python programming"),
            AIMessage(content="Python is a great language for beginners"),
            HumanMessage(content="Can you show me some code examples?"),
            AIMessage(content="Here's a simple function: def hello(): print('Hello')")
        ]
        
        summary = optimizer._create_conversation_summary(messages)
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        # Should contain relevant information
        assert "user" in summary.lower() or "ai" in summary.lower()


class TestRelevanceScoring:
    """Test relevance scoring and message prioritization."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a context optimizer for testing."""
        config = ContextConfig(
            relevance_threshold=0.7,
            keyword_match_weight=2.0,
            enable_semantic_search=True
        )
        return ContextOptimizer(config=config)
    
    def test_score_messages_for_relevance_empty(self, optimizer):
        """Test relevance scoring with empty messages."""
        result = optimizer._score_messages_for_relevance([])
        assert result == []
    
    def test_score_messages_for_relevance_basic(self, optimizer):
        """Test basic relevance scoring."""
        messages = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="What is Python?"),
            AIMessage(content="Python is a programming language"),
            HumanMessage(content="Tell me about cats")
        ]
        
        scored_messages = optimizer._score_messages_for_relevance(messages)
        
        assert len(scored_messages) == 4
        
        # System message should have high relevance
        system_score = next(sm for sm in scored_messages if sm.is_system)
        assert system_score.relevance_score >= 0.9
        
        # All messages should have scores between 0 and 1
        for scored_msg in scored_messages:
            assert 0.0 <= scored_msg.relevance_score <= 1.0
            assert scored_msg.token_count > 0
    
    def test_calculate_message_relevance_system_message(self, optimizer):
        """Test relevance calculation for system messages."""
        message = SystemMessage(content="You are a helpful assistant")
        
        relevance = optimizer._calculate_message_relevance(message, [])
        
        # System messages should always have high relevance
        assert relevance >= 0.9
    
    def test_calculate_message_relevance_keyword_matching(self, optimizer):
        """Test relevance calculation with keyword matching."""
        context_keywords = ["python", "programming", "code"]
        
        # Message with matching keywords
        relevant_message = HumanMessage(content="I want to learn Python programming")
        relevance1 = optimizer._calculate_message_relevance(relevant_message, context_keywords)
        
        # Message without matching keywords
        irrelevant_message = HumanMessage(content="What's the weather like?")
        relevance2 = optimizer._calculate_message_relevance(irrelevant_message, context_keywords)
        
        # Relevant message should have higher score
        assert relevance1 > relevance2
    
    def test_calculate_message_relevance_question_patterns(self, optimizer):
        """Test relevance boost for question patterns."""
        # Question message
        question_message = HumanMessage(content="How do I write a Python function?")
        relevance1 = optimizer._calculate_message_relevance(question_message, [])
        
        # Statement message
        statement_message = HumanMessage(content="I wrote a Python function today.")
        relevance2 = optimizer._calculate_message_relevance(statement_message, [])
        
        # Question should have higher relevance
        assert relevance1 > relevance2
    
    def test_calculate_message_relevance_explanation_patterns(self, optimizer):
        """Test relevance boost for explanation patterns."""
        # Message with explanation patterns
        explanation_message = AIMessage(content="Because Python is interpreted, therefore it's easier to debug")
        relevance1 = optimizer._calculate_message_relevance(explanation_message, [])
        
        # Simple message
        simple_message = AIMessage(content="Yes, that's correct")
        relevance2 = optimizer._calculate_message_relevance(simple_message, [])
        
        # Explanation should have higher relevance
        assert relevance1 > relevance2
    
    def test_calculate_content_quality_score(self, optimizer):
        """Test content quality scoring."""
        # High-quality content with code
        high_quality = "Here's a Python function:\n```python\ndef hello():\n    print('Hello')\n```"
        score1 = optimizer._calculate_content_quality_score(high_quality)
        
        # Low-quality content
        low_quality = "ok"
        score2 = optimizer._calculate_content_quality_score(low_quality)
        
        # High-quality content should score higher
        assert score1 > score2
        
        # Scores should be within expected range
        assert 0.0 <= score1 <= 0.3
        assert 0.0 <= score2 <= 0.3
    
    def test_calculate_semantic_pattern_score(self, optimizer):
        """Test semantic pattern scoring."""
        # Content with question patterns
        question_content = "how do you solve this problem? what is the solution?"
        score1 = optimizer._calculate_semantic_pattern_score(question_content)
        
        # Content with explanation patterns
        explanation_content = "because of this, therefore we can conclude that the solution is"
        score2 = optimizer._calculate_semantic_pattern_score(explanation_content)
        
        # Simple content
        simple_content = "yes no maybe"
        score3 = optimizer._calculate_semantic_pattern_score(simple_content)
        
        # Question and explanation content should score higher than simple content
        assert score1 > score3
        assert score2 > score3
        
        # Scores should be within expected range
        assert 0.0 <= score1 <= 0.2
        assert 0.0 <= score2 <= 0.2
        assert 0.0 <= score3 <= 0.2
    
    def test_extract_conversation_keywords(self, optimizer):
        """Test keyword extraction from conversation."""
        messages = [
            HumanMessage(content="I want to learn Python programming and data science"),
            AIMessage(content="Python is great for data science and machine learning"),
            HumanMessage(content="Can you show me some pandas examples?")
        ]
        
        keywords = optimizer._extract_conversation_keywords(messages)
        
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        
        # Should extract relevant keywords
        keywords_lower = [kw.lower() for kw in keywords]
        assert "python" in keywords_lower
        assert "data" in keywords_lower or "science" in keywords_lower
    
    def test_extract_keywords_simple(self, optimizer):
        """Test simple keyword extraction."""
        text = "Python programming is fun and data science is interesting"
        
        keywords = optimizer._extract_keywords_simple(text)
        
        assert isinstance(keywords, list)
        assert "python" in keywords
        assert "programming" in keywords
        assert "data" in keywords
        assert "science" in keywords
        
        # Should filter out stop words
        assert "is" not in keywords
        assert "and" not in keywords
    
    def test_has_stem_match(self, optimizer):
        """Test stem-based matching."""
        # Test exact match
        assert optimizer._has_stem_match("program", "I like programming") is True
        
        # Test stem match
        assert optimizer._has_stem_match("programming", "I program daily") is True
        
        # Test no match
        assert optimizer._has_stem_match("cooking", "I like programming") is False
        
        # Test short words (should not match)
        assert optimizer._has_stem_match("is", "This is a test") is False


class TestContextOptimizerStatistics:
    """Test context optimizer statistics and monitoring."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a context optimizer for testing."""
        return ContextOptimizer(session_id=123)
    
    def test_get_optimization_stats_initial(self, optimizer):
        """Test getting initial optimization statistics."""
        stats = optimizer.get_optimization_stats()
        
        assert stats["optimizations_performed"] == 0
        assert stats["tokens_saved"] == 0
        assert stats["messages_summarized"] == 0
        assert stats["relevance_calculations"] == 0
        assert "config" in stats
        assert stats["config"]["max_tokens"] == 4000
    
    def test_reset_stats(self, optimizer):
        """Test resetting optimization statistics."""
        # Set some stats
        optimizer.optimizations_performed = 5
        optimizer.tokens_saved = 100
        optimizer.messages_summarized = 10
        optimizer.relevance_calculations = 20
        
        optimizer.reset_stats()
        
        assert optimizer.optimizations_performed == 0
        assert optimizer.tokens_saved == 0
        assert optimizer.messages_summarized == 0
        assert optimizer.relevance_calculations == 0
    
    def test_update_config(self, optimizer):
        """Test updating optimizer configuration."""
        new_config = ContextConfig(
            max_tokens=3000,
            optimization_strategy=OptimizationStrategy.RELEVANCE
        )
        
        optimizer.update_config(new_config)
        
        assert optimizer.config.max_tokens == 3000
        assert optimizer.config.optimization_strategy == OptimizationStrategy.RELEVANCE
        assert optimizer.summarization_threshold == int(3000 * 0.8)
    
    def test_analyze_message_relevance(self, optimizer):
        """Test message relevance analysis."""
        messages = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="What is Python?"),
            AIMessage(content="Python is a programming language"),
            HumanMessage(content="Tell me about cats")
        ]
        
        analysis = optimizer.analyze_message_relevance(messages)
        
        assert "total_messages" in analysis
        assert "non_system_messages" in analysis
        assert "relevance_stats" in analysis
        assert "message_breakdown" in analysis
        
        assert analysis["total_messages"] == 4
        assert analysis["non_system_messages"] == 3
        
        # Check relevance stats
        relevance_stats = analysis["relevance_stats"]
        assert "mean" in relevance_stats
        assert "min" in relevance_stats
        assert "max" in relevance_stats
        assert "above_threshold" in relevance_stats
        
        # Check message breakdown
        breakdown = analysis["message_breakdown"]
        assert len(breakdown) == 3  # Non-system messages only
        
        for item in breakdown:
            assert "position" in item
            assert "relevance_score" in item
            assert "weighted_score" in item
            assert "token_count" in item
            assert "content_preview" in item
    
    def test_get_context_compression_ratio(self, optimizer):
        """Test context compression ratio calculation."""
        messages = [
            HumanMessage(content="Long message " * 20),
            AIMessage(content="Long response " * 20),
            HumanMessage(content="Another long message " * 20)
        ]
        
        ratios = optimizer.get_context_compression_ratio(messages)
        
        # Should have ratios for all strategies
        for strategy in OptimizationStrategy:
            assert strategy.value in ratios
            
            if "error" not in ratios[strategy.value]:
                ratio_data = ratios[strategy.value]
                assert "compression_ratio" in ratio_data
                assert "tokens_saved" in ratio_data
                assert "messages_kept" in ratio_data
                assert "messages_original" in ratio_data
                
                # Compression ratio should be between 0 and 1
                assert 0.0 <= ratio_data["compression_ratio"] <= 1.0


class TestSummarizationMiddleware:
    """Test summarization middleware functionality."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a context optimizer for testing."""
        config = ContextConfig(max_tokens=100, summarization_trigger_ratio=0.5)
        return ContextOptimizer(config=config)
    
    @pytest.fixture
    def middleware(self, optimizer):
        """Create summarization middleware for testing."""
        return SummarizationMiddleware(optimizer)
    
    def test_middleware_initialization(self, middleware, optimizer):
        """Test middleware initialization."""
        assert middleware.context_optimizer == optimizer
        assert middleware.auto_summarizations == 0
        assert middleware.middleware_invocations == 0
    
    def test_process_messages_no_summarization_needed(self, middleware):
        """Test processing messages when no summarization is needed."""
        messages = [
            HumanMessage(content="Short message"),
            AIMessage(content="Short response")
        ]
        
        result = middleware.process_messages(messages)
        
        # Should return optimized messages
        assert isinstance(result, list)
        assert middleware.middleware_invocations == 1
        assert middleware.auto_summarizations == 0
    
    def test_process_messages_with_summarization(self, middleware):
        """Test processing messages when summarization is triggered."""
        # Create messages that will trigger summarization
        long_content = "Very long message content " * 20
        messages = [
            HumanMessage(content=long_content),
            AIMessage(content=long_content),
            HumanMessage(content=long_content),
            AIMessage(content=long_content)
        ]
        
        result = middleware.process_messages(messages)
        
        # Should have triggered summarization
        assert isinstance(result, list)
        assert middleware.middleware_invocations == 1
        assert middleware.auto_summarizations == 1
        
        # Result should be shorter than original
        assert len(result) <= len(messages)
    
    def test_get_middleware_stats(self, middleware):
        """Test getting middleware statistics."""
        # Process some messages to generate stats
        middleware.process_messages([HumanMessage(content="Test")])
        middleware.process_messages([HumanMessage(content="Test")])
        
        stats = middleware.get_middleware_stats()
        
        assert stats["middleware_invocations"] == 2
        assert stats["auto_summarizations"] >= 0
        assert "summarization_rate" in stats
        assert 0.0 <= stats["summarization_rate"] <= 1.0
    
    def test_reset_middleware_stats(self, middleware):
        """Test resetting middleware statistics."""
        # Set some stats
        middleware.auto_summarizations = 5
        middleware.middleware_invocations = 10
        
        middleware.reset_stats()
        
        assert middleware.auto_summarizations == 0
        assert middleware.middleware_invocations == 0
    
    def test_middleware_error_handling(self, middleware):
        """Test middleware error handling."""
        # Mock the optimizer to raise an exception
        middleware.context_optimizer.should_summarize = Mock(side_effect=Exception("Test error"))
        
        messages = [HumanMessage(content="Test message")]
        
        # Should not raise exception, should return original messages
        result = middleware.process_messages(messages)
        
        assert result == messages
        assert middleware.middleware_invocations == 1


class TestContextOptimizerIntegration:
    """Test integration scenarios for context optimization."""
    
    def test_full_optimization_workflow(self):
        """Test complete optimization workflow."""
        config = ContextConfig(
            max_tokens=200,
            optimization_strategy=OptimizationStrategy.HYBRID,
            messages_to_keep_after_summary=3
        )
        optimizer = ContextOptimizer(config=config, session_id=123)
        
        # Create a conversation that will need optimization
        messages = [
            SystemMessage(content="You are a helpful programming assistant"),
            HumanMessage(content="What is Python programming?"),
            AIMessage(content="Python is a high-level programming language known for its simplicity"),
            HumanMessage(content="Can you show me a simple example?"),
            AIMessage(content="Here's a simple Python function: def greet(name): return f'Hello, {name}!'"),
            HumanMessage(content="How do I run this code?"),
            AIMessage(content="You can run Python code by saving it to a .py file and executing it"),
            HumanMessage(content="What about data structures in Python?"),
            AIMessage(content="Python has built-in data structures like lists, dictionaries, sets, and tuples")
        ]
        
        # Optimize the context
        result = optimizer.optimize_context(messages)
        
        # Verify optimization occurred
        assert len(result) <= len(messages)
        assert optimizer.optimizations_performed > 0
        
        # System message should be preserved
        system_messages = [msg for msg in result if isinstance(msg, SystemMessage)]
        assert len(system_messages) > 0
        
        # Should maintain conversation coherence
        assert len(result) > 0
    
    def test_optimization_with_middleware(self):
        """Test optimization through summarization middleware."""
        config = ContextConfig(max_tokens=150, summarization_trigger_ratio=0.6)
        optimizer = ContextOptimizer(config=config)
        middleware = SummarizationMiddleware(optimizer)
        
        # Create messages that will trigger middleware summarization
        long_content = "This is a detailed explanation about programming concepts " * 5
        messages = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content=long_content),
            AIMessage(content=long_content),
            HumanMessage(content=long_content),
            AIMessage(content="Recent response")
        ]
        
        result = middleware.process_messages(messages)
        
        # Should have processed through middleware
        assert middleware.middleware_invocations > 0
        assert len(result) <= len(messages)
        
        # Should preserve important elements
        assert any(isinstance(msg, SystemMessage) for msg in result)
        assert any("Recent response" in str(msg.content) for msg in result)
    
    def test_strategy_comparison(self):
        """Test different optimization strategies on the same data."""
        messages = [
            SystemMessage(content="System message"),
            HumanMessage(content="Question about Python programming"),
            AIMessage(content="Python is a programming language"),
            HumanMessage(content="Tell me about cats and dogs"),
            AIMessage(content="Cats and dogs are pets"),
            HumanMessage(content="More about Python please"),
            AIMessage(content="Python has many libraries for programming")
        ]
        
        strategies = [
            OptimizationStrategy.RECENCY,
            OptimizationStrategy.RELEVANCE,
            OptimizationStrategy.HYBRID
        ]
        
        results = {}
        
        for strategy in strategies:
            config = ContextConfig(
                max_tokens=150,
                optimization_strategy=strategy,
                messages_to_keep_after_summary=3
            )
            optimizer = ContextOptimizer(config=config)
            
            result = optimizer.optimize_context(messages)
            results[strategy] = result
        
        # All strategies should return valid results
        for strategy, result in results.items():
            assert isinstance(result, list)
            assert len(result) > 0
            assert len(result) <= len(messages)
            
            # All should preserve system messages
            system_count = sum(1 for msg in result if isinstance(msg, SystemMessage))
            assert system_count > 0
        
        # Results may differ between strategies
        # This is expected as each strategy has different selection criteria