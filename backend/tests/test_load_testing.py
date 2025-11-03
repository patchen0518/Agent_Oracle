"""
Load testing for session management under concurrent usage.

Tests concurrent session creation, cleanup performance under high volumes,
session recovery under load, and system stability during peak usage.
"""

import pytest
import asyncio
import time
import os
import statistics
import random
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

from backend.services.session_chat_service import SessionChatService
from backend.services.session_service import SessionService
from backend.services.gemini_client import GeminiClient, ChatSession
from backend.models.session_models import SessionCreate, MessageCreate


class LoadTestMetrics:
    """Collect and analyze load testing metrics."""
    
    def __init__(self):
        self.start_time = time.time()
        self.response_times: List[float] = []
        self.error_count = 0
        self.success_count = 0
        self.concurrent_sessions = 0
        self.peak_memory_usage = 0.0
        self.cleanup_operations = 0
        self.recovery_operations = 0
        self.throughput_samples: List[Tuple[float, int]] = []  # (timestamp, messages_processed)
    
    def record_response(self, response_time: float, success: bool = True):
        """Record a response time and success/failure."""
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def record_throughput_sample(self, messages_processed: int):
        """Record throughput at current time."""
        self.throughput_samples.append((time.time(), messages_processed))
    
    def update_peak_memory(self, memory_usage: float):
        """Update peak memory usage."""
        self.peak_memory_usage = max(self.peak_memory_usage, memory_usage)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive load test summary."""
        total_time = time.time() - self.start_time
        total_requests = self.success_count + self.error_count
        
        if not self.response_times:
            return {"error": "No response times recorded"}
        
        # Calculate throughput
        if len(self.throughput_samples) > 1:
            first_sample = self.throughput_samples[0]
            last_sample = self.throughput_samples[-1]
            time_diff = last_sample[0] - first_sample[0]
            message_diff = last_sample[1] - first_sample[1]
            throughput = message_diff / time_diff if time_diff > 0 else 0
        else:
            throughput = total_requests / total_time if total_time > 0 else 0
        
        return {
            "duration_seconds": total_time,
            "total_requests": total_requests,
            "success_rate": (self.success_count / total_requests) * 100 if total_requests > 0 else 0,
            "error_rate": (self.error_count / total_requests) * 100 if total_requests > 0 else 0,
            "throughput_rps": throughput,
            "response_times": {
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "p95": self._percentile(self.response_times, 95),
                "p99": self._percentile(self.response_times, 99),
                "min": min(self.response_times),
                "max": max(self.response_times)
            },
            "peak_memory_mb": self.peak_memory_usage,
            "concurrent_sessions": self.concurrent_sessions,
            "cleanup_operations": self.cleanup_operations,
            "recovery_operations": self.recovery_operations
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


@pytest.fixture
def load_test_metrics():
    """Create load test metrics collector."""
    return LoadTestMetrics()


@pytest.fixture
def mock_gemini_client_load_test():
    """Create a mock Gemini client optimized for load testing."""
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
    
    # Mock realistic session statistics
    def mock_get_session_stats():
        return {
            "active_sessions": len(client.active_sessions),
            "total_sessions_created": client.total_sessions_created,
            "sessions_expired": client.sessions_expired,
            "cache_hit_ratio": client.cache_hits / (client.cache_hits + client.cache_misses) if (client.cache_hits + client.cache_misses) > 0 else 0,
            "memory_usage_mb": len(client.active_sessions) * 0.1,
            "last_cleanup": datetime.now(),
            "oldest_session_age_hours": random.uniform(0.1, 2.0)
        }
    
    client.get_session_stats.side_effect = mock_get_session_stats
    
    # Mock cleanup operations
    def mock_cleanup_expired_sessions():
        start_time = time.time()
        sessions_to_remove = []
        
        # Simulate finding expired sessions
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
            "memory_freed_mb": len(sessions_to_remove) * 0.1
        }
    
    client.cleanup_expired_sessions.side_effect = mock_cleanup_expired_sessions
    
    return client


@pytest.fixture
def mock_chat_session_load_test():
    """Create a mock chat session optimized for load testing."""
    chat_session = Mock(spec=ChatSession)
    
    def mock_send_message(message: str):
        # Simulate variable processing time
        processing_time = random.uniform(0.01, 0.05)  # 10-50ms
        time.sleep(processing_time)
        
        # Simulate occasional failures (1% failure rate)
        if random.random() < 0.01:
            raise Exception("Simulated API failure")
        
        return f"Response to: {message[:30]}..."
    
    chat_session.send_message.side_effect = mock_send_message
    return chat_session


class TestConcurrentSessionManagement:
    """Test concurrent session creation and management."""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test creating many sessions concurrently."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        concurrent_sessions = 20
        messages_per_session = 3
        
        async def create_and_use_session(session_index: int):
            """Create a session and send multiple messages."""
            try:
                # Create session
                start_time = time.time()
                session = await session_service.create_session(
                    SessionCreate(title=f"Concurrent Session {session_index}")
                )
                creation_time = time.time() - start_time
                load_test_metrics.record_response(creation_time, True)
                
                # Configure for persistent sessions
                with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                    mock_gemini_client_load_test.get_or_create_session.return_value = mock_chat_session_load_test
                    
                    # Send multiple messages
                    for msg_index in range(messages_per_session):
                        try:
                            start_time = time.time()
                            await session_chat_service.send_message(
                                session.id, 
                                f"Message {msg_index} from session {session_index}"
                            )
                            response_time = time.time() - start_time
                            load_test_metrics.record_response(response_time, True)
                            
                            # Simulate session caching
                            if session.id not in mock_gemini_client_load_test.active_sessions:
                                mock_gemini_client_load_test.active_sessions[session.id] = (
                                    mock_chat_session_load_test, datetime.now(), datetime.now()
                                )
                                mock_gemini_client_load_test.total_sessions_created += 1
                                mock_gemini_client_load_test.cache_misses += 1
                            else:
                                mock_gemini_client_load_test.cache_hits += 1
                            
                            # Update metrics
                            stats = mock_gemini_client_load_test.get_session_stats()
                            load_test_metrics.update_peak_memory(stats["memory_usage_mb"])
                            
                        except Exception as e:
                            response_time = time.time() - start_time
                            load_test_metrics.record_response(response_time, False)
                            print(f"Message failed in session {session_index}: {e}")
                
                return session.id
                
            except Exception as e:
                creation_time = time.time() - start_time
                load_test_metrics.record_response(creation_time, False)
                print(f"Session creation failed for {session_index}: {e}")
                return None
        
        # Run concurrent session creation and usage
        start_time = time.time()
        tasks = [create_and_use_session(i) for i in range(concurrent_sessions)]
        session_ids = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Record final metrics
        successful_sessions = len([sid for sid in session_ids if sid is not None and not isinstance(sid, Exception)])
        load_test_metrics.concurrent_sessions = successful_sessions
        load_test_metrics.record_throughput_sample(successful_sessions * messages_per_session)
        
        # Analyze results
        summary = load_test_metrics.get_summary()
        
        # Verify concurrent performance
        assert summary["success_rate"] > 95  # Should have high success rate
        assert summary["response_times"]["mean"] < 0.5  # Average response under 500ms
        assert summary["response_times"]["p95"] < 1.0   # 95th percentile under 1s
        assert successful_sessions >= concurrent_sessions * 0.9  # At least 90% sessions created
        
        print(f"\nConcurrent Session Creation Results:")
        print(f"Sessions created: {successful_sessions}/{concurrent_sessions}")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        print(f"Average response time: {summary['response_times']['mean']:.3f}s")
        print(f"95th percentile: {summary['response_times']['p95']:.3f}s")
        print(f"Peak memory usage: {summary['peak_memory_mb']:.1f}MB")
        print(f"Total time: {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_high_concurrency_message_sending(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test sending many messages concurrently to existing sessions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        # Pre-create sessions
        num_sessions = 10
        messages_per_session = 10
        sessions = []
        
        for i in range(num_sessions):
            session = await session_service.create_session(
                SessionCreate(title=f"High Concurrency Session {i}")
            )
            sessions.append(session)
            
            # Pre-populate session cache
            mock_gemini_client_load_test.active_sessions[session.id] = (
                mock_chat_session_load_test, datetime.now(), datetime.now()
            )
        
        async def send_messages_to_session(session, message_count: int):
            """Send multiple messages to a single session."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_load_test.get_or_create_session.return_value = mock_chat_session_load_test
                
                for i in range(message_count):
                    try:
                        start_time = time.time()
                        await session_chat_service.send_message(
                            session.id, 
                            f"High concurrency message {i}"
                        )
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, True)
                        
                        # Simulate cache hits (sessions already exist)
                        mock_gemini_client_load_test.cache_hits += 1
                        
                    except Exception as e:
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, False)
                        print(f"Message failed: {e}")
        
        # Run high concurrency message sending
        start_time = time.time()
        tasks = [send_messages_to_session(session, messages_per_session) for session in sessions]
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Record metrics
        total_messages = num_sessions * messages_per_session
        load_test_metrics.record_throughput_sample(total_messages)
        
        # Analyze results
        summary = load_test_metrics.get_summary()
        
        # Verify high concurrency performance
        assert summary["success_rate"] > 98  # Should have very high success rate
        assert summary["throughput_rps"] > 50  # Should handle at least 50 messages/second
        assert summary["response_times"]["mean"] < 0.2  # Should be fast with cached sessions
        
        print(f"\nHigh Concurrency Message Sending Results:")
        print(f"Total messages: {total_messages}")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        print(f"Throughput: {summary['throughput_rps']:.1f} messages/second")
        print(f"Average response time: {summary['response_times']['mean']:.3f}s")
        print(f"Cache hit ratio: {mock_gemini_client_load_test.cache_hits / (mock_gemini_client_load_test.cache_hits + mock_gemini_client_load_test.cache_misses):.2f}")
    
    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test performance with mixed workload of new and existing sessions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        # Pre-create some sessions (existing workload)
        existing_sessions = []
        for i in range(5):
            session = await session_service.create_session(
                SessionCreate(title=f"Existing Session {i}")
            )
            existing_sessions.append(session)
            
            # Add to cache
            mock_gemini_client_load_test.active_sessions[session.id] = (
                mock_chat_session_load_test, datetime.now(), datetime.now()
            )
        
        async def existing_session_workload():
            """Simulate workload on existing sessions."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_load_test.get_or_create_session.return_value = mock_chat_session_load_test
                
                for _ in range(20):  # Send 20 messages to existing sessions
                    session = random.choice(existing_sessions)
                    try:
                        start_time = time.time()
                        await session_chat_service.send_message(
                            session.id, 
                            f"Existing session message {random.randint(1, 1000)}"
                        )
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, True)
                        mock_gemini_client_load_test.cache_hits += 1
                        
                    except Exception as e:
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, False)
        
        async def new_session_workload():
            """Simulate workload creating new sessions."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_load_test.get_or_create_session.return_value = mock_chat_session_load_test
                
                for i in range(10):  # Create 10 new sessions
                    try:
                        # Create new session
                        session = await session_service.create_session(
                            SessionCreate(title=f"New Session {i}")
                        )
                        
                        # Send first message (cache miss)
                        start_time = time.time()
                        await session_chat_service.send_message(
                            session.id, 
                            f"First message in new session {i}"
                        )
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, True)
                        
                        # Add to cache
                        mock_gemini_client_load_test.active_sessions[session.id] = (
                            mock_chat_session_load_test, datetime.now(), datetime.now()
                        )
                        mock_gemini_client_load_test.total_sessions_created += 1
                        mock_gemini_client_load_test.cache_misses += 1
                        
                        # Send follow-up message (cache hit)
                        start_time = time.time()
                        await session_chat_service.send_message(
                            session.id, 
                            f"Follow-up message in session {i}"
                        )
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, True)
                        mock_gemini_client_load_test.cache_hits += 1
                        
                    except Exception as e:
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, False)
        
        # Run mixed workload concurrently
        start_time = time.time()
        await asyncio.gather(
            existing_session_workload(),
            new_session_workload()
        )
        total_time = time.time() - start_time
        
        # Analyze results
        summary = load_test_metrics.get_summary()
        cache_stats = mock_gemini_client_load_test.get_session_stats()
        
        # Verify mixed workload performance
        assert summary["success_rate"] > 95  # Should handle mixed workload well
        assert cache_stats["cache_hit_ratio"] > 0.6  # Should have good cache utilization
        assert summary["response_times"]["mean"] < 0.3  # Should be reasonably fast
        
        print(f"\nMixed Workload Performance Results:")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        print(f"Average response time: {summary['response_times']['mean']:.3f}s")
        print(f"Cache hit ratio: {cache_stats['cache_hit_ratio']:.2f}")
        print(f"Total sessions: {cache_stats['active_sessions']}")
        print(f"Total time: {total_time:.2f}s")


