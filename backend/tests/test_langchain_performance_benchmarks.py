"""
Performance benchmarking tests for LangChain integration.

Tests benchmarking LangChain integration vs current implementation performance,
memory strategy performance with different conversation lengths,
and token usage reduction and response time improvements.
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, SQLModel

from backend.services.session_chat_service import SessionChatService
from backend.services.session_service import SessionService
from backend.services.langchain_client import LangChainClient
from backend.services.langchain_chat_session import LangChainChatSession
from backend.services.gemini_client import GeminiClient, ChatSession
from backend.services.memory_manager import MemoryManager, MemoryConfig, MemoryStrategyType
from backend.services.context_optimizer import ContextOptimizer, ContextConfig, OptimizationStrategy
from backend.models.session_models import SessionCreate, MessageCreate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(test_engine):
    """Create a database session for testing."""
    with Session(test_engine) as session:
        yield session


class PerformanceBenchmark:
    """Helper class for performance benchmarking."""
    
    def __init__(self):
        self.results = {}
    
    def time_operation(self, operation_name: str, operation_func, *args, **kwargs):
        """Time an operation and store the result."""
        start_time = time.time()
        result = operation_func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        self.results[operation_name] = {
            "execution_time": execution_time,
            "result": result,
            "timestamp": datetime.now()
        }
        
        return result
    
    async def time_async_operation(self, operation_name: str, operation_func, *args, **kwargs):
        """Time an async operation and store the result."""
        start_time = time.time()
        result = await operation_func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        self.results[operation_name] = {
            "execution_time": execution_time,
            "result": result,
            "timestamp": datetime.now()
        }
        
        return result
    
    def get_performance_comparison(self, baseline_op: str, comparison_op: str) -> Dict[str, Any]:
        """Compare performance between two operations."""
        if baseline_op not in self.results or comparison_op not in self.results:
            return {"error": "Missing benchmark results"}
        
        baseline_time = self.results[baseline_op]["execution_time"]
        comparison_time = self.results[comparison_op]["execution_time"]
        
        improvement_ratio = baseline_time / comparison_time if comparison_time > 0 else float('inf')
        improvement_percentage = ((baseline_time - comparison_time) / baseline_time) * 100 if baseline_time > 0 else 0
        
        return {
            "baseline_time": baseline_time,
            "comparison_time": comparison_time,
            "improvement_ratio": improvement_ratio,
            "improvement_percentage": improvement_percentage,
            "is_faster": comparison_time < baseline_time
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all benchmark results."""
        if not self.results:
            return {"error": "No benchmark results available"}
        
        times = [result["execution_time"] for result in self.results.values()]
        
        return {
            "total_operations": len(self.results),
            "total_time": sum(times),
            "average_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "operations": list(self.results.keys())
        }


