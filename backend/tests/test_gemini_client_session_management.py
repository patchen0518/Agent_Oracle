"""
Unit tests for Gemini Client session management functionality.

Tests the new persistent session management features including session caching,
cleanup mechanisms, and statistics tracking.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import os

from backend.services.gemini_client import GeminiClient, ChatSession


class TestGeminiClientSessionManagement:
    """Test session management functionality in GeminiClient."""
    
    @pytest.fixture
    def mock_genai_client(self):
        """Mock the underlying genai client."""
        with patch('backend.services.gemini_client.genai.Client') as mock_client:
            yield mock_client
    
    @pytest.fixture
    def gemini_client(self, mock_genai_client):
        """Create a GeminiClient instance for testing."""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            client = GeminiClient()
            return client
    
    @pytest.fixture
    def mock_chat_session(self):
        """Create a mock ChatSession."""
        mock_chat = Mock()
        mock_chat.send_message.return_value = "Test response"
        return ChatSession(mock_chat)
    
    def test_session_cache_initialization(self, gemini_client):
        """Test that session cache is properly initialized."""
        assert gemini_client.active_sessions == {}
        assert gemini_client.session_timeout == 3600
        assert gemini_client.max_sessions == 500
        assert gemini_client.cleanup_interval == 300
        assert gemini_client.total_sessions_created == 0
        assert gemini_client.cache_hits == 0
        assert gemini_client.cache_misses == 0
    
    def test_get_or_create_session_new_session(self, gemini_client):
        """Test creating a new session when none exists."""
        with patch.object(gemini_client, '_create_fresh_session') as mock_create:
            mock_session = Mock()
            mock_create.return_value = mock_session
            
            result = gemini_client.get_or_create_session(123, "test instruction")
            
            assert result == mock_session
            assert 123 in gemini_client.active_sessions
            assert gemini_client.total_sessions_created == 1
            assert gemini_client.cache_misses == 1
            mock_create.assert_called_once_with(123, "test instruction")
    
    def test_get_or_create_session_cache_hit(self, gemini_client, mock_chat_session):
        """Test retrieving an existing valid session from cache."""
        # Pre-populate cache with a session
        now = datetime.now()
        gemini_client.active_sessions[123] = (mock_chat_session, now, now)
        
        result = gemini_client.get_or_create_session(123, "test instruction")
        
        assert result == mock_chat_session
        assert gemini_client.cache_hits == 1
        # Verify last_used was updated
        _, last_used, _ = gemini_client.active_sessions[123]
        assert last_used > now
    
    def test_get_or_create_session_expired_session(self, gemini_client, mock_chat_session):
        """Test that expired sessions are removed and new ones created."""
        # Pre-populate cache with an expired session
        old_time = datetime.now() - timedelta(seconds=3700)  # Older than timeout
        gemini_client.active_sessions[123] = (mock_chat_session, old_time, old_time)
        
        with patch.object(gemini_client, '_create_fresh_session') as mock_create:
            new_session = Mock()
            mock_create.return_value = new_session
            
            result = gemini_client.get_or_create_session(123, "test instruction")
            
            assert result == new_session
            assert gemini_client.sessions_expired == 1
            assert gemini_client.cache_misses == 1
    
    def test_cleanup_expired_sessions(self, gemini_client, mock_chat_session):
        """Test cleanup of expired sessions."""
        now = datetime.now()
        old_time = now - timedelta(seconds=3700)  # Expired
        recent_time = now - timedelta(seconds=1800)  # Not expired
        
        # Add both expired and valid sessions
        gemini_client.active_sessions[123] = (mock_chat_session, old_time, old_time)
        gemini_client.active_sessions[456] = (mock_chat_session, recent_time, recent_time)
        
        stats = gemini_client.cleanup_expired_sessions()
        
        assert stats["sessions_removed"] == 1
        assert stats["sessions_expired"] == 1
        assert stats["cleanup_trigger"] == "automatic"
        assert 123 not in gemini_client.active_sessions
        assert 456 in gemini_client.active_sessions
    
    def test_memory_pressure_cleanup(self, gemini_client, mock_chat_session):
        """Test cleanup when approaching max session limit."""
        now = datetime.now()
        
        # Fill cache to max capacity
        for i in range(gemini_client.max_sessions + 10):
            session_time = now - timedelta(seconds=i)  # Older sessions have lower IDs
            gemini_client.active_sessions[i] = (mock_chat_session, session_time, session_time)
        
        stats = gemini_client.cleanup_expired_sessions()
        
        assert stats["sessions_removed_by_pressure"] > 0
        assert stats["cleanup_trigger"] == "memory_pressure"
        assert len(gemini_client.active_sessions) < gemini_client.max_sessions
    
    def test_force_cleanup_session(self, gemini_client, mock_chat_session):
        """Test explicit session removal."""
        now = datetime.now()
        gemini_client.active_sessions[123] = (mock_chat_session, now, now)
        
        result = gemini_client.force_cleanup_session(123)
        
        assert result is True
        assert 123 not in gemini_client.active_sessions
        
        # Test removing non-existent session
        result = gemini_client.force_cleanup_session(999)
        assert result is False
    
    def test_get_session_stats(self, gemini_client, mock_chat_session):
        """Test session statistics collection."""
        now = datetime.now()
        gemini_client.active_sessions[123] = (mock_chat_session, now, now)
        gemini_client.total_sessions_created = 5
        gemini_client.sessions_expired = 2
        gemini_client.cache_hits = 10
        gemini_client.cache_misses = 3
        
        stats = gemini_client.get_session_stats()
        
        assert stats["active_sessions"] == 1
        assert stats["total_sessions_created"] == 5
        assert stats["sessions_expired"] == 2
        assert abs(stats["cache_hit_ratio"] - (10 / 13)) < 0.001  # 10 hits out of 13 total
        assert stats["memory_usage_mb"] == 0.1  # 1 session * 0.1MB
        assert "last_cleanup" in stats
        assert "oldest_session_age_hours" in stats
    
    def test_session_validation(self, gemini_client, mock_chat_session):
        """Test session validation logic."""
        now = datetime.now()
        old_time = now - timedelta(seconds=3700)  # Expired
        
        # Add valid session
        gemini_client.active_sessions[123] = (mock_chat_session, now, now)
        assert gemini_client._validate_session(123) is True
        
        # Add expired session
        gemini_client.active_sessions[456] = (mock_chat_session, old_time, old_time)
        assert gemini_client._validate_session(456) is False
        
        # Test non-existent session
        assert gemini_client._validate_session(999) is False
    
    def test_should_cleanup_logic(self, gemini_client):
        """Test cleanup trigger logic."""
        # Fresh client should not need cleanup
        assert gemini_client._should_cleanup() is False
        
        # Set last cleanup to old time
        gemini_client.last_cleanup = datetime.now() - timedelta(seconds=400)
        assert gemini_client._should_cleanup() is True