class TestCleanupPerformanceUnderLoad:
    """Test cleanup performance under high session volumes."""
    
    @pytest.mark.asyncio
    async def test_cleanup_with_high_session_volume(self, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test cleanup performance with large number of sessions."""
        # Simulate high session volume
        session_count = 200
        now = datetime.now()
        
        # Create sessions with varying ages
        for i in range(session_count):
            # Make some sessions expired (older than 1 hour)
            if i < session_count // 3:  # 1/3 are expired
                age_hours = random.uniform(1.5, 5.0)  # 1.5-5 hours old
            else:
                age_hours = random.uniform(0.1, 0.9)  # Recent sessions
            
            timestamp = now - timedelta(hours=age_hours)
            mock_gemini_client_load_test.active_sessions[i] = (
                mock_chat_session_load_test, timestamp, timestamp
            )
        
        # Perform cleanup under load
        cleanup_times = []
        for _ in range(5):  # Multiple cleanup operations
            start_time = time.time()
            cleanup_stats = mock_gemini_client_load_test.cleanup_expired_sessions()
            cleanup_time = time.time() - start_time
            cleanup_times.append(cleanup_time)
            
            load_test_metrics.cleanup_operations += 1
            load_test_metrics.record_response(cleanup_time, True)
        
        # Analyze cleanup performance
        avg_cleanup_time = statistics.mean(cleanup_times)
        max_cleanup_time = max(cleanup_times)
        sessions_remaining = len(mock_gemini_client_load_test.active_sessions)
        sessions_cleaned = session_count - sessions_remaining
        
        # Verify cleanup performance under load
        assert avg_cleanup_time < 0.1  # Should be fast even with many sessions
        assert max_cleanup_time < 0.2  # Maximum time should be reasonable
        assert sessions_cleaned > 0    # Should have cleaned some sessions
        assert sessions_remaining < session_count  # Should have reduced session count
        
        print(f"\nCleanup Performance Under Load:")
        print(f"Initial sessions: {session_count}")
        print(f"Sessions cleaned: {sessions_cleaned}")
        print(f"Sessions remaining: {sessions_remaining}")
        print(f"Average cleanup time: {avg_cleanup_time:.4f}s")
        print(f"Max cleanup time: {max_cleanup_time:.4f}s")
        print(f"Cleanup operations: {load_test_metrics.cleanup_operations}")
    
    @pytest.mark.asyncio
    async def test_cleanup_during_active_usage(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test cleanup performance while sessions are actively being used."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        # Pre-create sessions with mixed ages
        sessions = []
        now = datetime.now()
        
        for i in range(50):
            session = await session_service.create_session(
                SessionCreate(title=f"Active Usage Session {i}")
            )
            sessions.append(session)
            
            # Some sessions are old (will be cleaned), others are recent
            if i < 20:  # Old sessions
                timestamp = now - timedelta(hours=2)
            else:  # Recent sessions
                timestamp = now - timedelta(minutes=random.randint(1, 30))
            
            mock_gemini_client_load_test.active_sessions[session.id] = (
                mock_chat_session_load_test, timestamp, timestamp
            )
        
        async def active_usage_workload():
            """Simulate active session usage."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_load_test.get_or_create_session.return_value = mock_chat_session_load_test
                
                for _ in range(30):  # Send 30 messages during cleanup
                    session = random.choice(sessions[-30:])  # Use recent sessions
                    try:
                        start_time = time.time()
                        await session_chat_service.send_message(
                            session.id, 
                            f"Message during cleanup {random.randint(1, 1000)}"
                        )
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, True)
                        
                        # Update session timestamp (active usage)
                        if session.id in mock_gemini_client_load_test.active_sessions:
                            session_data = mock_gemini_client_load_test.active_sessions[session.id]
                            mock_gemini_client_load_test.active_sessions[session.id] = (
                                session_data[0], datetime.now(), session_data[2]
                            )
                        
                        await asyncio.sleep(0.01)  # Small delay between messages
                        
                    except Exception as e:
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, False)
        
        async def cleanup_workload():
            """Simulate periodic cleanup during active usage."""
            for _ in range(3):  # 3 cleanup operations
                await asyncio.sleep(0.1)  # Wait a bit between cleanups
                
                start_time = time.time()
                cleanup_stats = mock_gemini_client_load_test.cleanup_expired_sessions()
                cleanup_time = time.time() - start_time
                
                load_test_metrics.cleanup_operations += 1
                load_test_metrics.record_response(cleanup_time, True)
        
        # Run active usage and cleanup concurrently
        start_time = time.time()
        await asyncio.gather(
            active_usage_workload(),
            cleanup_workload()
        )
        total_time = time.time() - start_time
        
        # Analyze results
        summary = load_test_metrics.get_summary()
        
        # Verify that cleanup doesn't interfere with active usage
        assert summary["success_rate"] > 95  # Active usage should not be affected
        assert summary["response_times"]["mean"] < 0.3  # Response times should remain good
        assert load_test_metrics.cleanup_operations == 3  # All cleanups should complete
        
        print(f"\nCleanup During Active Usage Results:")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        print(f"Average response time: {summary['response_times']['mean']:.3f}s")
        print(f"Cleanup operations completed: {load_test_metrics.cleanup_operations}")
        print(f"Total test time: {total_time:.2f}s")