class TestLangChainVsCurrentImplementation:
    """Test benchmarking LangChain integration vs current implementation performance."""
    
    @pytest.fixture
    def mock_gemini_client(self):
        """Create a mock Gemini client for baseline comparison."""
        client = Mock(spec=GeminiClient)
        chat_session = Mock(spec=ChatSession)
        chat_session.send_message.return_value = "Baseline Gemini response"
        client.create_chat_session.return_value = chat_session
        return client
    
    @pytest.fixture
    def mock_langchain_client(self):
        """Create a mock LangChain client for comparison."""
        client = Mock(spec=LangChainClient)
        chat_session = Mock(spec=LangChainChatSession)
        chat_session.send_message.return_value = "LangChain response"
        chat_session.get_optimization_stats.return_value = {
            "optimizer": {"optimizations_performed": 1, "tokens_saved": 50}
        }
        client.get_or_create_session.return_value = chat_session
        return client
    
    @pytest.mark.asyncio
    async def test_single_message_performance_comparison(
        self, 
        db_session, 
        mock_gemini_client, 
        mock_langchain_client
    ):
        """Compare single message performance between implementations."""
        benchmark = PerformanceBenchmark()
        
        # Create test session
        session_service = SessionService(db_session)
        test_session = await session_service.create_session(SessionCreate(title="Performance Test"))
        
        # Benchmark baseline Gemini implementation
        baseline_service = SessionChatService(db_session, mock_gemini_client)
        await benchmark.time_async_operation(
            "baseline_single_message",
            baseline_service.send_message,
            test_session.id,
            "Performance test message"
        )
        
        # Benchmark LangChain implementation
        langchain_service = SessionChatService(db_session, mock_langchain_client)
        await benchmark.time_async_operation(
            "langchain_single_message",
            langchain_service.send_message,
            test_session.id,
            "Performance test message"
        )
        
        # Compare performance
        comparison = benchmark.get_performance_comparison(
            "baseline_single_message",
            "langchain_single_message"
        )
        
        # Verify both implementations work
        assert "error" not in comparison
        assert comparison["baseline_time"] > 0
        assert comparison["comparison_time"] > 0
        
        # Log performance results
        print(f"Single Message Performance Comparison:")
        print(f"  Baseline: {comparison['baseline_time']:.4f}s")
        print(f"  LangChain: {comparison['comparison_time']:.4f}s")
        print(f"  Improvement: {comparison['improvement_percentage']:.2f}%")
    
    @pytest.mark.asyncio
    async def test_conversation_flow_performance_comparison(
        self, 
        db_session, 
        mock_gemini_client, 
        mock_langchain_client
    ):
        """Compare conversation flow performance between implementations."""
        benchmark = PerformanceBenchmark()
        
        # Create test sessions
        session_service = SessionService(db_session)
        baseline_session = await session_service.create_session(SessionCreate(title="Baseline Test"))
        langchain_session = await session_service.create_session(SessionCreate(title="LangChain Test"))
        
        # Test messages for conversation flow
        test_messages = [
            "Hello, how are you?",
            "What is Python programming?",
            "Can you explain functions?",
            "How do I handle errors?",
            "What about data structures?"
        ]
        
        # Benchmark baseline implementation
        baseline_service = SessionChatService(db_session, mock_gemini_client)
        
        async def baseline_conversation():
            for message in test_messages:
                await baseline_service.send_message(baseline_session.id, message)
        
        await benchmark.time_async_operation(
            "baseline_conversation_flow",
            baseline_conversation
        )
        
        # Benchmark LangChain implementation
        langchain_service = SessionChatService(db_session, mock_langchain_client)
        
        async def langchain_conversation():
            for message in test_messages:
                await langchain_service.send_message(langchain_session.id, message)
        
        await benchmark.time_async_operation(
            "langchain_conversation_flow",
            langchain_conversation
        )
        
        # Compare performance
        comparison = benchmark.get_performance_comparison(
            "baseline_conversation_flow",
            "langchain_conversation_flow"
        )
        
        # Verify results
        assert "error" not in comparison
        
        # Verify message counts
        baseline_messages = await session_service.get_session_messages(baseline_session.id)
        langchain_messages = await session_service.get_session_messages(langchain_session.id)
        
        assert len(baseline_messages) == len(test_messages) * 2  # user + assistant per message
        assert len(langchain_messages) == len(test_messages) * 2
        
        print(f"Conversation Flow Performance Comparison:")
        print(f"  Baseline: {comparison['baseline_time']:.4f}s")
        print(f"  LangChain: {comparison['comparison_time']:.4f}s")
        print(f"  Messages processed: {len(test_messages)}")
        print(f"  Improvement: {comparison['improvement_percentage']:.2f}%")
    
    @pytest.mark.asyncio
    async def test_streaming_performance_comparison(
        self, 
        db_session, 
        mock_gemini_client, 
        mock_langchain_client
    ):
        """Compare streaming performance between implementations."""
        benchmark = PerformanceBenchmark()
        
        # Setup streaming mocks
        mock_gemini_session = Mock(spec=ChatSession)
        mock_gemini_session.send_message_stream.return_value = iter([
            "Baseline", " streaming", " response"
        ])
        mock_gemini_client.create_chat_session.return_value = mock_gemini_session
        
        mock_langchain_session = Mock(spec=LangChainChatSession)
        mock_langchain_session.send_message_stream.return_value = iter([
            "LangChain", " streaming", " response"
        ])
        mock_langchain_client.get_or_create_session.return_value = mock_langchain_session
        
        # Create test sessions
        session_service = SessionService(db_session)
        baseline_session = await session_service.create_session(SessionCreate(title="Baseline Streaming"))
        langchain_session = await session_service.create_session(SessionCreate(title="LangChain Streaming"))
        
        # Benchmark baseline streaming
        baseline_service = SessionChatService(db_session, mock_gemini_client)
        
        async def baseline_streaming():
            chunks = []
            async for chunk in baseline_service.send_message_stream(baseline_session.id, "Stream test"):
                chunks.append(chunk)
            return chunks
        
        baseline_chunks = await benchmark.time_async_operation(
            "baseline_streaming",
            baseline_streaming
        )
        
        # Benchmark LangChain streaming
        langchain_service = SessionChatService(db_session, mock_langchain_client)
        
        async def langchain_streaming():
            chunks = []
            async for chunk in langchain_service.send_message_stream(langchain_session.id, "Stream test"):
                chunks.append(chunk)
            return chunks
        
        langchain_chunks = await benchmark.time_async_operation(
            "langchain_streaming",
            langchain_streaming
        )
        
        # Compare performance
        comparison = benchmark.get_performance_comparison(
            "baseline_streaming",
            "langchain_streaming"
        )
        
        # Verify streaming worked
        assert len(baseline_chunks) == 3
        assert len(langchain_chunks) == 3
        assert "".join(baseline_chunks) == "Baseline streaming response"
        assert "".join(langchain_chunks) == "LangChain streaming response"
        
        print(f"Streaming Performance Comparison:")
        print(f"  Baseline: {comparison['baseline_time']:.4f}s")
        print(f"  LangChain: {comparison['comparison_time']:.4f}s")
        print(f"  Chunks processed: {len(baseline_chunks)}")
        print(f"  Improvement: {comparison['improvement_percentage']:.2f}%")
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(
        self, 
        db_session, 
        mock_gemini_client, 
        mock_langchain_client
    ):
        """Compare concurrent request handling performance."""
        benchmark = PerformanceBenchmark()
        
        # Create multiple test sessions
        session_service = SessionService(db_session)
        baseline_sessions = []
        langchain_sessions = []
        
        for i in range(5):
            baseline_session = await session_service.create_session(
                SessionCreate(title=f"Baseline Concurrent {i}")
            )
            langchain_session = await session_service.create_session(
                SessionCreate(title=f"LangChain Concurrent {i}")
            )
            baseline_sessions.append(baseline_session)
            langchain_sessions.append(langchain_session)
        
        # Benchmark baseline concurrent requests
        baseline_service = SessionChatService(db_session, mock_gemini_client)
        
        async def baseline_concurrent():
            tasks = []
            for session in baseline_sessions:
                task = baseline_service.send_message(session.id, f"Concurrent test {session.id}")
                tasks.append(task)
            return await asyncio.gather(*tasks)
        
        baseline_results = await benchmark.time_async_operation(
            "baseline_concurrent",
            baseline_concurrent
        )
        
        # Benchmark LangChain concurrent requests
        langchain_service = SessionChatService(db_session, mock_langchain_client)
        
        async def langchain_concurrent():
            tasks = []
            for session in langchain_sessions:
                task = langchain_service.send_message(session.id, f"Concurrent test {session.id}")
                tasks.append(task)
            return await asyncio.gather(*tasks)
        
        langchain_results = await benchmark.time_async_operation(
            "langchain_concurrent",
            langchain_concurrent
        )
        
        # Compare performance
        comparison = benchmark.get_performance_comparison(
            "baseline_concurrent",
            "langchain_concurrent"
        )
        
        # Verify all requests completed
        assert len(baseline_results) == 5
        assert len(langchain_results) == 5
        
        print(f"Concurrent Requests Performance Comparison:")
        print(f"  Baseline: {comparison['baseline_time']:.4f}s")
        print(f"  LangChain: {comparison['comparison_time']:.4f}s")
        print(f"  Concurrent requests: 5")
        print(f"  Improvement: {comparison['improvement_percentage']:.2f}%")


