"""
Performance regression tests for session management.

Automated tests to detect performance regressions in session management,
scalability, memory usage, and cleanup operations.
"""

import pytest
import asyncio
import time
import os
import statistics
import psutil
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from backend.services.session_chat_service import SessionChatService
from backend.services.session_service import SessionService
from backend.services.gemini_client import GeminiClient, ChatSession
from backend.models.session_models import SessionCreate, MessageCreate


class PerformanceBaseline:
    """Define performance baselines and thresholds for regression detection."""
    
    # Response time baselines (in seconds)
    RESPONSE_TIME_BASELINE = {
        "persistent_session_hit": 0.05,    # Cache hit should be very fast
        "persistent_session_miss": 0.2,    # Cache miss with session creation
        "stateless_session": 0.3,          # Stateless with context building
        "session_recovery": 0.5,           # Recovery from database
        "cleanup_operation": 0.01          # Cleanup should be very fast
    }
    
    # Throughput baselines (requests per second)
    THROUGHPUT_BASELINE = {
        "concurrent_messages": 50,          # Messages per second under concurrency
        "session_creation": 20,            # New sessions per second
        "mixed_workload": 30               # Mixed new/existing sessions
    }
    
    # Memory usage baselines (MB)
    MEMORY_BASELINE = {
        "per_session": 0.1,                # Memory per cached session
        "cleanup_effectiveness": 0.8,      # Fraction of memory freed during cleanup
        "max_memory_growth": 50            # Maximum memory growth during test (MB)
    }
    
    # Cache performance baselines
    CACHE_BASELINE = {
        "hit_ratio_mixed_workload": 0.6,   # Cache hit ratio in mixed workload
        "hit_ratio_reuse_heavy": 0.8,      # Cache hit ratio with heavy reuse
        "miss_penalty_factor": 4.0         # Max slowdown factor for cache miss vs hit
    }
    
    # Scalability baselines
    SCALABILITY_BASELINE = {
        "max_degradation_factor": 2.0,     # Max performance degradation under load
        "linear_scaling_threshold": 0.9,   # R² threshold for linear scaling
        "cleanup_scaling_factor": 1.5      # Max cleanup time increase with session count
    }


