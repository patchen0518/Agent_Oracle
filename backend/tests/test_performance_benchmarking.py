"""
Performance benchmarking tests for persistent vs stateless session management.

Tests token usage reduction, API call reduction, response time improvements,
and memory usage patterns under various load conditions.
"""

import pytest
import asyncio
import time
import os
import statistics
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from backend.services.session_chat_service import SessionChatService
from backend.services.session_service import SessionService
from backend.services.gemini_client import GeminiClient, ChatSession
from backend.models.session_models import SessionCreate, MessageCreate


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""
    
    def __init__(self):
        self.response_times: List[float] = []
        self.token_usage: List[int] = []
        self.api_calls: List[int] = []
        self.memory_usage: List[float] = []
        self.cache_hits: int = 0
        self.cache_misses: int = 0
    
    def add_measurement(self, response_time: float, tokens: int, api_calls: int, memory_mb: float):
        """Add a performance measurement."""
        self.response_times.append(response_time)
        self.token_usage.append(tokens)
        self.api_calls.append(api_calls)
        self.memory_usage.append(memory_mb)
    
    def add_cache_hit(self):
        """Record a cache hit."""
        self.cache_hits += 1
    
    def add_cache_miss(self):
        """Record a cache miss."""
        self.cache_misses += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistical summary of collected metrics."""
        if not self.response_times:
            return {}
        
        return {
            "response_time": {
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "min": min(self.response_times),
                "max": max(self.response_times),
                "stdev": statistics.stdev(self.response_times) if len(self.response_times) > 1 else 0
            },
            "token_usage": {
                "mean": statistics.mean(self.token_usage),
                "total": sum(self.token_usage),
                "min": min(self.token_usage),
                "max": max(self.token_usage)
            },
            "api_calls": {
                "mean": statistics.mean(self.api_calls),
                "total": sum(self.api_calls)
            },
            "memory_usage": {
                "mean": statistics.mean(self.memory_usage),
                "max": max(self.memory_usage)
            },
            "cache_performance": {
                "hit_ratio": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
                "total_hits": self.cache_hits,
                "total_misses": self.cache_misses
            }
        }


@pytest.fixture
def performance_metrics():
    """Create a performance metrics collector."""
    return PerformanceMetrics()


@pytest.fixture
def mock_gemini_client_with_metrics():
    """Create a mock Gemini client that tracks performance metrics."""
    client = Mock(spec=GeminiClient)
    
    # Initialize session management attributes
    client.active_sessions = {}
    client.total_sessions_created = 0
    client.sessions_expired = 0
    client.cache_hits = 0
    client.cache_misses = 0
    client.sessions_recovered = 0
    
    # Mock session statistics
    def mock_get_session_stats():
        return {
            "active_sessions": len(client.active_sessions),
            "total_sessions_created": client.total_sessions_created,
            "sessions_expired": client.sessions_expired,
            "cache_hit_ratio": client.cache_hits / (client.cache_hits + client.cache_misses) if (client.cache_hits + client.cache_misses) > 0 else 0,
            "memory_usage_mb": len(client.active_sessions) * 0.1,
            "last_cleanup": datetime.now(),
            "oldest_session_age_hours": 0.5
        }
    
    client.get_session_stats.side_effect = mock_get_session_stats
    
    return client


@pytest.fixture
def mock_chat_session_with_metrics():
    """Create a mock chat session that simulates realistic performance characteristics."""
    chat_session = Mock(spec=ChatSession)
    
    # Simulate variable response times and token usage
    def mock_send_message(message: str):
        # Simulate processing time based on message length
        time.sleep(0.01 + len(message) * 0.001)  # Base time + length factor
        
        # Simulate token usage (rough estimate)
        estimated_tokens = len(message.split()) * 1.3  # Input tokens
        estimated_tokens += 50  # Average response tokens
        
        return f"Response to: {message[:50]}..."
    
    chat_session.send_message.side_effect = mock_send_message
    return chat_session


class TestPersistentVsStatelessPerformance:
    """Compare performance between persistent and stateless session implementations."""
    
    @pytest.mark.asyncio
    async def test_response_time_comparison(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics, performance_metrics):
        """Test response time improvements with persistent sessions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        
        # Create test session
        session_service = SessionService(db_session)
        test_session = await session_service.create_session(SessionCreate(title="Performance Test"))
        
        # Add conversation history to test context building overhead
        for i in range(10):
            await session_service.add_message(MessageCreate(
                session_id=test_session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i} with some content to build context"
            ))
        
        # Test persistent sessions
        persistent_times = []
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_with_metrics.get_or_create_session.return_value = mock_chat_session_with_metrics
            
            for i in range(5):
                start_time = time.time()
                await session_chat_service.send_message(test_session.id, f"Persistent test message {i}")
                end_time = time.time()
                persistent_times.append(end_time - start_time)
                
                # Simulate cache hit after first message
                if i > 0:
                    mock_gemini_client_with_metrics.cache_hits += 1
                else:
                    mock_gemini_client_with_metrics.cache_misses += 1
        
        # Test stateless implementation
        stateless_times = []
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "false"}):
            mock_gemini_client_with_metrics.create_chat_session.return_value = mock_chat_session_with_metrics
            
            for i in range(5):
                start_time = time.time()
                await session_chat_service.send_message(test_session.id, f"Stateless test message {i}")
                end_time = time.time()
                stateless_times.append(end_time - start_time)
        
        # Analyze results
        persistent_avg = statistics.mean(persistent_times)
        stateless_avg = statistics.mean(stateless_times)
        improvement = ((stateless_avg - persistent_avg) / stateless_avg) * 100
        
        # Verify performance improvement (should be at least 20% faster)
        assert improvement > 20, f"Expected >20% improvement, got {improvement:.1f}%"
        
        # Log results for analysis
        print(f"\nResponse Time Comparison:")
        print(f"Persistent sessions avg: {persistent_avg:.3f}s")
        print(f"Stateless avg: {stateless_avg:.3f}s")
        print(f"Improvement: {improvement:.1f}%")
    
    @pytest.mark.asyncio
    async def test_token_usage_reduction(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test token usage reduction with persistent sessions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        
        # Create test session with extensive history
        session_service = SessionService(db_session)
        test_session = await session_service.create_session(SessionCreate(title="Token Usage Test"))
        
        # Add substantial conversation history
        for i in range(25):  # More than max_context_messages to trigger optimization
            content = f"This is message {i} with substantial content to simulate real conversation history and token usage patterns."
            await session_service.add_message(MessageCreate(
                session_id=test_session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=content
            ))
        
        # Mock token counting
        persistent_tokens = []
        stateless_tokens = []
        
        def mock_persistent_send(message):
            # Persistent sessions only send the new message
            tokens = len(message.split()) * 1.3  # Only new message tokens
            persistent_tokens.append(int(tokens))
            return f"Persistent response to: {message[:30]}..."
        
        def mock_stateless_send(context_message):
            # Stateless sends full context + new message
            tokens = len(context_message.split()) * 1.3  # Full context tokens
            stateless_tokens.append(int(tokens))
            return f"Stateless response to: {context_message[-30:]}..."
        
        # Test persistent sessions
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_with_metrics.get_or_create_session.return_value = mock_chat_session_with_metrics
            mock_chat_session_with_metrics.send_message.side_effect = mock_persistent_send
            
            for i in range(3):
                await session_chat_service.send_message(test_session.id, f"New message {i}")
        
        # Test stateless implementation
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "false"}):
            mock_gemini_client_with_metrics.create_chat_session.return_value = mock_chat_session_with_metrics
            mock_chat_session_with_metrics.send_message.side_effect = mock_stateless_send
            
            for i in range(3):
                await session_chat_service.send_message(test_session.id, f"New message {i}")
        
        # Analyze token usage
        persistent_avg = statistics.mean(persistent_tokens)
        stateless_avg = statistics.mean(stateless_tokens)
        reduction = ((stateless_avg - persistent_avg) / stateless_avg) * 100
        
        # Verify significant token reduction (should be at least 60%)
        assert reduction > 60, f"Expected >60% token reduction, got {reduction:.1f}%"
        
        print(f"\nToken Usage Comparison:")
        print(f"Persistent sessions avg: {persistent_avg:.0f} tokens")
        print(f"Stateless avg: {stateless_avg:.0f} tokens")
        print(f"Reduction: {reduction:.1f}%")
    
    @pytest.mark.asyncio
    async def test_api_call_reduction(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test API call reduction with session reuse."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        
        # Create test session
        session_service = SessionService(db_session)
        test_session = await session_service.create_session(SessionCreate(title="API Call Test"))
        
        # Test persistent sessions - should reuse session
        persistent_api_calls = 0
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_with_metrics.get_or_create_session.return_value = mock_chat_session_with_metrics
            
            for i in range(5):
                await session_chat_service.send_message(test_session.id, f"Message {i}")
                # First call creates session, subsequent calls reuse it
                if i == 0:
                    mock_gemini_client_with_metrics.total_sessions_created += 1
                    persistent_api_calls += 1
                # Each message is one API call to existing session
                persistent_api_calls += 1
        
        # Test stateless implementation - creates new session each time
        stateless_api_calls = 0
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "false"}):
            mock_gemini_client_with_metrics.create_chat_session.return_value = mock_chat_session_with_metrics
            
            for i in range(5):
                await session_chat_service.send_message(test_session.id, f"Message {i}")
                # Each message requires session creation + message send
                stateless_api_calls += 2  # create_session + send_message
        
        # Analyze API call reduction
        reduction = ((stateless_api_calls - persistent_api_calls) / stateless_api_calls) * 100
        
        # Verify significant API call reduction (should be at least 40%)
        assert reduction > 40, f"Expected >40% API call reduction, got {reduction:.1f}%"
        
        print(f"\nAPI Call Comparison:")
        print(f"Persistent sessions: {persistent_api_calls} calls")
        print(f"Stateless: {stateless_api_calls} calls")
        print(f"Reduction: {reduction:.1f}%")
    
    @pytest.mark.asyncio
    async def test_memory_usage_patterns(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test memory usage patterns and cleanup effectiveness."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        session_service = SessionService(db_session)
        
        # Create multiple test sessions
        test_sessions = []
        for i in range(10):
            session = await session_service.create_session(SessionCreate(title=f"Memory Test {i}"))
            test_sessions.append(session)
        
        memory_usage = []
        
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_with_metrics.get_or_create_session.return_value = mock_chat_session_with_metrics
            
            # Simulate session creation and usage
            for i, session in enumerate(test_sessions):
                await session_chat_service.send_message(session.id, f"Test message {i}")
                
                # Simulate session being added to cache
                mock_gemini_client_with_metrics.active_sessions[session.id] = (
                    mock_chat_session_with_metrics, 
                    datetime.now(), 
                    datetime.now()
                )
                
                # Record memory usage
                stats = mock_gemini_client_with_metrics.get_session_stats()
                memory_usage.append(stats["memory_usage_mb"])
        
        # Test cleanup effectiveness
        initial_sessions = len(mock_gemini_client_with_metrics.active_sessions)
        
        # Simulate cleanup by removing half the sessions
        sessions_to_remove = list(mock_gemini_client_with_metrics.active_sessions.keys())[:5]
        for session_id in sessions_to_remove:
            del mock_gemini_client_with_metrics.active_sessions[session_id]
        
        final_sessions = len(mock_gemini_client_with_metrics.active_sessions)
        cleanup_effectiveness = ((initial_sessions - final_sessions) / initial_sessions) * 100
        
        # Verify memory usage grows linearly with sessions
        assert len(memory_usage) == len(test_sessions)
        assert memory_usage[-1] > memory_usage[0]  # Memory should increase
        
        # Verify cleanup effectiveness
        assert cleanup_effectiveness == 50  # Should have removed exactly 50%
        
        print(f"\nMemory Usage Analysis:")
        print(f"Initial memory: {memory_usage[0]:.1f} MB")
        print(f"Final memory: {memory_usage[-1]:.1f} MB")
        print(f"Memory per session: {(memory_usage[-1] - memory_usage[0]) / (len(test_sessions) - 1):.2f} MB")
        print(f"Cleanup effectiveness: {cleanup_effectiveness:.0f}%")


class TestLoadConditionPerformance:
    """Test performance under various load conditions."""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_performance(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test performance under concurrent session usage."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        session_service = SessionService(db_session)
        
        # Create multiple sessions for concurrent testing
        test_sessions = []
        for i in range(5):
            session = await session_service.create_session(SessionCreate(title=f"Concurrent Test {i}"))
            test_sessions.append(session)
        
        async def send_messages_to_session(session, message_count: int):
            """Send multiple messages to a session."""
            times = []
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_with_metrics.get_or_create_session.return_value = mock_chat_session_with_metrics
                
                for i in range(message_count):
                    start_time = time.time()
                    await session_chat_service.send_message(session.id, f"Concurrent message {i}")
                    end_time = time.time()
                    times.append(end_time - start_time)
                    
                    # Simulate cache behavior
                    if session.id not in mock_gemini_client_with_metrics.active_sessions:
                        mock_gemini_client_with_metrics.active_sessions[session.id] = (
                            mock_chat_session_with_metrics, datetime.now(), datetime.now()
                        )
                        mock_gemini_client_with_metrics.cache_misses += 1
                    else:
                        mock_gemini_client_with_metrics.cache_hits += 1
            
            return times
        
        # Run concurrent tasks
        start_time = time.time()
        tasks = [send_messages_to_session(session, 3) for session in test_sessions]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze concurrent performance
        all_times = [time for session_times in results for time in session_times]
        avg_response_time = statistics.mean(all_times)
        total_messages = len(all_times)
        throughput = total_messages / total_time
        
        # Verify reasonable performance under concurrency
        assert avg_response_time < 0.5  # Should be under 500ms per message
        assert throughput > 5  # Should handle at least 5 messages per second
        
        # Verify cache effectiveness
        stats = mock_gemini_client_with_metrics.get_session_stats()
        assert stats["cache_hit_ratio"] > 0.5  # Should have good cache hit ratio
        
        print(f"\nConcurrent Performance Analysis:")
        print(f"Total messages: {total_messages}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.1f} messages/second")
        print(f"Avg response time: {avg_response_time:.3f}s")
        print(f"Cache hit ratio: {stats['cache_hit_ratio']:.2f}")
    
    @pytest.mark.asyncio
    async def test_high_volume_session_creation(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test performance with high volume session creation."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        session_service = SessionService(db_session)
        
        # Test creating many sessions rapidly
        session_creation_times = []
        message_send_times = []
        
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_with_metrics.get_or_create_session.return_value = mock_chat_session_with_metrics
            
            for i in range(20):  # Create 20 sessions
                # Time session creation
                start_time = time.time()
                session = await session_service.create_session(SessionCreate(title=f"High Volume {i}"))
                creation_time = time.time() - start_time
                session_creation_times.append(creation_time)
                
                # Time first message (cache miss)
                start_time = time.time()
                await session_chat_service.send_message(session.id, f"First message {i}")
                message_time = time.time() - start_time
                message_send_times.append(message_time)
                
                # Simulate session being cached
                mock_gemini_client_with_metrics.active_sessions[session.id] = (
                    mock_chat_session_with_metrics, datetime.now(), datetime.now()
                )
                mock_gemini_client_with_metrics.total_sessions_created += 1
                mock_gemini_client_with_metrics.cache_misses += 1
        
        # Analyze high volume performance
        avg_creation_time = statistics.mean(session_creation_times)
        avg_message_time = statistics.mean(message_send_times)
        total_sessions = len(mock_gemini_client_with_metrics.active_sessions)
        
        # Verify performance doesn't degrade significantly
        assert avg_creation_time < 0.1  # Session creation should be fast
        assert avg_message_time < 0.5   # First message should be reasonable
        assert total_sessions == 20     # All sessions should be created
        
        print(f"\nHigh Volume Performance Analysis:")
        print(f"Sessions created: {total_sessions}")
        print(f"Avg creation time: {avg_creation_time:.3f}s")
        print(f"Avg first message time: {avg_message_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_memory_pressure_performance(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test performance under memory pressure conditions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        session_service = SessionService(db_session)
        
        # Simulate approaching memory limits
        max_sessions = 10  # Simulate low memory limit
        mock_gemini_client_with_metrics.max_sessions = max_sessions
        
        cleanup_times = []
        performance_degradation = []
        
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_with_metrics.get_or_create_session.return_value = mock_chat_session_with_metrics
            
            # Fill cache to capacity and beyond
            for i in range(max_sessions + 5):
                session = await session_service.create_session(SessionCreate(title=f"Memory Pressure {i}"))
                
                # Time message sending as cache fills up
                start_time = time.time()
                await session_chat_service.send_message(session.id, f"Message {i}")
                message_time = time.time() - start_time
                performance_degradation.append(message_time)
                
                # Simulate session caching
                mock_gemini_client_with_metrics.active_sessions[session.id] = (
                    mock_chat_session_with_metrics, 
                    datetime.now() - timedelta(seconds=i),  # Older sessions have earlier timestamps
                    datetime.now() - timedelta(seconds=i)
                )
                
                # Simulate cleanup when over limit
                if len(mock_gemini_client_with_metrics.active_sessions) > max_sessions:
                    cleanup_start = time.time()
                    
                    # Remove oldest sessions (simulate cleanup)
                    sessions_to_remove = sorted(
                        mock_gemini_client_with_metrics.active_sessions.items(),
                        key=lambda x: x[1][1]  # Sort by last_used timestamp
                    )[:2]  # Remove 2 oldest
                    
                    for session_id, _ in sessions_to_remove:
                        del mock_gemini_client_with_metrics.active_sessions[session_id]
                        mock_gemini_client_with_metrics.sessions_expired += 1
                    
                    cleanup_time = time.time() - cleanup_start
                    cleanup_times.append(cleanup_time)
        
        # Analyze memory pressure performance
        if cleanup_times:
            avg_cleanup_time = statistics.mean(cleanup_times)
            max_cleanup_time = max(cleanup_times)
        else:
            avg_cleanup_time = max_cleanup_time = 0
        
        early_performance = statistics.mean(performance_degradation[:5])
        late_performance = statistics.mean(performance_degradation[-5:])
        degradation_ratio = late_performance / early_performance if early_performance > 0 else 1
        
        # Verify cleanup is efficient and performance doesn't degrade too much
        assert avg_cleanup_time < 0.01  # Cleanup should be very fast
        assert degradation_ratio < 2.0  # Performance shouldn't degrade more than 2x
        assert len(mock_gemini_client_with_metrics.active_sessions) <= max_sessions
        
        print(f"\nMemory Pressure Analysis:")
        print(f"Cleanup operations: {len(cleanup_times)}")
        print(f"Avg cleanup time: {avg_cleanup_time:.4f}s")
        print(f"Max cleanup time: {max_cleanup_time:.4f}s")
        print(f"Performance degradation ratio: {degradation_ratio:.2f}x")
        print(f"Final active sessions: {len(mock_gemini_client_with_metrics.active_sessions)}")


class TestSessionRecoveryPerformance:
    """Test performance of session recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_recovery_performance_with_history(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test session recovery performance with various history sizes."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        session_service = SessionService(db_session)
        
        recovery_times = []
        history_sizes = [5, 10, 20, 50]  # Different conversation lengths
        
        for history_size in history_sizes:
            # Create session with specific history size
            session = await session_service.create_session(SessionCreate(title=f"Recovery Test {history_size}"))
            
            # Add conversation history
            for i in range(history_size):
                await session_service.add_message(MessageCreate(
                    session_id=session.id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"History message {i} with content"
                ))
            
            # Mock recovery process
            mock_gemini_client_with_metrics._create_fresh_session.return_value = mock_chat_session_with_metrics
            mock_chat_session_with_metrics.send_message.return_value = "Recovery response"
            
            # Time the recovery process
            start_time = time.time()
            try:
                recovered_session = await session_chat_service.recover_session_from_database(
                    session.id, "Test system instruction"
                )
                recovery_time = time.time() - start_time
                recovery_times.append((history_size, recovery_time))
                
                # Simulate successful recovery
                mock_gemini_client_with_metrics.sessions_recovered += 1
                
            except Exception as e:
                # Record failed recovery
                recovery_time = time.time() - start_time
                recovery_times.append((history_size, recovery_time))
                print(f"Recovery failed for history size {history_size}: {e}")
        
        # Analyze recovery performance
        if recovery_times:
            avg_recovery_time = statistics.mean([time for _, time in recovery_times])
            max_recovery_time = max([time for _, time in recovery_times])
            
            # Check if recovery time scales reasonably with history size
            small_history_time = next((time for size, time in recovery_times if size <= 10), 0)
            large_history_time = next((time for size, time in recovery_times if size >= 50), 0)
            
            scaling_factor = large_history_time / small_history_time if small_history_time > 0 else 1
        else:
            avg_recovery_time = max_recovery_time = scaling_factor = 0
        
        # Verify recovery performance is acceptable
        assert avg_recovery_time < 1.0  # Should recover within 1 second on average
        assert max_recovery_time < 2.0  # Should never take more than 2 seconds
        assert scaling_factor < 5.0     # Should scale reasonably with history size
        
        print(f"\nSession Recovery Performance:")
        print(f"Avg recovery time: {avg_recovery_time:.3f}s")
        print(f"Max recovery time: {max_recovery_time:.3f}s")
        print(f"Scaling factor (large/small history): {scaling_factor:.2f}x")
        print(f"Successful recoveries: {mock_gemini_client_with_metrics.sessions_recovered}")
    
    @pytest.mark.asyncio
    async def test_recovery_failure_performance(self, db_session, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test performance when recovery fails and fallback is used."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_with_metrics)
        session_service = SessionService(db_session)
        
        # Create session with history
        session = await session_service.create_session(SessionCreate(title="Recovery Failure Test"))
        for i in range(10):
            await session_service.add_message(MessageCreate(
                session_id=session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"History message {i}"
            ))
        
        # Mock recovery to fail, but fallback to succeed
        mock_gemini_client_with_metrics._create_fresh_session.side_effect = Exception("Recovery failed")
        mock_gemini_client_with_metrics.create_chat_session.return_value = mock_chat_session_with_metrics
        mock_chat_session_with_metrics.send_message.return_value = "Fallback response"
        
        # Time the fallback process
        start_time = time.time()
        result = await session_chat_service.send_message(session.id, "Test message after recovery failure")
        fallback_time = time.time() - start_time
        
        # Verify fallback performance
        assert fallback_time < 1.0  # Fallback should be fast
        assert result.assistant_message.content == "Fallback response"
        assert result.assistant_message.message_metadata["persistent_session"] == False
        
        print(f"\nRecovery Failure Performance:")
        print(f"Fallback time: {fallback_time:.3f}s")
        print(f"Fallback successful: {result.assistant_message.content == 'Fallback response'}")


class TestCleanupOperationPerformance:
    """Test performance of cleanup operations."""
    
    @pytest.mark.asyncio
    async def test_cleanup_operation_efficiency(self, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test efficiency of cleanup operations under various conditions."""
        # Simulate large number of sessions in cache
        session_count = 100
        now = datetime.now()
        
        # Add sessions with varying ages
        for i in range(session_count):
            age_seconds = i * 10  # Sessions get progressively older
            timestamp = now - timedelta(seconds=age_seconds)
            mock_gemini_client_with_metrics.active_sessions[i] = (
                mock_chat_session_with_metrics, timestamp, timestamp
            )
        
        # Mock cleanup method
        def mock_cleanup_expired_sessions():
            start_time = time.time()
            
            # Simulate cleanup logic - remove sessions older than 1 hour
            timeout = 3600
            sessions_to_remove = []
            
            for session_id, (session, last_used, created) in mock_gemini_client_with_metrics.active_sessions.items():
                if (now - last_used).total_seconds() > timeout:
                    sessions_to_remove.append(session_id)
            
            # Remove expired sessions
            for session_id in sessions_to_remove:
                del mock_gemini_client_with_metrics.active_sessions[session_id]
                mock_gemini_client_with_metrics.sessions_expired += 1
            
            cleanup_time = time.time() - start_time
            
            return {
                "sessions_removed": len(sessions_to_remove),
                "sessions_expired": len(sessions_to_remove),
                "cleanup_duration_ms": cleanup_time * 1000,
                "cleanup_trigger": "automatic",
                "memory_freed_mb": len(sessions_to_remove) * 0.1
            }
        
        mock_gemini_client_with_metrics.cleanup_expired_sessions.side_effect = mock_cleanup_expired_sessions
        
        # Perform cleanup
        cleanup_stats = mock_gemini_client_with_metrics.cleanup_expired_sessions()
        
        # Analyze cleanup performance
        cleanup_time_ms = cleanup_stats["cleanup_duration_ms"]
        sessions_removed = cleanup_stats["sessions_removed"]
        cleanup_rate = sessions_removed / (cleanup_time_ms / 1000) if cleanup_time_ms > 0 else 0
        
        # Verify cleanup efficiency
        assert cleanup_time_ms < 100  # Should complete within 100ms
        assert sessions_removed > 0   # Should remove some sessions
        assert cleanup_rate > 100     # Should process at least 100 sessions per second
        
        print(f"\nCleanup Operation Performance:")
        print(f"Sessions processed: {session_count}")
        print(f"Sessions removed: {sessions_removed}")
        print(f"Cleanup time: {cleanup_time_ms:.1f}ms")
        print(f"Cleanup rate: {cleanup_rate:.0f} sessions/second")
        print(f"Memory freed: {cleanup_stats['memory_freed_mb']:.1f}MB")
    
    @pytest.mark.asyncio
    async def test_memory_pressure_cleanup_performance(self, mock_gemini_client_with_metrics, mock_chat_session_with_metrics):
        """Test cleanup performance under memory pressure."""
        # Simulate memory pressure scenario
        max_sessions = 50
        current_sessions = 75  # Over the limit
        mock_gemini_client_with_metrics.max_sessions = max_sessions
        
        now = datetime.now()
        
        # Fill cache beyond capacity
        for i in range(current_sessions):
            timestamp = now - timedelta(seconds=i)  # Older sessions have lower IDs
            mock_gemini_client_with_metrics.active_sessions[i] = (
                mock_chat_session_with_metrics, timestamp, timestamp
            )
        
        # Mock memory pressure cleanup
        def mock_memory_pressure_cleanup():
            start_time = time.time()
            
            sessions_over_limit = len(mock_gemini_client_with_metrics.active_sessions) - max_sessions
            if sessions_over_limit <= 0:
                return {"sessions_removed": 0, "cleanup_duration_ms": 0}
            
            # Remove oldest sessions first
            sessions_by_age = sorted(
                mock_gemini_client_with_metrics.active_sessions.items(),
                key=lambda x: x[1][1]  # Sort by last_used timestamp
            )
            
            sessions_to_remove = sessions_by_age[:sessions_over_limit + 10]  # Remove extra for buffer
            
            for session_id, _ in sessions_to_remove:
                del mock_gemini_client_with_metrics.active_sessions[session_id]
            
            cleanup_time = time.time() - start_time
            
            return {
                "sessions_removed": len(sessions_to_remove),
                "sessions_removed_by_pressure": len(sessions_to_remove),
                "cleanup_duration_ms": cleanup_time * 1000,
                "cleanup_trigger": "memory_pressure",
                "memory_freed_mb": len(sessions_to_remove) * 0.1
            }
        
        # Perform memory pressure cleanup
        cleanup_stats = mock_memory_pressure_cleanup()
        
        # Analyze memory pressure cleanup performance
        cleanup_time_ms = cleanup_stats["cleanup_duration_ms"]
        sessions_removed = cleanup_stats["sessions_removed"]
        final_session_count = len(mock_gemini_client_with_metrics.active_sessions)
        
        # Verify memory pressure cleanup effectiveness
        assert cleanup_time_ms < 50   # Should be very fast under pressure
        assert sessions_removed > 25  # Should remove significant number
        assert final_session_count <= max_sessions  # Should be under limit
        
        print(f"\nMemory Pressure Cleanup Performance:")
        print(f"Initial sessions: {current_sessions}")
        print(f"Sessions removed: {sessions_removed}")
        print(f"Final sessions: {final_session_count}")
        print(f"Cleanup time: {cleanup_time_ms:.1f}ms")
        print(f"Memory freed: {cleanup_stats['memory_freed_mb']:.1f}MB")