class TestMemoryStrategyPerformance:
    """Test memory strategy performance with different conversation lengths."""
    
    def create_test_messages(self, count: int) -> List[HumanMessage | AIMessage]:
        """Create test messages for performance testing."""
        messages = []
        for i in range(count):
            if i % 2 == 0:
                messages.append(HumanMessage(content=f"User message {i}: This is a test message with some content"))
            else:
                messages.append(AIMessage(content=f"AI message {i}: This is a response with relevant information"))
        return messages
    
    def test_buffer_memory_strategy_performance(self):
        """Test buffer memory strategy performance with different conversation lengths."""
        benchmark = PerformanceBenchmark()
        
        conversation_lengths = [10, 50, 100, 200, 500]
        
        for length in conversation_lengths:
            # Create memory manager with buffer strategy
            config = MemoryConfig(
                strategy=MemoryStrategyType.BUFFER,
                max_buffer_size=50
            )
            memory_manager = MemoryManager(session_id=123, config=config)
            
            # Create test messages
            messages = self.create_test_messages(length)
            
            # Benchmark adding messages
            def add_messages():
                for message in messages:
                    memory_manager.add_message(message)
                return memory_manager.get_conversation_context()
            
            context = benchmark.time_operation(
                f"buffer_strategy_{length}_messages",
                add_messages
            )
            
            # Verify buffer strategy worked
            assert len(context) <= config.max_buffer_size
            
            # Get memory stats
            stats = memory_manager.get_memory_stats()
            assert stats["strategy"] == "buffer"
            assert stats["total_messages"] == length
        
        # Analyze performance scaling
        results = benchmark.results
        print("Buffer Memory Strategy Performance:")
        for length in conversation_lengths:
            key = f"buffer_strategy_{length}_messages"
            time_taken = results[key]["execution_time"]
            print(f"  {length} messages: {time_taken:.4f}s")
    
    def test_summary_memory_strategy_performance(self):
        """Test summary memory strategy performance with different conversation lengths."""
        benchmark = PerformanceBenchmark()
        
        conversation_lengths = [10, 50, 100, 200, 500]
        
        for length in conversation_lengths:
            # Create memory manager with summary strategy
            config = MemoryConfig(
                strategy=MemoryStrategyType.SUMMARY,
                max_buffer_size=20,
                max_tokens_before_summary=1000
            )
            memory_manager = MemoryManager(session_id=123, config=config)
            
            # Create test messages
            messages = self.create_test_messages(length)
            
            # Benchmark adding messages with summarization
            def add_messages_with_summary():
                for message in messages:
                    memory_manager.add_message(message)
                return memory_manager.get_conversation_context()
            
            context = benchmark.time_operation(
                f"summary_strategy_{length}_messages",
                add_messages_with_summary
            )
            
            # Verify summary strategy worked
            stats = memory_manager.get_memory_stats()
            assert stats["strategy"] == "summary"
            assert stats["total_messages"] == length
            
            # For longer conversations, should have created summaries
            if length > 50:
                assert stats.get("summaries_created", 0) >= 0
        
        # Analyze performance scaling
        results = benchmark.results
        print("Summary Memory Strategy Performance:")
        for length in conversation_lengths:
            key = f"summary_strategy_{length}_messages"
            time_taken = results[key]["execution_time"]
            print(f"  {length} messages: {time_taken:.4f}s")
    
    def test_entity_memory_strategy_performance(self):
        """Test entity memory strategy performance with different conversation lengths."""
        benchmark = PerformanceBenchmark()
        
        conversation_lengths = [10, 50, 100, 200, 500]
        
        # Create messages with entity-rich content
        def create_entity_rich_messages(count: int):
            messages = []
            names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
            topics = ["Python", "JavaScript", "AI", "Machine Learning", "Data Science"]
            
            for i in range(count):
                if i % 2 == 0:
                    name = names[i % len(names)]
                    topic = topics[i % len(topics)]
                    content = f"My name is {name} and I'm interested in {topic} programming"
                    messages.append(HumanMessage(content=content))
                else:
                    topic = topics[i % len(topics)]
                    content = f"Great! {topic} is a fascinating field with many applications"
                    messages.append(AIMessage(content=content))
            return messages
        
        for length in conversation_lengths:
            # Create memory manager with entity strategy
            config = MemoryConfig(
                strategy=MemoryStrategyType.ENTITY,
                max_buffer_size=20,
                entity_extraction_enabled=True
            )
            memory_manager = MemoryManager(session_id=123, config=config)
            
            # Create entity-rich test messages
            messages = create_entity_rich_messages(length)
            
            # Benchmark adding messages with entity extraction
            def add_messages_with_entities():
                for message in messages:
                    memory_manager.add_message(message)
                return memory_manager.get_conversation_context()
            
            context = benchmark.time_operation(
                f"entity_strategy_{length}_messages",
                add_messages_with_entities
            )
            
            # Verify entity strategy worked
            stats = memory_manager.get_memory_stats()
            assert stats["strategy"] == "entity"
            assert stats["total_messages"] == length
            
            # Should have extracted entities
            entities = memory_manager.get_entities()
            assert len(entities["names"]) > 0
            assert len(entities["topics"]) > 0
        
        # Analyze performance scaling
        results = benchmark.results
        print("Entity Memory Strategy Performance:")
        for length in conversation_lengths:
            key = f"entity_strategy_{length}_messages"
            time_taken = results[key]["execution_time"]
            print(f"  {length} messages: {time_taken:.4f}s")
    
    def test_memory_strategy_comparison(self):
        """Compare performance between different memory strategies."""
        benchmark = PerformanceBenchmark()
        
        # Test with moderate conversation length
        message_count = 100
        messages = self.create_test_messages(message_count)
        
        strategies = [
            (MemoryStrategyType.BUFFER, "buffer"),
            (MemoryStrategyType.SUMMARY, "summary"),
            (MemoryStrategyType.ENTITY, "entity")
        ]
        
        for strategy_type, strategy_name in strategies:
            config = MemoryConfig(
                strategy=strategy_type,
                max_buffer_size=20,
                max_tokens_before_summary=1000,
                entity_extraction_enabled=True
            )
            memory_manager = MemoryManager(session_id=123, config=config)
            
            def test_strategy():
                for message in messages:
                    memory_manager.add_message(message)
                context = memory_manager.get_conversation_context()
                stats = memory_manager.get_memory_stats()
                return {"context": context, "stats": stats}
            
            result = benchmark.time_operation(
                f"strategy_comparison_{strategy_name}",
                test_strategy
            )
            
            # Verify strategy worked
            assert result["stats"]["strategy"] == strategy_name
            assert result["stats"]["total_messages"] == message_count
        
        # Compare strategies
        print("Memory Strategy Performance Comparison (100 messages):")
        for _, strategy_name in strategies:
            key = f"strategy_comparison_{strategy_name}"
            time_taken = benchmark.results[key]["execution_time"]
            print(f"  {strategy_name.capitalize()}: {time_taken:.4f}s")