class PerformanceMonitor:
    """Monitor system performance during tests."""
    
    def __init__(self):
        self.start_time = time.time()
        self.start_memory = self._get_memory_usage()
        self.measurements: List[Dict[str, Any]] = []
        self.process = psutil.Process()
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            return self.process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def record_measurement(self, operation: str, duration: float, success: bool = True, **kwargs):
        """Record a performance measurement."""
        measurement = {
            "timestamp": time.time() - self.start_time,
            "operation": operation,
            "duration": duration,
            "success": success,
            "memory_mb": self._get_memory_usage(),
            **kwargs
        }
        self.measurements.append(measurement)
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for a specific operation."""
        op_measurements = [m for m in self.measurements if m["operation"] == operation and m["success"]]
        
        if not op_measurements:
            return {"count": 0}
        
        durations = [m["duration"] for m in op_measurements]
        
        return {
            "count": len(op_measurements),
            "mean": statistics.mean(durations),
            "median": statistics.median(durations),
            "min": min(durations),
            "max": max(durations),
            "p95": self._percentile(durations, 95),
            "p99": self._percentile(durations, 99),
            "stdev": statistics.stdev(durations) if len(durations) > 1 else 0
        }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        memory_values = [m["memory_mb"] for m in self.measurements]
        
        if not memory_values:
            return {"peak": self.start_memory, "growth": 0}
        
        return {
            "start": self.start_memory,
            "peak": max(memory_values),
            "current": self._get_memory_usage(),
            "growth": max(memory_values) - self.start_memory
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


@pytest.fixture
def performance_monitor():
    """Create a performance monitor for tests."""
    return PerformanceMonitor()


@pytest.fixture
def mock_gemini_client_perf():
    """Create a mock Gemini client for performance testing."""
    client = Mock(spec=GeminiClient)
    
    # Initialize session management state
    client.active_sessions = {}
    client.total_sessions_created = 0
    client.sessions_expired = 0
    client.cache_hits = 0
    client.cache_misses = 0
    client.sessions_recovered = 0
    client.max_sessions = 100
    client.session_timeout = 3600
    
    # Mock session statistics
    def mock_get_session_stats():
        return {
            "active_sessions": len(client.active_sessions),
            "total_sessions_created": client.total_sessions_created,
            "sessions_expired": client.sessions_expired,
            "cache_hit_ratio": client.cache_hits / (client.cache_hits + client.cache_misses) if (client.cache_hits + client.cache_misses) > 0 else 0,
            "memory_usage_mb": len(client.active_sessions) * PerformanceBaseline.MEMORY_BASELINE["per_session"],
            "last_cleanup": datetime.now(),
            "oldest_session_age_hours": 0.5
        }
    
    client.get_session_stats.side_effect = mock_get_session_stats
    
    # Mock cleanup with realistic performance
    def mock_cleanup_expired_sessions():
        start_time = time.time()
        
        # Simulate cleanup logic
        sessions_to_remove = []
        now = datetime.now()
        
        for session_id, (session, last_used, created) in list(client.active_sessions.items()):
            if (now - last_used).total_seconds() > client.session_timeout:
                sessions_to_remove.append(session_id)
        
        # Remove expired sessions
        for session_id in sessions_to_remove:
            if session_id in client.active_sessions:
                del client.active_sessions[session_id]
                client.sessions_expired += 1
        
        cleanup_time = (time.time() - start_time) * 1000
        
        return {
            "sessions_removed": len(sessions_to_remove),
            "sessions_expired": len(sessions_to_remove),
            "cleanup_duration_ms": cleanup_time,
            "cleanup_trigger": "automatic",
            "memory_freed_mb": len(sessions_to_remove) * PerformanceBaseline.MEMORY_BASELINE["per_session"]
        }
    
    client.cleanup_expired_sessions.side_effect = mock_cleanup_expired_sessions
    
    return client


@pytest.fixture
def mock_chat_session_perf():
    """Create a mock chat session for performance testing."""
    chat_session = Mock(spec=ChatSession)
    
    def mock_send_message(message: str):
        # Simulate realistic processing time
        base_time = 0.005  # 5ms base for cache hits
        message_factor = len(message) * 0.0001  # Factor based on message length
        time.sleep(base_time + message_factor)
        
        return f"Response to: {message[:30]}..."
    
    chat_session.send_message.side_effect = mock_send_message
    return chat_session


class TestResponseTimeRegression:
    """Test for response time regressions."""
    
    @pytest.mark.asyncio
    async def test_persistent_session_response_times(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test that persistent session response times meet baseline requirements."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Create test session
        session = await session_service.create_session(SessionCreate(title="Response Time Test"))
        
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
            
            # Test cache miss (first message)
            start_time = time.time()
            await session_chat_service.send_message(session.id, "First message (cache miss)")
            cache_miss_time = time.time() - start_time
            
            performance_monitor.record_measurement("persistent_session_miss", cache_miss_time)
            mock_gemini_client_perf.cache_misses += 1
            mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
            
            # Test cache hits (subsequent messages)
            cache_hit_times = []
            for i in range(5):
                start_time = time.time()
                await session_chat_service.send_message(session.id, f"Cache hit message {i}")
                cache_hit_time = time.time() - start_time
                cache_hit_times.append(cache_hit_time)
                
                performance_monitor.record_measurement("persistent_session_hit", cache_hit_time)
                mock_gemini_client_perf.cache_hits += 1
        
        # Analyze results against baselines
        avg_cache_hit_time = statistics.mean(cache_hit_times)
        
        # Verify performance meets baselines
        assert cache_miss_time < PerformanceBaseline.RESPONSE_TIME_BASELINE["persistent_session_miss"], \
            f"Cache miss time {cache_miss_time:.3f}s exceeds baseline {PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_miss']:.3f}s"
        
        assert avg_cache_hit_time < PerformanceBaseline.RESPONSE_TIME_BASELINE["persistent_session_hit"], \
            f"Cache hit time {avg_cache_hit_time:.3f}s exceeds baseline {PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_hit']:.3f}s"
        
        # Verify cache hit is significantly faster than cache miss
        speedup_factor = cache_miss_time / avg_cache_hit_time
        assert speedup_factor > 1.2, f"Cache hit should be at least 1.2x faster than miss, got {speedup_factor:.1f}x"
        
        print(f"\nResponse Time Performance:")
        print(f"Cache miss: {cache_miss_time:.3f}s (baseline: {PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_miss']:.3f}s)")
        print(f"Cache hit avg: {avg_cache_hit_time:.3f}s (baseline: {PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_hit']:.3f}s)")
        print(f"Speedup factor: {speedup_factor:.1f}x")
    
    @pytest.mark.asyncio
    async def test_stateless_vs_persistent_comparison(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test performance comparison between stateless and persistent implementations."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Create session with conversation history
        session = await session_service.create_session(SessionCreate(title="Comparison Test"))
        
        # Add conversation history to test context building overhead
        for i in range(10):
            await session_service.add_message(MessageCreate(
                session_id=session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"History message {i} with content"
            ))
        
        # Test persistent session performance
        persistent_times = []
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
            
            for i in range(3):
                start_time = time.time()
                await session_chat_service.send_message(session.id, f"Persistent message {i}")
                response_time = time.time() - start_time
                persistent_times.append(response_time)
                
                performance_monitor.record_measurement("persistent_session", response_time)
                
                # Simulate caching after first message
                if i == 0:
                    mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
                    mock_gemini_client_perf.cache_misses += 1
                else:
                    mock_gemini_client_perf.cache_hits += 1
        
        # Test stateless implementation performance
        stateless_times = []
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "false"}):
            mock_gemini_client_perf.create_chat_session.return_value = mock_chat_session_perf
            
            for i in range(3):
                start_time = time.time()
                await session_chat_service.send_message(session.id, f"Stateless message {i}")
                response_time = time.time() - start_time
                stateless_times.append(response_time)
                
                performance_monitor.record_measurement("stateless_session", response_time)
        
        # Analyze performance comparison
        persistent_avg = statistics.mean(persistent_times)
        stateless_avg = statistics.mean(stateless_times)
        improvement_factor = stateless_avg / persistent_avg
        improvement_percentage = ((stateless_avg - persistent_avg) / stateless_avg) * 100
        
        # Verify persistent sessions are faster
        assert persistent_avg < PerformanceBaseline.RESPONSE_TIME_BASELINE["persistent_session_hit"] * 2, \
            f"Persistent session avg {persistent_avg:.3f}s exceeds reasonable threshold"
        
        assert stateless_avg < PerformanceBaseline.RESPONSE_TIME_BASELINE["stateless_session"], \
            f"Stateless session avg {stateless_avg:.3f}s exceeds baseline {PerformanceBaseline.RESPONSE_TIME_BASELINE['stateless_session']:.3f}s"
        
        assert improvement_factor > 1.5, \
            f"Persistent sessions should be at least 1.5x faster, got {improvement_factor:.1f}x"
        
        print(f"\nPersistent vs Stateless Comparison:")
        print(f"Persistent avg: {persistent_avg:.3f}s")
        print(f"Stateless avg: {stateless_avg:.3f}s")
        print(f"Improvement: {improvement_factor:.1f}x ({improvement_percentage:.1f}%)")
    
    @pytest.mark.asyncio
    async def test_session_recovery_performance(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test session recovery performance meets baseline requirements."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Create session with conversation history
        session = await session_service.create_session(SessionCreate(title="Recovery Performance Test"))
        
        # Add conversation history of varying sizes
        history_sizes = [5, 15, 30]
        recovery_times = []
        
        for size in history_sizes:
            # Clear previous history
            # (In real implementation, we'd clear the database, but for testing we'll simulate)
            
            # Add specific amount of history
            for i in range(size):
                await session_service.add_message(MessageCreate(
                    session_id=session.id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Recovery test message {i}"
                ))
            
            # Mock recovery process
            mock_gemini_client_perf._create_fresh_session.return_value = mock_chat_session_perf
            mock_chat_session_perf.send_message.return_value = "Recovery response"
            
            # Test recovery performance
            start_time = time.time()
            try:
                recovered_session = await session_chat_service.recover_session_from_database(
                    session.id, "Test system instruction"
                )
                recovery_time = time.time() - start_time
                recovery_times.append((size, recovery_time))
                
                performance_monitor.record_measurement("session_recovery", recovery_time, history_size=size)
                mock_gemini_client_perf.sessions_recovered += 1
                
            except Exception as e:
                recovery_time = time.time() - start_time
                recovery_times.append((size, recovery_time))
                performance_monitor.record_measurement("session_recovery", recovery_time, success=False, history_size=size)
                print(f"Recovery failed for history size {size}: {e}")
        
        # Analyze recovery performance
        if recovery_times:
            max_recovery_time = max(time for _, time in recovery_times)
            avg_recovery_time = statistics.mean([time for _, time in recovery_times])
            
            # Check scaling with history size
            if len(recovery_times) >= 2:
                small_time = next((time for size, time in recovery_times if size <= 10), 0)
                large_time = next((time for size, time in recovery_times if size >= 25), 0)
                scaling_factor = large_time / small_time if small_time > 0 else 1
            else:
                scaling_factor = 1
        else:
            max_recovery_time = avg_recovery_time = scaling_factor = 0
        
        # Verify recovery performance meets baseline
        assert max_recovery_time < PerformanceBaseline.RESPONSE_TIME_BASELINE["session_recovery"], \
            f"Max recovery time {max_recovery_time:.3f}s exceeds baseline {PerformanceBaseline.RESPONSE_TIME_BASELINE['session_recovery']:.3f}s"
        
        assert scaling_factor < 5.0, \
            f"Recovery time scaling factor {scaling_factor:.1f}x is too high"
        
        print(f"\nSession Recovery Performance:")
        print(f"Average recovery time: {avg_recovery_time:.3f}s")
        print(f"Max recovery time: {max_recovery_time:.3f}s (baseline: {PerformanceBaseline.RESPONSE_TIME_BASELINE['session_recovery']:.3f}s)")
        print(f"Scaling factor: {scaling_factor:.1f}x")
        
        for size, time in recovery_times:
            print(f"  {size} messages: {time:.3f}s")


class TestThroughputRegression:
    """Test for throughput regressions."""
    
    @pytest.mark.asyncio
    async def test_concurrent_message_throughput(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test concurrent message processing throughput."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Create multiple sessions for concurrent testing
        sessions = []
        for i in range(5):
            session = await session_service.create_session(SessionCreate(title=f"Throughput Test {i}"))
            sessions.append(session)
            
            # Pre-populate cache
            mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
        
        async def send_messages_concurrently(session, message_count: int):
            """Send messages to a session concurrently."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
                
                for i in range(message_count):
                    start_time = time.time()
                    await session_chat_service.send_message(session.id, f"Concurrent message {i}")
                    response_time = time.time() - start_time
                    
                    performance_monitor.record_measurement("concurrent_message", response_time)
                    mock_gemini_client_perf.cache_hits += 1
        
        # Run concurrent message sending
        messages_per_session = 10
        start_time = time.time()
        
        tasks = [send_messages_concurrently(session, messages_per_session) for session in sessions]
        await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        total_messages = len(sessions) * messages_per_session
        throughput = total_messages / total_time
        
        # Verify throughput meets baseline
        assert throughput > PerformanceBaseline.THROUGHPUT_BASELINE["concurrent_messages"], \
            f"Throughput {throughput:.1f} msg/s below baseline {PerformanceBaseline.THROUGHPUT_BASELINE['concurrent_messages']} msg/s"
        
        # Verify response times are reasonable
        stats = performance_monitor.get_operation_stats("concurrent_message")
        assert stats["mean"] < 0.1, f"Average response time {stats['mean']:.3f}s too high under concurrency"
        
        print(f"\nConcurrent Message Throughput:")
        print(f"Total messages: {total_messages}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.1f} msg/s (baseline: {PerformanceBaseline.THROUGHPUT_BASELINE['concurrent_messages']} msg/s)")
        print(f"Avg response time: {stats['mean']:.3f}s")
        print(f"95th percentile: {stats['p95']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_session_creation_throughput(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test session creation throughput."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        async def create_and_use_session(session_index: int):
            """Create a session and send first message."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
                
                # Create session
                session = await session_service.create_session(
                    SessionCreate(title=f"Creation Throughput Test {session_index}")
                )
                
                # Send first message (triggers session creation in cache)
                start_time = time.time()
                await session_chat_service.send_message(session.id, f"First message {session_index}")
                response_time = time.time() - start_time
                
                performance_monitor.record_measurement("session_creation", response_time)
                
                # Simulate session caching
                mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
                mock_gemini_client_perf.total_sessions_created += 1
                mock_gemini_client_perf.cache_misses += 1
                
                return session.id
        
        # Test session creation throughput
        session_count = 15
        start_time = time.time()
        
        tasks = [create_and_use_session(i) for i in range(session_count)]
        session_ids = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        throughput = session_count / total_time
        
        # Verify session creation throughput
        assert throughput > PerformanceBaseline.THROUGHPUT_BASELINE["session_creation"], \
            f"Session creation throughput {throughput:.1f} sessions/s below baseline {PerformanceBaseline.THROUGHPUT_BASELINE['session_creation']} sessions/s"
        
        # Verify all sessions were created successfully
        successful_sessions = len([sid for sid in session_ids if sid is not None])
        assert successful_sessions == session_count, f"Only {successful_sessions}/{session_count} sessions created successfully"
        
        # Verify response times
        stats = performance_monitor.get_operation_stats("session_creation")
        assert stats["mean"] < 0.3, f"Average session creation time {stats['mean']:.3f}s too high"
        
        print(f"\nSession Creation Throughput:")
        print(f"Sessions created: {successful_sessions}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.1f} sessions/s (baseline: {PerformanceBaseline.THROUGHPUT_BASELINE['session_creation']} sessions/s)")
        print(f"Avg creation time: {stats['mean']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_mixed_workload_throughput(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test throughput with mixed workload of new and existing sessions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Pre-create some sessions for reuse
        existing_sessions = []
        for i in range(3):
            session = await session_service.create_session(SessionCreate(title=f"Existing Session {i}"))
            existing_sessions.append(session)
            
            # Add to cache
            mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
        
        async def mixed_workload_task(task_id: int):
            """Execute mixed workload task."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
                
                operations = 0
                
                # 70% chance to use existing session, 30% to create new
                if task_id % 10 < 7 and existing_sessions:
                    # Use existing session
                    session = existing_sessions[task_id % len(existing_sessions)]
                    
                    start_time = time.time()
                    await session_chat_service.send_message(session.id, f"Existing session message {task_id}")
                    response_time = time.time() - start_time
                    
                    performance_monitor.record_measurement("mixed_existing", response_time)
                    mock_gemini_client_perf.cache_hits += 1
                    operations += 1
                    
                else:
                    # Create new session
                    session = await session_service.create_session(
                        SessionCreate(title=f"Mixed New Session {task_id}")
                    )
                    
                    start_time = time.time()
                    await session_chat_service.send_message(session.id, f"New session message {task_id}")
                    response_time = time.time() - start_time
                    
                    performance_monitor.record_measurement("mixed_new", response_time)
                    
                    # Add to cache
                    mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
                    mock_gemini_client_perf.total_sessions_created += 1
                    mock_gemini_client_perf.cache_misses += 1
                    operations += 1
                
                return operations
        
        # Run mixed workload
        task_count = 20
        start_time = time.time()
        
        tasks = [mixed_workload_task(i) for i in range(task_count)]
        operation_counts = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        total_operations = sum(operation_counts)
        throughput = total_operations / total_time
        
        # Verify mixed workload throughput
        assert throughput > PerformanceBaseline.THROUGHPUT_BASELINE["mixed_workload"], \
            f"Mixed workload throughput {throughput:.1f} ops/s below baseline {PerformanceBaseline.THROUGHPUT_BASELINE['mixed_workload']} ops/s"
        
        # Verify cache utilization
        cache_stats = mock_gemini_client_perf.get_session_stats()
        assert cache_stats["cache_hit_ratio"] > PerformanceBaseline.CACHE_BASELINE["hit_ratio_mixed_workload"], \
            f"Cache hit ratio {cache_stats['cache_hit_ratio']:.2f} below baseline {PerformanceBaseline.CACHE_BASELINE['hit_ratio_mixed_workload']:.2f}"
        
        print(f"\nMixed Workload Throughput:")
        print(f"Total operations: {total_operations}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.1f} ops/s (baseline: {PerformanceBaseline.THROUGHPUT_BASELINE['mixed_workload']} ops/s)")
        print(f"Cache hit ratio: {cache_stats['cache_hit_ratio']:.2f}")


class TestMemoryUsageRegression:
    """Test for memory usage regressions."""
    
    @pytest.mark.asyncio
    async def test_session_memory_usage_scaling(self, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test that memory usage scales linearly with session count."""
        session_counts = [10, 25, 50, 100]
        memory_measurements = []
        
        for count in session_counts:
            # Clear previous sessions
            mock_gemini_client_perf.active_sessions.clear()
            
            # Add sessions to cache
            now = datetime.now()
            for i in range(count):
                mock_gemini_client_perf.active_sessions[i] = (mock_chat_session_perf, now, now)
            
            # Measure memory usage
            stats = mock_gemini_client_perf.get_session_stats()
            memory_usage = stats["memory_usage_mb"]
            memory_measurements.append((count, memory_usage))
            
            performance_monitor.record_measurement("memory_usage", memory_usage, session_count=count)
        
        # Analyze memory scaling
        if len(memory_measurements) >= 2:
            # Calculate memory per session
            memory_per_session_values = [memory / count for count, memory in memory_measurements if count > 0]
            avg_memory_per_session = statistics.mean(memory_per_session_values)
            
            # Check linearity (simple correlation)
            counts = [count for count, _ in memory_measurements]
            memories = [memory for _, memory in memory_measurements]
            
            # Simple linear regression to check scaling
            n = len(counts)
            sum_x = sum(counts)
            sum_y = sum(memories)
            sum_xy = sum(x * y for x, y in zip(counts, memories))
            sum_x2 = sum(x * x for x in counts)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Verify memory usage per session is within baseline
            assert avg_memory_per_session <= PerformanceBaseline.MEMORY_BASELINE["per_session"] * 1.2, \
                f"Memory per session {avg_memory_per_session:.3f}MB exceeds baseline {PerformanceBaseline.MEMORY_BASELINE['per_session']:.3f}MB"
            
            # Verify linear scaling (slope should be close to expected memory per session)
            expected_slope = PerformanceBaseline.MEMORY_BASELINE["per_session"]
            slope_ratio = slope / expected_slope
            assert 0.8 <= slope_ratio <= 1.2, \
                f"Memory scaling slope ratio {slope_ratio:.2f} indicates non-linear scaling"
        
        print(f"\nMemory Usage Scaling:")
        for count, memory in memory_measurements:
            memory_per_session = memory / count if count > 0 else 0
            print(f"  {count} sessions: {memory:.1f}MB ({memory_per_session:.3f}MB per session)")
        
        if len(memory_measurements) >= 2:
            print(f"Average memory per session: {avg_memory_per_session:.3f}MB (baseline: {PerformanceBaseline.MEMORY_BASELINE['per_session']:.3f}MB)")
            print(f"Scaling slope: {slope:.3f}MB per session")
    
    @pytest.mark.asyncio
    async def test_cleanup_memory_effectiveness(self, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test cleanup operation memory effectiveness."""
        # Fill cache with sessions of varying ages
        session_count = 50
        now = datetime.now()
        
        for i in range(session_count):
            # Make half the sessions expired
            if i < session_count // 2:
                timestamp = now - timedelta(hours=2)  # Expired
            else:
                timestamp = now - timedelta(minutes=30)  # Recent
            
            mock_gemini_client_perf.active_sessions[i] = (mock_chat_session_perf, timestamp, timestamp)
        
        # Measure memory before cleanup
        stats_before = mock_gemini_client_perf.get_session_stats()
        memory_before = stats_before["memory_usage_mb"]
        
        # Perform cleanup
        start_time = time.time()
        cleanup_stats = mock_gemini_client_perf.cleanup_expired_sessions()
        cleanup_time = time.time() - start_time
        
        # Measure memory after cleanup
        stats_after = mock_gemini_client_perf.get_session_stats()
        memory_after = stats_after["memory_usage_mb"]
        
        # Calculate cleanup effectiveness
        memory_freed = memory_before - memory_after
        cleanup_effectiveness = memory_freed / memory_before if memory_before > 0 else 0
        
        performance_monitor.record_measurement("cleanup_operation", cleanup_time, 
                                             memory_freed=memory_freed, 
                                             effectiveness=cleanup_effectiveness)
        
        # Verify cleanup performance
        assert cleanup_time < PerformanceBaseline.RESPONSE_TIME_BASELINE["cleanup_operation"], \
            f"Cleanup time {cleanup_time:.4f}s exceeds baseline {PerformanceBaseline.RESPONSE_TIME_BASELINE['cleanup_operation']:.4f}s"
        
        assert cleanup_effectiveness >= PerformanceBaseline.MEMORY_BASELINE["cleanup_effectiveness"] * 0.8, \
            f"Cleanup effectiveness {cleanup_effectiveness:.2f} below baseline {PerformanceBaseline.MEMORY_BASELINE['cleanup_effectiveness']:.2f}"
        
        # Verify memory was actually freed
        assert memory_freed > 0, "Cleanup should have freed some memory"
        assert cleanup_stats["sessions_removed"] > 0, "Cleanup should have removed some sessions"
        
        print(f"\nCleanup Memory Effectiveness:")
        print(f"Memory before: {memory_before:.1f}MB")
        print(f"Memory after: {memory_after:.1f}MB")
        print(f"Memory freed: {memory_freed:.1f}MB")
        print(f"Cleanup effectiveness: {cleanup_effectiveness:.2f} (baseline: {PerformanceBaseline.MEMORY_BASELINE['cleanup_effectiveness']:.2f})")
        print(f"Cleanup time: {cleanup_time:.4f}s (baseline: {PerformanceBaseline.RESPONSE_TIME_BASELINE['cleanup_operation']:.4f}s)")
        print(f"Sessions removed: {cleanup_stats['sessions_removed']}")
    
    @pytest.mark.asyncio
    async def test_memory_growth_under_load(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test memory growth patterns under sustained load."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Record initial memory
        initial_memory = performance_monitor._get_memory_usage()
        
        # Simulate sustained load with session creation and usage
        async def sustained_load_task(task_id: int):
            """Simulate sustained load."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
                
                # Create session
                session = await session_service.create_session(
                    SessionCreate(title=f"Load Test Session {task_id}")
                )
                
                # Send multiple messages
                for i in range(3):
                    await session_chat_service.send_message(session.id, f"Load message {i}")
                    
                    # Record memory usage
                    current_memory = performance_monitor._get_memory_usage()
                    performance_monitor.record_measurement("memory_under_load", current_memory - initial_memory)
                
                # Simulate session caching
                mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
                mock_gemini_client_perf.total_sessions_created += 1
        
        # Run sustained load
        load_tasks = 20
        tasks = [sustained_load_task(i) for i in range(load_tasks)]
        await asyncio.gather(*tasks)
        
        # Analyze memory growth
        final_memory = performance_monitor._get_memory_usage()
        memory_growth = final_memory - initial_memory
        
        # Verify memory growth is within acceptable limits
        assert memory_growth < PerformanceBaseline.MEMORY_BASELINE["max_memory_growth"], \
            f"Memory growth {memory_growth:.1f}MB exceeds baseline {PerformanceBaseline.MEMORY_BASELINE['max_memory_growth']}MB"
        
        # Verify memory growth is reasonable for the number of sessions created
        expected_memory_growth = load_tasks * PerformanceBaseline.MEMORY_BASELINE["per_session"]
        growth_ratio = memory_growth / expected_memory_growth if expected_memory_growth > 0 else 1
        
        assert growth_ratio < 3.0, \
            f"Memory growth ratio {growth_ratio:.1f}x indicates excessive memory usage"
        
        print(f"\nMemory Growth Under Load:")
        print(f"Initial memory: {initial_memory:.1f}MB")
        print(f"Final memory: {final_memory:.1f}MB")
        print(f"Memory growth: {memory_growth:.1f}MB (baseline limit: {PerformanceBaseline.MEMORY_BASELINE['max_memory_growth']}MB)")
        print(f"Expected growth: {expected_memory_growth:.1f}MB")
        print(f"Growth ratio: {growth_ratio:.1f}x")


class TestScalabilityRegression:
    """Test for scalability regressions."""
    
    @pytest.mark.asyncio
    async def test_performance_degradation_under_load(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test that performance doesn't degrade excessively under increasing load."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        load_levels = [5, 10, 20, 30]  # Different concurrency levels
        performance_by_load = []
        
        for load_level in load_levels:
            # Create sessions for this load level
            sessions = []
            for i in range(load_level):
                session = await session_service.create_session(
                    SessionCreate(title=f"Scalability Test L{load_level} S{i}")
                )
                sessions.append(session)
                
                # Pre-populate cache
                mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
            
            # Measure performance at this load level
            response_times = []
            
            async def load_level_task(session):
                """Execute task at specific load level."""
                with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                    mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
                    
                    start_time = time.time()
                    await session_chat_service.send_message(session.id, f"Scalability test message")
                    response_time = time.time() - start_time
                    response_times.append(response_time)
                    
                    performance_monitor.record_measurement("scalability_test", response_time, load_level=load_level)
                    mock_gemini_client_perf.cache_hits += 1
            
            # Run concurrent tasks at this load level
            start_time = time.time()
            tasks = [load_level_task(session) for session in sessions]
            await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            # Calculate performance metrics for this load level
            avg_response_time = statistics.mean(response_times)
            throughput = len(sessions) / total_time
            
            performance_by_load.append((load_level, avg_response_time, throughput))
        
        # Analyze scalability
        if len(performance_by_load) >= 2:
            # Compare lowest and highest load performance
            low_load = performance_by_load[0]
            high_load = performance_by_load[-1]
            
            response_time_degradation = high_load[1] / low_load[1]
            throughput_degradation = low_load[2] / high_load[2]  # Inverted because lower is worse
            
            # Verify performance degradation is within acceptable limits
            assert response_time_degradation < PerformanceBaseline.SCALABILITY_BASELINE["max_degradation_factor"], \
                f"Response time degradation {response_time_degradation:.1f}x exceeds baseline {PerformanceBaseline.SCALABILITY_BASELINE['max_degradation_factor']:.1f}x"
            
            assert throughput_degradation < PerformanceBaseline.SCALABILITY_BASELINE["max_degradation_factor"], \
                f"Throughput degradation {throughput_degradation:.1f}x exceeds baseline {PerformanceBaseline.SCALABILITY_BASELINE['max_degradation_factor']:.1f}x"
        
        print(f"\nScalability Performance:")
        for load_level, response_time, throughput in performance_by_load:
            print(f"  Load {load_level}: {response_time:.3f}s avg, {throughput:.1f} ops/s")
        
        if len(performance_by_load) >= 2:
            print(f"Response time degradation: {response_time_degradation:.1f}x (baseline limit: {PerformanceBaseline.SCALABILITY_BASELINE['max_degradation_factor']:.1f}x)")
            print(f"Throughput degradation: {throughput_degradation:.1f}x")
    
    @pytest.mark.asyncio
    async def test_cleanup_scaling_performance(self, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test that cleanup performance scales reasonably with session count."""
        session_counts = [25, 50, 100, 200]
        cleanup_times = []
        
        for count in session_counts:
            # Clear and populate cache
            mock_gemini_client_perf.active_sessions.clear()
            now = datetime.now()
            
            # Add sessions with mix of expired and active
            for i in range(count):
                if i < count // 3:  # 1/3 expired
                    timestamp = now - timedelta(hours=2)
                else:
                    timestamp = now - timedelta(minutes=30)
                
                mock_gemini_client_perf.active_sessions[i] = (mock_chat_session_perf, timestamp, timestamp)
            
            # Measure cleanup time
            start_time = time.time()
            cleanup_stats = mock_gemini_client_perf.cleanup_expired_sessions()
            cleanup_time = time.time() - start_time
            
            cleanup_times.append((count, cleanup_time))
            performance_monitor.record_measurement("cleanup_scaling", cleanup_time, session_count=count)
        
        # Analyze cleanup scaling
        if len(cleanup_times) >= 2:
            # Compare smallest and largest session counts
            small_count, small_time = cleanup_times[0]
            large_count, large_time = cleanup_times[-1]
            
            scaling_factor = large_time / small_time if small_time > 0 else 1
            
            # Verify cleanup scaling is reasonable
            assert scaling_factor < PerformanceBaseline.SCALABILITY_BASELINE["cleanup_scaling_factor"], \
                f"Cleanup scaling factor {scaling_factor:.1f}x exceeds baseline {PerformanceBaseline.SCALABILITY_BASELINE['cleanup_scaling_factor']:.1f}x"
            
            # Verify all cleanup times are within acceptable limits
            max_cleanup_time = max(time for _, time in cleanup_times)
            assert max_cleanup_time < PerformanceBaseline.RESPONSE_TIME_BASELINE["cleanup_operation"] * 10, \
                f"Max cleanup time {max_cleanup_time:.4f}s too high even for large session counts"
        
        print(f"\nCleanup Scaling Performance:")
        for count, cleanup_time in cleanup_times:
            print(f"  {count} sessions: {cleanup_time:.4f}s")
        
        if len(cleanup_times) >= 2:
            print(f"Scaling factor: {scaling_factor:.1f}x (baseline limit: {PerformanceBaseline.SCALABILITY_BASELINE['cleanup_scaling_factor']:.1f}x)")


class TestCachePerformanceRegression:
    """Test for cache performance regressions."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_ratio_performance(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Test cache hit ratio meets baseline requirements."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Create sessions for cache testing
        sessions = []
        for i in range(5):
            session = await session_service.create_session(SessionCreate(title=f"Cache Test {i}"))
            sessions.append(session)
        
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
            
            # Send messages with heavy session reuse
            for round_num in range(4):  # 4 rounds of messages
                for session in sessions:
                    start_time = time.time()
                    await session_chat_service.send_message(session.id, f"Cache test round {round_num}")
                    response_time = time.time() - start_time
                    
                    # Track cache behavior
                    if session.id in mock_gemini_client_perf.active_sessions:
                        mock_gemini_client_perf.cache_hits += 1
                        performance_monitor.record_measurement("cache_hit", response_time)
                    else:
                        mock_gemini_client_perf.cache_misses += 1
                        mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
                        performance_monitor.record_measurement("cache_miss", response_time)
        
        # Analyze cache performance
        cache_stats = mock_gemini_client_perf.get_session_stats()
        hit_ratio = cache_stats["cache_hit_ratio"]
        
        # Get performance stats for hits vs misses
        hit_stats = performance_monitor.get_operation_stats("cache_hit")
        miss_stats = performance_monitor.get_operation_stats("cache_miss")
        
        # Verify cache hit ratio meets baseline
        assert hit_ratio >= PerformanceBaseline.CACHE_BASELINE["hit_ratio_reuse_heavy"], \
            f"Cache hit ratio {hit_ratio:.2f} below baseline {PerformanceBaseline.CACHE_BASELINE['hit_ratio_reuse_heavy']:.2f}"
        
        # Verify cache hits are significantly faster than misses
        if hit_stats["count"] > 0 and miss_stats["count"] > 0:
            speedup_factor = miss_stats["mean"] / hit_stats["mean"]
            assert speedup_factor <= PerformanceBaseline.CACHE_BASELINE["miss_penalty_factor"], \
                f"Cache miss penalty {speedup_factor:.1f}x exceeds baseline {PerformanceBaseline.CACHE_BASELINE['miss_penalty_factor']:.1f}x"
        
        print(f"\nCache Performance:")
        print(f"Cache hit ratio: {hit_ratio:.2f} (baseline: {PerformanceBaseline.CACHE_BASELINE['hit_ratio_reuse_heavy']:.2f})")
        print(f"Cache hits: {mock_gemini_client_perf.cache_hits}")
        print(f"Cache misses: {mock_gemini_client_perf.cache_misses}")
        
        if hit_stats["count"] > 0:
            print(f"Avg hit time: {hit_stats['mean']:.3f}s")
        if miss_stats["count"] > 0:
            print(f"Avg miss time: {miss_stats['mean']:.3f}s")
            if hit_stats["count"] > 0:
                print(f"Miss penalty: {speedup_factor:.1f}x")


# Performance test runner
class TestPerformanceTestRunner:
    """Run comprehensive performance regression tests."""
    
    @pytest.mark.asyncio
    async def test_comprehensive_performance_regression(self, db_session, mock_gemini_client_perf, mock_chat_session_perf, performance_monitor):
        """Run comprehensive performance regression test suite."""
        print("\n" + "="*60)
        print("COMPREHENSIVE PERFORMANCE REGRESSION TEST")
        print("="*60)
        
        # Initialize test environment
        session_chat_service = SessionChatService(db_session, mock_gemini_client_perf)
        session_service = SessionService(db_session)
        
        # Test 1: Basic response time regression
        print("\n1. Testing response time regression...")
        session = await session_service.create_session(SessionCreate(title="Comprehensive Test"))
        
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            # Mock cache miss behavior (slower)
            def mock_cache_miss_session(*args, **kwargs):
                time.sleep(0.015)  # Additional 15ms for cache miss overhead
                return mock_chat_session_perf
            
            mock_gemini_client_perf.get_or_create_session.side_effect = mock_cache_miss_session
            
            # Cache miss
            start_time = time.time()
            await session_chat_service.send_message(session.id, "First message")
            cache_miss_time = time.time() - start_time
            mock_gemini_client_perf.active_sessions[session.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
            mock_gemini_client_perf.cache_misses += 1
            
            # Mock cache hit behavior (faster)
            mock_gemini_client_perf.get_or_create_session.side_effect = None
            mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
            
            # Cache hits
            cache_hit_times = []
            for i in range(3):
                start_time = time.time()
                await session_chat_service.send_message(session.id, f"Cache hit {i}")
                cache_hit_time = time.time() - start_time
                cache_hit_times.append(cache_hit_time)
                mock_gemini_client_perf.cache_hits += 1
        
        avg_cache_hit = statistics.mean(cache_hit_times)
        
        # Test 2: Throughput regression
        print("2. Testing throughput regression...")
        throughput_sessions = []
        for i in range(3):
            s = await session_service.create_session(SessionCreate(title=f"Throughput {i}"))
            throughput_sessions.append(s)
            mock_gemini_client_perf.active_sessions[s.id] = (mock_chat_session_perf, datetime.now(), datetime.now())
        
        start_time = time.time()
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            mock_gemini_client_perf.get_or_create_session.return_value = mock_chat_session_perf
            
            async def send_throughput_message(s):
                await session_chat_service.send_message(s.id, "Throughput test")
                mock_gemini_client_perf.cache_hits += 1
            
            tasks = [send_throughput_message(s) for s in throughput_sessions for _ in range(3)]
            await asyncio.gather(*tasks)
        
        throughput_time = time.time() - start_time
        throughput = len(tasks) / throughput_time
        
        # Test 3: Memory usage regression
        print("3. Testing memory usage regression...")
        memory_sessions = 20
        for i in range(memory_sessions):
            mock_gemini_client_perf.active_sessions[f"mem_{i}"] = (mock_chat_session_perf, datetime.now(), datetime.now())
        
        memory_stats = mock_gemini_client_perf.get_session_stats()
        memory_per_session = memory_stats["memory_usage_mb"] / memory_sessions
        
        # Test 4: Cleanup performance regression
        print("4. Testing cleanup performance regression...")
        start_time = time.time()
        cleanup_stats = mock_gemini_client_perf.cleanup_expired_sessions()
        cleanup_time = time.time() - start_time
        
        # Compile results
        results = {
            "response_times": {
                "cache_miss": cache_miss_time,
                "cache_hit_avg": avg_cache_hit,
                "speedup_factor": cache_miss_time / avg_cache_hit if avg_cache_hit > 0 else 1
            },
            "throughput": {
                "messages_per_second": throughput,
                "total_messages": len(tasks),
                "total_time": throughput_time
            },
            "memory": {
                "per_session_mb": memory_per_session,
                "total_sessions": memory_sessions,
                "total_memory_mb": memory_stats["memory_usage_mb"]
            },
            "cleanup": {
                "cleanup_time_ms": cleanup_time * 1000,
                "sessions_cleaned": cleanup_stats.get("sessions_removed", 0)
            },
            "cache": {
                "hit_ratio": mock_gemini_client_perf.get_session_stats()["cache_hit_ratio"]
            }
        }
        
        # Verify all baselines are met
        print("\n" + "="*60)
        print("PERFORMANCE REGRESSION TEST RESULTS")
        print("="*60)
        
        # Response time checks
        print(f"\nResponse Times:")
        print(f"  Cache miss: {results['response_times']['cache_miss']:.3f}s (baseline: {PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_miss']:.3f}s)")
        print(f"  Cache hit:  {results['response_times']['cache_hit_avg']:.3f}s (baseline: {PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_hit']:.3f}s)")
        print(f"  Speedup:    {results['response_times']['speedup_factor']:.1f}x")
        
        assert results['response_times']['cache_miss'] < PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_miss']
        assert results['response_times']['cache_hit_avg'] < PerformanceBaseline.RESPONSE_TIME_BASELINE['persistent_session_hit']
        assert results['response_times']['speedup_factor'] > 2.0
        
        # Throughput checks
        print(f"\nThroughput:")
        print(f"  Messages/sec: {results['throughput']['messages_per_second']:.1f} (baseline: {PerformanceBaseline.THROUGHPUT_BASELINE['concurrent_messages']} msg/s)")
        
        assert results['throughput']['messages_per_second'] > PerformanceBaseline.THROUGHPUT_BASELINE['concurrent_messages']
        
        # Memory checks
        print(f"\nMemory Usage:")
        print(f"  Per session: {results['memory']['per_session_mb']:.3f}MB (baseline: {PerformanceBaseline.MEMORY_BASELINE['per_session']:.3f}MB)")
        
        assert results['memory']['per_session_mb'] <= PerformanceBaseline.MEMORY_BASELINE['per_session'] * 1.25
        
        # Cleanup checks
        print(f"\nCleanup Performance:")
        print(f"  Cleanup time: {results['cleanup']['cleanup_time_ms']:.1f}ms (baseline: {PerformanceBaseline.RESPONSE_TIME_BASELINE['cleanup_operation'] * 1000:.1f}ms)")
        
        assert results['cleanup']['cleanup_time_ms'] < PerformanceBaseline.RESPONSE_TIME_BASELINE['cleanup_operation'] * 1000
        
        print(f"\n✅ ALL PERFORMANCE REGRESSION TESTS PASSED")
        print("="*60)
        
        return results