class TestSessionRecoveryUnderLoad:
    """Test session recovery performance under load conditions."""
    
    @pytest.mark.asyncio
    async def test_recovery_with_concurrent_requests(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test session recovery when multiple requests need recovery simultaneously."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        # Create sessions with conversation history
        sessions_with_history = []
        for i in range(10):
            session = await session_service.create_session(
                SessionCreate(title=f"Recovery Test Session {i}")
            )
            
            # Add conversation history
            for j in range(5):
                await session_service.add_message(MessageCreate(
                    session_id=session.id,
                    role="user" if j % 2 == 0 else "assistant",
                    content=f"History message {j} in session {i}"
                ))
            
            sessions_with_history.append(session)
        
        # Mock recovery process
        mock_gemini_client_load_test._create_fresh_session.return_value = mock_chat_session_load_test
        mock_chat_session_load_test.send_message.return_value = "Recovery response"
        
        async def trigger_recovery_for_session(session):
            """Trigger recovery for a specific session."""
            try:
                start_time = time.time()
                
                # Simulate cache miss requiring recovery
                recovered_session = await session_chat_service.recover_session_from_database(
                    session.id, "Test system instruction"
                )
                
                recovery_time = time.time() - start_time
                load_test_metrics.record_response(recovery_time, True)
                load_test_metrics.recovery_operations += 1
                
                # Simulate successful recovery
                mock_gemini_client_load_test.sessions_recovered += 1
                mock_gemini_client_load_test.active_sessions[session.id] = (
                    recovered_session, datetime.now(), datetime.now()
                )
                
                return recovered_session
                
            except Exception as e:
                recovery_time = time.time() - start_time
                load_test_metrics.record_response(recovery_time, False)
                print(f"Recovery failed for session {session.id}: {e}")
                return None
        
        # Trigger concurrent recovery operations
        start_time = time.time()
        recovery_tasks = [trigger_recovery_for_session(session) for session in sessions_with_history]
        recovery_results = await asyncio.gather(*recovery_tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze recovery performance
        successful_recoveries = len([r for r in recovery_results if r is not None and not isinstance(r, Exception)])
        summary = load_test_metrics.get_summary()
        
        # Verify concurrent recovery performance
        assert successful_recoveries >= len(sessions_with_history) * 0.9  # At least 90% should succeed
        assert summary["success_rate"] > 90  # High success rate
        assert summary["response_times"]["mean"] < 1.0  # Recovery should be reasonably fast
        assert load_test_metrics.recovery_operations >= successful_recoveries
        
        print(f"\nConcurrent Recovery Performance:")
        print(f"Sessions to recover: {len(sessions_with_history)}")
        print(f"Successful recoveries: {successful_recoveries}")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        print(f"Average recovery time: {summary['response_times']['mean']:.3f}s")
        print(f"Total time: {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_recovery_with_large_conversation_history(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test recovery performance with sessions having large conversation histories."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        # Create sessions with varying history sizes
        history_sizes = [10, 25, 50, 100]  # Different conversation lengths
        sessions_by_size = {}
        
        for size in history_sizes:
            session = await session_service.create_session(
                SessionCreate(title=f"Large History Session {size}")
            )
            
            # Add extensive conversation history
            for i in range(size):
                content = f"Message {i} with substantial content to test recovery performance with large histories"
                await session_service.add_message(MessageCreate(
                    session_id=session.id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=content
                ))
            
            sessions_by_size[size] = session
        
        # Mock recovery with realistic processing time based on history size
        def mock_recovery_send_message(message: str):
            # Simulate processing time proportional to history size
            base_time = 0.01
            history_factor = len(message.split()) * 0.0001  # Small factor per word
            time.sleep(base_time + history_factor)
            return "Recovery response"
        
        mock_gemini_client_load_test._create_fresh_session.return_value = mock_chat_session_load_test
        mock_chat_session_load_test.send_message.side_effect = mock_recovery_send_message
        
        # Test recovery for each history size
        recovery_times_by_size = {}
        
        for size, session in sessions_by_size.items():
            try:
                start_time = time.time()
                
                recovered_session = await session_chat_service.recover_session_from_database(
                    session.id, "Test system instruction"
                )
                
                recovery_time = time.time() - start_time
                recovery_times_by_size[size] = recovery_time
                
                load_test_metrics.record_response(recovery_time, True)
                load_test_metrics.recovery_operations += 1
                mock_gemini_client_load_test.sessions_recovered += 1
                
            except Exception as e:
                recovery_time = time.time() - start_time
                recovery_times_by_size[size] = recovery_time
                load_test_metrics.record_response(recovery_time, False)
                print(f"Recovery failed for session with {size} messages: {e}")
        
        # Analyze scaling of recovery time with history size
        if len(recovery_times_by_size) >= 2:
            smallest_size = min(history_sizes)
            largest_size = max(history_sizes)
            
            if smallest_size in recovery_times_by_size and largest_size in recovery_times_by_size:
                scaling_factor = recovery_times_by_size[largest_size] / recovery_times_by_size[smallest_size]
            else:
                scaling_factor = 1.0
        else:
            scaling_factor = 1.0
        
        # Verify recovery performance scales reasonably
        max_recovery_time = max(recovery_times_by_size.values()) if recovery_times_by_size else 0
        assert max_recovery_time < 2.0  # Even large histories should recover within 2 seconds
        assert scaling_factor < 10.0    # Scaling should be reasonable
        
        print(f"\nLarge History Recovery Performance:")
        for size, recovery_time in recovery_times_by_size.items():
            print(f"  {size} messages: {recovery_time:.3f}s")
        print(f"Scaling factor (largest/smallest): {scaling_factor:.2f}x")
        print(f"Max recovery time: {max_recovery_time:.3f}s")


class TestSystemStabilityUnderPeakUsage:
    """Test system stability and error rates during peak usage."""
    
    @pytest.mark.asyncio
    async def test_peak_usage_stability(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test system stability under peak usage conditions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        # Simulate peak usage parameters
        concurrent_users = 15
        messages_per_user = 8
        session_reuse_probability = 0.7  # 70% chance to reuse existing session
        
        # Pre-create some sessions for reuse
        reusable_sessions = []
        for i in range(concurrent_users // 2):
            session = await session_service.create_session(
                SessionCreate(title=f"Reusable Session {i}")
            )
            reusable_sessions.append(session)
            
            # Add to cache
            mock_gemini_client_load_test.active_sessions[session.id] = (
                mock_chat_session_load_test, datetime.now(), datetime.now()
            )
        
        async def simulate_user_behavior(user_id: int):
            """Simulate realistic user behavior during peak usage."""
            with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
                mock_gemini_client_load_test.get_or_create_session.return_value = mock_chat_session_load_test
                
                user_sessions = []
                
                for message_num in range(messages_per_user):
                    try:
                        # Decide whether to reuse session or create new one
                        if (random.random() < session_reuse_probability and 
                            (user_sessions or reusable_sessions)):
                            
                            # Reuse existing session
                            if user_sessions and random.random() < 0.8:
                                session = random.choice(user_sessions)
                            else:
                                session = random.choice(reusable_sessions)
                        else:
                            # Create new session
                            session = await session_service.create_session(
                                SessionCreate(title=f"User {user_id} Session {len(user_sessions)}")
                            )
                            user_sessions.append(session)
                            
                            # Add to cache
                            mock_gemini_client_load_test.active_sessions[session.id] = (
                                mock_chat_session_load_test, datetime.now(), datetime.now()
                            )
                            mock_gemini_client_load_test.total_sessions_created += 1
                            mock_gemini_client_load_test.cache_misses += 1
                        
                        # Send message
                        start_time = time.time()
                        await session_chat_service.send_message(
                            session.id, 
                            f"User {user_id} message {message_num}: {random.choice(['Hello', 'How are you?', 'Tell me about AI', 'What can you do?'])}"
                        )
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, True)
                        
                        # Update cache hit/miss
                        if session in user_sessions[:-1] or session in reusable_sessions:
                            mock_gemini_client_load_test.cache_hits += 1
                        
                        # Random delay between messages (realistic user behavior)
                        await asyncio.sleep(random.uniform(0.01, 0.05))
                        
                    except Exception as e:
                        response_time = time.time() - start_time
                        load_test_metrics.record_response(response_time, False)
                        print(f"User {user_id} message {message_num} failed: {e}")
        
        async def periodic_cleanup():
            """Simulate periodic cleanup during peak usage."""
            for _ in range(3):  # 3 cleanup cycles during test
                await asyncio.sleep(0.2)  # Wait between cleanups
                
                try:
                    cleanup_stats = mock_gemini_client_load_test.cleanup_expired_sessions()
                    load_test_metrics.cleanup_operations += 1
                except Exception as e:
                    print(f"Cleanup failed: {e}")
        
        # Run peak usage simulation
        start_time = time.time()
        
        # Create user behavior tasks
        user_tasks = [simulate_user_behavior(i) for i in range(concurrent_users)]
        
        # Run users and cleanup concurrently
        await asyncio.gather(
            *user_tasks,
            periodic_cleanup(),
            return_exceptions=True
        )
        
        total_time = time.time() - start_time
        
        # Record final metrics
        total_messages = concurrent_users * messages_per_user
        load_test_metrics.record_throughput_sample(total_messages)
        
        # Analyze system stability
        summary = load_test_metrics.get_summary()
        cache_stats = mock_gemini_client_load_test.get_session_stats()
        
        # Verify system stability under peak usage
        assert summary["success_rate"] > 95  # Should maintain high success rate
        assert summary["error_rate"] < 5     # Should keep error rate low
        assert summary["throughput_rps"] > 20  # Should maintain good throughput
        assert cache_stats["cache_hit_ratio"] > 0.5  # Should have reasonable cache utilization
        
        print(f"\nPeak Usage Stability Results:")
        print(f"Concurrent users: {concurrent_users}")
        print(f"Total messages: {total_messages}")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        print(f"Error rate: {summary['error_rate']:.1f}%")
        print(f"Throughput: {summary['throughput_rps']:.1f} messages/second")
        print(f"Average response time: {summary['response_times']['mean']:.3f}s")
        print(f"95th percentile: {summary['response_times']['p95']:.3f}s")
        print(f"Cache hit ratio: {cache_stats['cache_hit_ratio']:.2f}")
        print(f"Active sessions: {cache_stats['active_sessions']}")
        print(f"Cleanup operations: {load_test_metrics.cleanup_operations}")
        print(f"Total test time: {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_resilience(self, db_session, mock_gemini_client_load_test, mock_chat_session_load_test, load_test_metrics):
        """Test system resilience and recovery from various error conditions."""
        session_chat_service = SessionChatService(db_session, mock_gemini_client_load_test)
        session_service = SessionService(db_session)
        
        # Create test session
        session = await session_service.create_session(
            SessionCreate(title="Error Recovery Test")
        )
        
        # Test different error scenarios
        error_scenarios = [
            ("api_timeout", Exception("API timeout")),
            ("rate_limit", Exception("Rate limit exceeded")),
            ("network_error", Exception("Network connection failed")),
            ("server_error", Exception("Internal server error")),
            ("recovery_failure", Exception("Session recovery failed"))
        ]
        
        recovery_attempts = []
        
        with patch.dict(os.environ, {"USE_PERSISTENT_SESSIONS": "true", "GRADUAL_ROLLOUT_PERCENTAGE": "100"}):
            for error_type, error in error_scenarios:
                # Configure mocks to simulate error then recovery
                call_count = 0
                
                def mock_with_recovery(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise error  # First call fails
                    return mock_chat_session_load_test  # Second call succeeds
                
                mock_gemini_client_load_test.get_or_create_session.side_effect = mock_with_recovery
                mock_gemini_client_load_test.create_chat_session.return_value = mock_chat_session_load_test
                mock_chat_session_load_test.send_message.return_value = f"Recovered from {error_type}"
                
                # Test error recovery
                try:
                    start_time = time.time()
                    result = await session_chat_service.send_message(
                        session.id, 
                        f"Test message for {error_type}"
                    )
                    recovery_time = time.time() - start_time
                    
                    # Verify recovery was successful
                    assert "Recovered from" in result.assistant_message.content
                    recovery_attempts.append((error_type, recovery_time, True))
                    load_test_metrics.record_response(recovery_time, True)
                    
                except Exception as e:
                    recovery_time = time.time() - start_time
                    recovery_attempts.append((error_type, recovery_time, False))
                    load_test_metrics.record_response(recovery_time, False)
                    print(f"Failed to recover from {error_type}: {e}")
                
                # Reset mock for next test
                mock_gemini_client_load_test.get_or_create_session.side_effect = None
        
        # Analyze error recovery performance
        successful_recoveries = len([r for r in recovery_attempts if r[2]])
        avg_recovery_time = statistics.mean([r[1] for r in recovery_attempts])
        
        # Verify error resilience
        assert successful_recoveries >= len(error_scenarios) * 0.8  # At least 80% should recover
        assert avg_recovery_time < 1.0  # Recovery should be reasonably fast
        
        print(f"\nError Recovery and Resilience Results:")
        print(f"Error scenarios tested: {len(error_scenarios)}")
        print(f"Successful recoveries: {successful_recoveries}")
        print(f"Recovery success rate: {(successful_recoveries / len(error_scenarios)) * 100:.1f}%")
        print(f"Average recovery time: {avg_recovery_time:.3f}s")
        
        for error_type, recovery_time, success in recovery_attempts:
            status = "✓" if success else "✗"
            print(f"  {status} {error_type}: {recovery_time:.3f}s")