class TestTokenUsageAndOptimization:
    """Test token usage reduction and response time improvements."""
    
    def test_context_optimization_token_reduction(self):
        """Test token usage reduction through context optimization."""
        benchmark = PerformanceBenchmark()
        
        # Create context optimizer
        config = ContextConfig(
            max_tokens=1000,
            optimization_strategy=OptimizationStrategy.HYBRID,
            messages_to_keep_after_summary=10
        )
        optimizer = ContextOptimizer(config=config, session_id=123)
        
        # Create messages that will exceed token limit
        long_messages = []
        for i in range(30):
            content = f"This is a long message {i} with substantial content that will contribute to token usage " * 10
            if i % 2 == 0:
                long_messages.append(HumanMessage(content=content))
            else:
                long_messages.append(AIMessage(content=content))
        
        # Benchmark without optimization
        def calculate_tokens_without_optimization():
            return optimizer.calculate_token_usage(long_messages)
        
        original_tokens = benchmark.time_operation(
            "token_calculation_without_optimization",
            calculate_tokens_without_optimization
        )
        
        # Benchmark with optimization
        def optimize_and_calculate_tokens():
            optimized_messages = optimizer.optimize_context(long_messages)
            optimized_tokens = optimizer.calculate_token_usage(optimized_messages)
            return {
                "optimized_messages": optimized_messages,
                "optimized_tokens": optimized_tokens,
                "original_count": len(long_messages),
                "optimized_count": len(optimized_messages)
            }
        
        optimization_result = benchmark.time_operation(
            "token_optimization",
            optimize_and_calculate_tokens
        )
        
        # Calculate token savings
        tokens_saved = original_tokens - optimization_result["optimized_tokens"]
        reduction_percentage = (tokens_saved / original_tokens) * 100 if original_tokens > 0 else 0
        
        # Verify optimization worked
        assert optimization_result["optimized_tokens"] < original_tokens
        assert optimization_result["optimized_count"] <= optimization_result["original_count"]
        assert tokens_saved > 0
        
        print(f"Token Usage Optimization Results:")
        print(f"  Original tokens: {original_tokens}")
        print(f"  Optimized tokens: {optimization_result['optimized_tokens']}")
        print(f"  Tokens saved: {tokens_saved}")
        print(f"  Reduction: {reduction_percentage:.2f}%")
        print(f"  Messages: {optimization_result['original_count']} -> {optimization_result['optimized_count']}")
    
    def test_optimization_strategy_performance(self):
        """Test performance of different optimization strategies."""
        benchmark = PerformanceBenchmark()
        
        # Create test messages
        messages = []
        for i in range(50):
            content = f"Message {i} about Python programming and data science with relevant content"
            if i % 2 == 0:
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
        
        strategies = [
            OptimizationStrategy.RECENCY,
            OptimizationStrategy.RELEVANCE,
            OptimizationStrategy.HYBRID,
            OptimizationStrategy.SUMMARIZATION
        ]
        
        for strategy in strategies:
            config = ContextConfig(
                max_tokens=800,
                optimization_strategy=strategy,
                messages_to_keep_after_summary=15
            )
            optimizer = ContextOptimizer(config=config, session_id=123)
            
            def test_optimization_strategy():
                original_tokens = optimizer.calculate_token_usage(messages)
                optimized_messages = optimizer.optimize_context(messages)
                optimized_tokens = optimizer.calculate_token_usage(optimized_messages)
                
                return {
                    "original_tokens": original_tokens,
                    "optimized_tokens": optimized_tokens,
                    "tokens_saved": original_tokens - optimized_tokens,
                    "messages_kept": len(optimized_messages),
                    "optimization_stats": optimizer.get_optimization_stats()
                }
            
            result = benchmark.time_operation(
                f"optimization_strategy_{strategy.value}",
                test_optimization_strategy
            )
            
            # Verify optimization worked
            assert result["optimized_tokens"] <= result["original_tokens"]
            assert result["tokens_saved"] >= 0
        
        # Compare strategy performance
        print("Optimization Strategy Performance Comparison:")
        for strategy in strategies:
            key = f"optimization_strategy_{strategy.value}"
            result = benchmark.results[key]
            time_taken = result["execution_time"]
            optimization_result = result["result"]
            
            print(f"  {strategy.value.capitalize()}:")
            print(f"    Time: {time_taken:.4f}s")
            print(f"    Tokens saved: {optimization_result['tokens_saved']}")
            print(f"    Messages kept: {optimization_result['messages_kept']}")
    
    def test_summarization_performance_scaling(self):
        """Test summarization performance with different conversation lengths."""
        benchmark = PerformanceBenchmark()
        
        conversation_lengths = [20, 50, 100, 200, 500]
        
        for length in conversation_lengths:
            # Create messages for summarization
            messages = []
            for i in range(length):
                content = f"Conversation message {i} discussing various topics including programming, AI, and technology"
                if i % 2 == 0:
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))
            
            # Create optimizer with summarization strategy
            config = ContextConfig(
                max_tokens=500,  # Low limit to trigger summarization
                optimization_strategy=OptimizationStrategy.SUMMARIZATION,
                messages_to_keep_after_summary=10
            )
            optimizer = ContextOptimizer(config=config, session_id=123)
            
            def test_summarization():
                original_tokens = optimizer.calculate_token_usage(messages)
                summarized_messages = optimizer.apply_summarization(messages)
                summarized_tokens = optimizer.calculate_token_usage(summarized_messages)
                
                return {
                    "original_messages": len(messages),
                    "summarized_messages": len(summarized_messages),
                    "original_tokens": original_tokens,
                    "summarized_tokens": summarized_tokens,
                    "compression_ratio": len(summarized_messages) / len(messages) if messages else 1
                }
            
            result = benchmark.time_operation(
                f"summarization_{length}_messages",
                test_summarization
            )
            
            # Verify summarization worked
            assert result["summarized_messages"] <= result["original_messages"]
            assert result["summarized_tokens"] <= result["original_tokens"]
        
        # Analyze summarization scaling
        print("Summarization Performance Scaling:")
        for length in conversation_lengths:
            key = f"summarization_{length}_messages"
            result = benchmark.results[key]
            time_taken = result["execution_time"]
            summarization_result = result["result"]
            
            print(f"  {length} messages:")
            print(f"    Time: {time_taken:.4f}s")
            print(f"    Compression: {summarization_result['compression_ratio']:.2f}")
            print(f"    Token reduction: {summarization_result['original_tokens'] - summarization_result['summarized_tokens']}")
    
    def test_relevance_scoring_performance(self):
        """Test performance of relevance scoring with different message counts."""
        benchmark = PerformanceBenchmark()
        
        message_counts = [10, 50, 100, 200, 500]
        
        for count in message_counts:
            # Create messages with varying relevance
            messages = []
            keywords = ["python", "programming", "data", "science", "machine", "learning"]
            
            for i in range(count):
                # Make some messages more relevant than others
                if i % 3 == 0:
                    # High relevance message
                    keyword = keywords[i % len(keywords)]
                    content = f"I want to learn about {keyword} programming and how to use it effectively"
                else:
                    # Lower relevance message
                    content = f"This is message {i} with some general content"
                
                if i % 2 == 0:
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))
            
            # Create optimizer for relevance testing
            config = ContextConfig(
                max_tokens=1000,
                optimization_strategy=OptimizationStrategy.RELEVANCE,
                relevance_threshold=0.5
            )
            optimizer = ContextOptimizer(config=config, session_id=123)
            
            def test_relevance_scoring():
                analysis = optimizer.analyze_message_relevance(messages)
                optimized_messages = optimizer._apply_relevance_optimization(messages)
                
                return {
                    "total_messages": len(messages),
                    "optimized_messages": len(optimized_messages),
                    "relevance_analysis": analysis,
                    "above_threshold": analysis["relevance_stats"]["above_threshold"]
                }
            
            result = benchmark.time_operation(
                f"relevance_scoring_{count}_messages",
                test_relevance_scoring
            )
            
            # Verify relevance scoring worked
            assert result["relevance_analysis"]["total_messages"] == count
            assert result["above_threshold"] >= 0
        
        # Analyze relevance scoring performance
        print("Relevance Scoring Performance:")
        for count in message_counts:
            key = f"relevance_scoring_{count}_messages"
            result = benchmark.results[key]
            time_taken = result["execution_time"]
            scoring_result = result["result"]
            
            print(f"  {count} messages:")
            print(f"    Time: {time_taken:.4f}s")
            print(f"    Above threshold: {scoring_result['above_threshold']}")
            print(f"    Optimization ratio: {scoring_result['optimized_messages'] / scoring_result['total_messages']:.2f}")


class TestIntegratedPerformanceBenchmarks:
    """Test integrated performance benchmarks combining multiple optimizations."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_performance_with_optimizations(self, db_session):
        """Test end-to-end performance with all optimizations enabled."""
        benchmark = PerformanceBenchmark()
        
        # Create mock LangChain client with optimization features
        mock_langchain_client = Mock(spec=LangChainClient)
        mock_chat_session = Mock(spec=LangChainChatSession)
        
        # Mock optimization stats
        mock_chat_session.get_optimization_stats.return_value = {
            "optimizer": {
                "optimizations_performed": 5,
                "tokens_saved": 300,
                "relevance_calculations": 25
            },
            "middleware": {
                "auto_summarizations": 2,
                "middleware_invocations": 10
            }
        }
        
        mock_chat_session.send_message.return_value = "Optimized response"
        mock_langchain_client.get_or_create_session.return_value = mock_chat_session
        
        # Create test session
        session_service = SessionService(db_session)
        test_session = await session_service.create_session(SessionCreate(
            title="End-to-End Performance Test"
        ))
        
        # Add existing conversation history
        for i in range(20):
            await session_service.add_message(MessageCreate(
                session_id=test_session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Performance test message {i} with substantial content for optimization testing"
            ))
        
        # Create service with optimizations
        optimized_service = SessionChatService(db_session, mock_langchain_client)
        
        # Benchmark end-to-end conversation with optimizations
        async def optimized_conversation():
            responses = []
            test_messages = [
                "What is machine learning?",
                "How does neural network training work?",
                "Can you explain backpropagation?",
                "What about deep learning architectures?",
                "How do I implement a CNN?"
            ]
            
            for message in test_messages:
                response = await optimized_service.send_message(test_session.id, message)
                responses.append(response)
            
            return responses
        
        responses = await benchmark.time_async_operation(
            "end_to_end_optimized_conversation",
            optimized_conversation
        )
        
        # Verify all responses completed
        assert len(responses) == 5
        for response in responses:
            assert response.assistant_message.content == "Optimized response"
        
        # Verify optimization stats
        optimization_stats = mock_chat_session.get_optimization_stats()
        assert optimization_stats["optimizer"]["optimizations_performed"] > 0
        assert optimization_stats["optimizer"]["tokens_saved"] > 0
        
        # Check final message count
        final_messages = await session_service.get_session_messages(test_session.id)
        expected_count = 20 + (5 * 2)  # existing + new messages
        assert len(final_messages) == expected_count
        
        print(f"End-to-End Optimized Performance:")
        print(f"  Total time: {benchmark.results['end_to_end_optimized_conversation']['execution_time']:.4f}s")
        print(f"  Messages processed: 5")
        print(f"  Optimizations performed: {optimization_stats['optimizer']['optimizations_performed']}")
        print(f"  Tokens saved: {optimization_stats['optimizer']['tokens_saved']}")
    
    def test_memory_and_optimization_integration_performance(self):
        """Test integrated performance of memory management and context optimization."""
        benchmark = PerformanceBenchmark()
        
        # Create integrated system
        memory_config = MemoryConfig(
            strategy=MemoryStrategyType.SUMMARY,
            max_buffer_size=15,
            max_tokens_before_summary=800
        )
        
        context_config = ContextConfig(
            max_tokens=1000,
            optimization_strategy=OptimizationStrategy.HYBRID,
            messages_to_keep_after_summary=12
        )
        
        memory_manager = MemoryManager(session_id=123, config=memory_config)
        context_optimizer = ContextOptimizer(config=context_config, session_id=123)
        
        # Create large conversation
        messages = []
        for i in range(100):
            content = f"Integrated test message {i} discussing programming, AI, and optimization techniques"
            if i % 2 == 0:
                message = HumanMessage(content=content)
            else:
                message = AIMessage(content=content)
            messages.append(message)
        
        def integrated_processing():
            # Process through memory manager
            for message in messages:
                memory_manager.add_message(message)
            
            # Get context from memory
            memory_context = memory_manager.get_conversation_context()
            
            # Optimize context
            optimized_context = context_optimizer.optimize_context(memory_context)
            
            # Calculate final metrics
            original_tokens = context_optimizer.calculate_token_usage(messages)
            memory_tokens = context_optimizer.calculate_token_usage(memory_context)
            optimized_tokens = context_optimizer.calculate_token_usage(optimized_context)
            
            return {
                "original_messages": len(messages),
                "memory_messages": len(memory_context),
                "optimized_messages": len(optimized_context),
                "original_tokens": original_tokens,
                "memory_tokens": memory_tokens,
                "optimized_tokens": optimized_tokens,
                "memory_stats": memory_manager.get_memory_stats(),
                "optimization_stats": context_optimizer.get_optimization_stats()
            }
        
        result = benchmark.time_operation(
            "integrated_memory_optimization",
            integrated_processing
        )
        
        # Verify integration worked
        assert result["optimized_messages"] <= result["memory_messages"] <= result["original_messages"]
        assert result["optimized_tokens"] <= result["memory_tokens"] <= result["original_tokens"]
        
        # Calculate total savings
        total_token_savings = result["original_tokens"] - result["optimized_tokens"]
        total_message_reduction = result["original_messages"] - result["optimized_messages"]
        
        print(f"Integrated Memory and Optimization Performance:")
        print(f"  Processing time: {benchmark.results['integrated_memory_optimization']['execution_time']:.4f}s")
        print(f"  Message flow: {result['original_messages']} -> {result['memory_messages']} -> {result['optimized_messages']}")
        print(f"  Token flow: {result['original_tokens']} -> {result['memory_tokens']} -> {result['optimized_tokens']}")
        print(f"  Total token savings: {total_token_savings}")
        print(f"  Total message reduction: {total_message_reduction}")
        print(f"  Memory summaries: {result['memory_stats'].get('summaries_created', 0)}")
        print(f"  Optimizations: {result['optimization_stats']['optimizations_performed']}")


if __name__ == "__main__":
    # Run performance benchmarks when executed directly
    print("Running LangChain Performance Benchmarks...")
    
    # This would typically be run with pytest, but can be executed directly for quick benchmarking
    import sys
    sys.exit("Run with: pytest backend/tests/test_langchain_performance_benchmarks.py -v -s")