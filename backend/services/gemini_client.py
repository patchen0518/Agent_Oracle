"""
Gemini API client wrapper for Google Generative AI integration.

Based on google-genai v1.33.0+ documentation (Context 7 lookup: 2025-01-27)
Implements chat session management, error handling, and API key configuration
following current best practices from googleapis/python-genai.
"""

import os
from typing import List, Optional, Dict, Tuple, Any
from datetime import datetime, timedelta
from google import genai
from google.genai import errors, types
from backend.utils.logging_config import get_logger


class GeminiClient:
    """
    Wrapper class for Google Generative AI client.
    
    Handles API key configuration, chat session management, and error handling
    for Gemini API interactions. Follows the latest patterns from the official
    google-genai Python SDK.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Gemini API key. If None, will use GEMINI_API_KEY or GOOGLE_API_KEY env var
            model: Model name to use for chat sessions. If None, will use GEMINI_MODEL env var or default to "gemini-2.5-flash"
            
        Raises:
            ValueError: If no API key is provided or found in environment
        """
        # Get model from parameter or environment, with fallback to default
        if model is None:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        self.model = model
        
        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        # Initialize client following latest documentation patterns
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini client: {str(e)}")
        
        # Session cache: session_id -> (ChatSession, last_used, created_at)
        self.active_sessions: Dict[int, Tuple[ChatSession, datetime, datetime]] = {}
        
        # Session management configuration
        self.session_timeout: int = int(os.getenv("PERSISTENT_SESSION_TIMEOUT", "3600"))  # 1 hour default
        self.max_sessions: int = int(os.getenv("MAX_PERSISTENT_SESSIONS", "500"))  # 500 sessions default
        self.cleanup_interval: int = int(os.getenv("CLEANUP_INTERVAL", "300"))  # 5 minutes default
        self.last_cleanup: datetime = datetime.now()
        
        # Statistics tracking
        self.total_sessions_created: int = 0
        self.sessions_expired: int = 0
        self.sessions_recovered: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        
        # Initialize logger
        self.logger = get_logger("gemini_client")
        
        # Performance metrics tracking
        self.performance_metrics = {
            "session_creation_times": [],
            "session_recovery_times": [],
            "cleanup_operations": [],
            "token_usage_reductions": [],
            "response_time_improvements": []
        }
    
    def get_or_create_session(self, session_id: int, system_instruction: Optional[str] = None) -> "ChatSession":
        """
        Get existing session from cache or create a new one.
        
        Args:
            session_id: The session ID to retrieve or create
            system_instruction: Optional system instruction for new sessions
            
        Returns:
            ChatSession: The cached or newly created chat session
            
        Raises:
            errors.APIError: If session creation fails
        """
        now = datetime.now()
        
        # Trigger cleanup if overdue
        if self._should_cleanup():
            self.cleanup_expired_sessions()
        
        # Check if session exists in cache
        if session_id in self.active_sessions:
            chat_session, last_used, created_at = self.active_sessions[session_id]
            
            # Check if session has expired
            if now - last_used > timedelta(seconds=self.session_timeout):
                # Session expired, remove from cache
                session_age_seconds = int((now - last_used).total_seconds())
                del self.active_sessions[session_id]
                self.sessions_expired += 1
                self.cache_misses += 1
                
                # Enhanced session expiration logging
                self.logger.info(
                    "session_expired",
                    extra={
                        "event_type": "session_lifecycle",
                        "action": "expired",
                        "session_id": session_id,
                        "age_seconds": session_age_seconds,
                        "timeout_seconds": self.session_timeout,
                        "active_sessions": len(self.active_sessions),
                        "sessions_expired_total": self.sessions_expired,
                        "cache_hit_ratio": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
                    }
                )
            else:
                # Session is valid, update last_used and return
                self.active_sessions[session_id] = (chat_session, now, created_at)
                self.cache_hits += 1
                
                # Enhanced cache hit logging
                self.logger.debug(
                    "session_cache_hit",
                    extra={
                        "event_type": "session_performance",
                        "action": "cache_hit",
                        "session_id": session_id,
                        "age_seconds": int((now - created_at).total_seconds()),
                        "cache_hit_ratio": self.cache_hits / (self.cache_hits + self.cache_misses),
                        "cache_hits": self.cache_hits,
                        "cache_misses": self.cache_misses,
                        "active_sessions": len(self.active_sessions)
                    }
                )
                return chat_session
        else:
            self.cache_misses += 1
        
        # Create new session with performance tracking
        session_creation_start = datetime.now()
        chat_session = self._create_fresh_session(session_id, system_instruction)
        session_creation_time = (datetime.now() - session_creation_start).total_seconds() * 1000
        
        # Track performance metrics
        self.performance_metrics["session_creation_times"].append({
            "timestamp": now.isoformat(),
            "session_id": session_id,
            "creation_time_ms": session_creation_time
        })
        
        # Keep only last 100 performance entries
        if len(self.performance_metrics["session_creation_times"]) > 100:
            self.performance_metrics["session_creation_times"] = self.performance_metrics["session_creation_times"][-100:]
        
        # Add to cache
        self.active_sessions[session_id] = (chat_session, now, now)
        self.total_sessions_created += 1
        
        # Enhanced session lifecycle logging
        self.logger.info(
            "session_created",
            extra={
                "event_type": "session_lifecycle",
                "action": "created",
                "session_id": session_id,
                "creation_time_ms": session_creation_time,
                "total_sessions_created": self.total_sessions_created,
                "active_sessions": len(self.active_sessions),
                "has_system_instruction": system_instruction is not None,
                "cache_size": len(self.active_sessions),
                "memory_usage_mb": len(self.active_sessions) * 0.1
            }
        )
        
        return chat_session
    
    def _create_fresh_session(self, session_id: int, system_instruction: Optional[str] = None) -> "ChatSession":
        """
        Create a new Gemini chat session.
        
        Args:
            session_id: The session ID for logging purposes
            system_instruction: Optional system instruction
            
        Returns:
            ChatSession: A new chat session instance
            
        Raises:
            errors.APIError: If session creation fails
        """
        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(
                    temperature=0.7,
                    system_instruction=system_instruction
                )
            
            # Create fresh chat session
            chat = self.client.chats.create(
                model=self.model,
                config=config
            )
            
            return ChatSession(chat)
            
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise errors.APIError(f"Failed to create chat session for session {session_id}: {str(e)}")
    
    def _should_cleanup(self) -> bool:
        """
        Check if cleanup should be triggered based on cleanup interval.
        
        Returns:
            bool: True if cleanup should be performed
        """
        return datetime.now() - self.last_cleanup > timedelta(seconds=self.cleanup_interval)
    
    def _validate_session(self, session_id: int) -> bool:
        """
        Validate if a session exists and is not expired.
        
        Args:
            session_id: The session ID to validate
            
        Returns:
            bool: True if session is valid and not expired
        """
        if session_id not in self.active_sessions:
            return False
        
        _, last_used, _ = self.active_sessions[session_id]
        return datetime.now() - last_used <= timedelta(seconds=self.session_timeout)
    
    def cleanup_expired_sessions(self) -> Dict[str, int]:
        """
        Remove expired sessions from cache and handle memory pressure.
        
        Returns:
            Dict[str, int]: Cleanup statistics including sessions removed and cleanup trigger
        """
        now = datetime.now()
        expired_sessions = []
        memory_pressure_sessions = []
        
        # Find expired sessions
        for session_id, (chat_session, last_used, created_at) in self.active_sessions.items():
            if now - last_used > timedelta(seconds=self.session_timeout):
                expired_sessions.append(session_id)
        
        # Remove expired sessions
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
            self.sessions_expired += 1
        
        # Handle memory pressure if approaching max_sessions limit
        sessions_removed_by_expiration = len(expired_sessions)
        sessions_removed_by_pressure = 0
        
        if len(self.active_sessions) >= self.max_sessions:
            # Sort sessions by last_used (oldest first) for memory pressure cleanup
            sorted_sessions = sorted(
                self.active_sessions.items(),
                key=lambda x: x[1][1]  # Sort by last_used timestamp
            )
            
            # Remove oldest sessions until we're under the limit
            target_removal = len(self.active_sessions) - int(self.max_sessions * 0.8)  # Remove to 80% capacity
            for i in range(min(target_removal, len(sorted_sessions))):
                session_id = sorted_sessions[i][0]
                memory_pressure_sessions.append(session_id)
                del self.active_sessions[session_id]
                sessions_removed_by_pressure += 1
        
        # Update cleanup timestamp
        self.last_cleanup = now
        
        # Determine cleanup trigger
        cleanup_trigger = "automatic"
        if sessions_removed_by_pressure > 0:
            cleanup_trigger = "memory_pressure"
        
        cleanup_stats = {
            "sessions_removed": sessions_removed_by_expiration + sessions_removed_by_pressure,
            "sessions_expired": sessions_removed_by_expiration,
            "sessions_removed_by_pressure": sessions_removed_by_pressure,
            "cleanup_trigger": cleanup_trigger,
            "cleanup_duration_ms": int((datetime.now() - now).total_seconds() * 1000),
            "active_sessions_remaining": len(self.active_sessions)
        }
        
        # Track cleanup performance
        cleanup_duration_ms = int((datetime.now() - now).total_seconds() * 1000)
        cleanup_stats["cleanup_duration_ms"] = cleanup_duration_ms
        
        # Store cleanup operation for monitoring
        self.performance_metrics["cleanup_operations"].append({
            "timestamp": now.isoformat(),
            "sessions_removed": cleanup_stats["sessions_removed"],
            "cleanup_trigger": cleanup_stats["cleanup_trigger"],
            "cleanup_duration_ms": cleanup_duration_ms,
            "memory_freed_mb": cleanup_stats["sessions_removed"] * 0.1
        })
        
        # Keep only last 50 cleanup operations
        if len(self.performance_metrics["cleanup_operations"]) > 50:
            self.performance_metrics["cleanup_operations"] = self.performance_metrics["cleanup_operations"][-50:]
        
        # Enhanced cleanup logging
        if cleanup_stats["sessions_removed"] > 0:
            self.logger.info(
                "session_cleanup_completed",
                extra={
                    "event_type": "session_lifecycle",
                    "action": "cleanup",
                    **cleanup_stats,
                    "memory_freed_mb": cleanup_stats["sessions_removed"] * 0.1,
                    "cleanup_efficiency": cleanup_stats["sessions_removed"] / max(1, self.total_sessions_created)
                }
            )
        
        return cleanup_stats
    
    def force_cleanup_session(self, session_id: int) -> bool:
        """
        Explicitly remove a specific session from cache.
        
        Args:
            session_id: The session ID to remove
            
        Returns:
            bool: True if session was found and removed, False if not found
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            
            # Enhanced manual cleanup logging
            self.logger.info(
                "session_force_removed",
                extra={
                    "event_type": "session_lifecycle",
                    "action": "force_removed",
                    "session_id": session_id,
                    "active_sessions": len(self.active_sessions),
                    "cleanup_trigger": "manual",
                    "memory_freed_mb": 0.1
                }
            )
            return True
        return False
    
    def _emergency_cleanup(self, target_removal: int) -> int:
        """
        Emergency cleanup when memory pressure is critical.
        
        Args:
            target_removal: Number of sessions to remove
            
        Returns:
            int: Number of sessions actually removed
        """
        if not self.active_sessions:
            return 0
        
        # Sort by last_used (oldest first)
        sorted_sessions = sorted(
            self.active_sessions.items(),
            key=lambda x: x[1][1]
        )
        
        removed_count = 0
        for i in range(min(target_removal, len(sorted_sessions))):
            session_id = sorted_sessions[i][0]
            del self.active_sessions[session_id]
            removed_count += 1
        
        return removed_count
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive session management statistics.
        
        Returns:
            Dict[str, Any]: Statistics including active count, hit ratios, memory usage
        """
        now = datetime.now()
        
        # Calculate cache hit ratio
        total_requests = self.cache_hits + self.cache_misses
        cache_hit_ratio = self.cache_hits / total_requests if total_requests > 0 else 0.0
        
        # Calculate memory usage (rough estimate)
        memory_usage_mb = len(self.active_sessions) * 0.1  # Rough estimate: 0.1MB per session
        
        # Find oldest session age
        oldest_session_age_hours = 0.0
        if self.active_sessions:
            oldest_created = min(created_at for _, _, created_at in self.active_sessions.values())
            oldest_session_age_hours = (now - oldest_created).total_seconds() / 3600
        
        return {
            "active_sessions": len(self.active_sessions),
            "total_sessions_created": self.total_sessions_created,
            "sessions_expired": self.sessions_expired,
            "sessions_recovered": self.sessions_recovered,
            "cache_hit_ratio": round(cache_hit_ratio, 3),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "memory_usage_mb": round(memory_usage_mb, 2),
            "last_cleanup": self.last_cleanup.isoformat(),
            "oldest_session_age_hours": round(oldest_session_age_hours, 2),
            "session_timeout_seconds": self.session_timeout,
            "max_sessions": self.max_sessions,
            "cleanup_interval_seconds": self.cleanup_interval,
            "performance_metrics": self._get_performance_summary()
        }
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance metrics summary for monitoring.
        
        Returns:
            Dict[str, Any]: Performance metrics summary
        """
        summary = {
            "session_creation": {
                "total_operations": len(self.performance_metrics["session_creation_times"]),
                "avg_creation_time_ms": 0,
                "min_creation_time_ms": 0,
                "max_creation_time_ms": 0
            },
            "session_recovery": {
                "total_operations": len(self.performance_metrics["session_recovery_times"]),
                "avg_recovery_time_ms": 0,
                "min_recovery_time_ms": 0,
                "max_recovery_time_ms": 0
            },
            "cleanup_operations": {
                "total_operations": len(self.performance_metrics["cleanup_operations"]),
                "avg_cleanup_time_ms": 0,
                "total_sessions_cleaned": 0,
                "total_memory_freed_mb": 0
            },
            "token_usage": {
                "estimated_reduction_percent": 0,
                "total_optimizations": len(self.performance_metrics["token_usage_reductions"])
            },
            "response_times": {
                "estimated_improvement_percent": 0,
                "total_measurements": len(self.performance_metrics["response_time_improvements"])
            }
        }
        
        # Calculate session creation metrics
        if self.performance_metrics["session_creation_times"]:
            creation_times = [op["creation_time_ms"] for op in self.performance_metrics["session_creation_times"]]
            summary["session_creation"]["avg_creation_time_ms"] = round(sum(creation_times) / len(creation_times), 2)
            summary["session_creation"]["min_creation_time_ms"] = min(creation_times)
            summary["session_creation"]["max_creation_time_ms"] = max(creation_times)
        
        # Calculate session recovery metrics
        if self.performance_metrics["session_recovery_times"]:
            recovery_times = [op["recovery_time_ms"] for op in self.performance_metrics["session_recovery_times"]]
            summary["session_recovery"]["avg_recovery_time_ms"] = round(sum(recovery_times) / len(recovery_times), 2)
            summary["session_recovery"]["min_recovery_time_ms"] = min(recovery_times)
            summary["session_recovery"]["max_recovery_time_ms"] = max(recovery_times)
        
        # Calculate cleanup metrics
        if self.performance_metrics["cleanup_operations"]:
            cleanup_times = [op["cleanup_duration_ms"] for op in self.performance_metrics["cleanup_operations"]]
            sessions_cleaned = sum(op["sessions_removed"] for op in self.performance_metrics["cleanup_operations"])
            memory_freed = sum(op.get("memory_freed_mb", 0) for op in self.performance_metrics["cleanup_operations"])
            
            summary["cleanup_operations"]["avg_cleanup_time_ms"] = round(sum(cleanup_times) / len(cleanup_times), 2)
            summary["cleanup_operations"]["total_sessions_cleaned"] = sessions_cleaned
            summary["cleanup_operations"]["total_memory_freed_mb"] = round(memory_freed, 2)
        
        # Calculate token usage reduction (estimated)
        if self.cache_hits > 0:
            # Estimate 70% token reduction for cache hits
            summary["token_usage"]["estimated_reduction_percent"] = 70
        
        # Calculate response time improvement (estimated)
        if self.cache_hits > 0:
            # Estimate 40% response time improvement for cache hits
            summary["response_times"]["estimated_improvement_percent"] = 40
        
        return summary
    
    def track_session_recovery(self, session_id: int, recovery_time_ms: float, success: bool) -> None:
        """
        Track session recovery performance metrics.
        
        Args:
            session_id: The session ID that was recovered
            recovery_time_ms: Time taken for recovery in milliseconds
            success: Whether recovery was successful
        """
        recovery_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "recovery_time_ms": recovery_time_ms,
            "success": success
        }
        
        self.performance_metrics["session_recovery_times"].append(recovery_entry)
        
        # Keep only last 100 recovery entries
        if len(self.performance_metrics["session_recovery_times"]) > 100:
            self.performance_metrics["session_recovery_times"] = self.performance_metrics["session_recovery_times"][-100:]
        
        # Log recovery performance
        self.logger.info(
            "session_recovery_tracked",
            extra={
                "event_type": "session_performance",
                "action": "recovery_tracked",
                "session_id": session_id,
                "recovery_time_ms": recovery_time_ms,
                "recovery_success": success,
                "total_recoveries": len(self.performance_metrics["session_recovery_times"])
            }
        )
    
    def track_token_usage_reduction(self, session_id: int, estimated_reduction_percent: float) -> None:
        """
        Track estimated token usage reduction from persistent sessions.
        
        Args:
            session_id: The session ID
            estimated_reduction_percent: Estimated percentage of token reduction
        """
        token_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "reduction_percent": estimated_reduction_percent
        }
        
        self.performance_metrics["token_usage_reductions"].append(token_entry)
        
        # Keep only last 100 token entries
        if len(self.performance_metrics["token_usage_reductions"]) > 100:
            self.performance_metrics["token_usage_reductions"] = self.performance_metrics["token_usage_reductions"][-100:]
    
    def track_response_time_improvement(self, session_id: int, improvement_percent: float) -> None:
        """
        Track response time improvements from persistent sessions.
        
        Args:
            session_id: The session ID
            improvement_percent: Percentage improvement in response time
        """
        response_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "improvement_percent": improvement_percent
        }
        
        self.performance_metrics["response_time_improvements"].append(response_entry)
        
        # Keep only last 100 response entries
        if len(self.performance_metrics["response_time_improvements"]) > 100:
            self.performance_metrics["response_time_improvements"] = self.performance_metrics["response_time_improvements"][-100:]
    
    def create_chat_session(self, system_instruction: Optional[str] = None) -> "ChatSession":
        """
        Create a new chat session with optional conversation history.
        
        The Gemini SDK automatically manages conversation history within chat sessions.
        For single-session applications, we create a fresh session each time and rely
        on the system instruction to maintain the AI's identity and behavior.
        
        Args:
            system_instruction: Optional system instruction for the chat session
            history: Optional conversation history (currently not used - see note below)
            
        Returns:
            ChatSession: A new chat session instance
            
        Raises:
            errors.APIError: If chat session creation fails
            
        Note:
            The history parameter is accepted for API compatibility but not currently used.
            The Gemini SDK manages conversation history automatically within sessions.
            For stateless applications, each request creates a fresh session with the
            system instruction, ensuring consistent AI behavior.
        """
        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(
                    temperature=0.7,
                    system_instruction=system_instruction
                )
            
            # Create fresh chat session
            # The SDK will automatically manage conversation history within this session
            chat = self.client.chats.create(
                model=self.model,
                config=config
            )
            
            return ChatSession(chat)
            
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise errors.APIError(f"Failed to create chat session: {str(e)}")
    

    
    def _handle_api_error(self, error: errors.APIError) -> errors.APIError:
        """
        Handle and enrich API errors with specific messages.
        
        Args:
            error: The original API error
            
        Returns:
            errors.APIError: Enhanced error with specific messaging
        """
        error_messages = {
            404: "Model not found or invalid model name",
            429: "Rate limit exceeded. Please try again later",
            400: "Invalid request format or parameters",
            401: "Invalid API key or authentication failed",
            403: "Access forbidden. Check API key permissions",
            500: "Internal server error. Please try again later"
        }
        
        specific_message = error_messages.get(error.code, "Unknown API error")
        enhanced_message = f"{specific_message}. Original error: {error.message}"
        
        # Create new error with enhanced message but preserve original code
        new_error = errors.APIError(enhanced_message, {})
        new_error.code = error.code
        return new_error


class ChatSession:
    """
    Wrapper for Gemini chat session with conversation management.
    
    Provides methods for sending messages, managing history, and handling
    responses following the latest Gemini API patterns from Context 7 documentation.
    """
    
    def __init__(self, chat_session):
        """
        Initialize chat session wrapper.
        
        Args:
            chat_session: The underlying Gemini chat session object
        """
        self.chat = chat_session
    
    def send_message(self, message: str) -> str:
        """
        Send a message to the chat session.
        
        The chat session automatically maintains conversation history,
        so no need to manually pass history - it's handled by the SDK.
        
        Args:
            message: The user message to send
            
        Returns:
            str: The model's response text
            
        Raises:
            errors.APIError: If the API call fails
        """
        try:
            # The new SDK automatically manages conversation history within the chat session
            response = self.chat.send_message(message)
            return response.text
            
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise ValueError(f"Failed to send message: {str(e)}")
    
    def send_message_stream(self, message: str):
        """
        Send a message and get streaming response.
        
        Args:
            message: The user message to send
            
        Yields:
            str: Chunks of the model's response as they arrive
            
        Raises:
            errors.APIError: If the API call fails
        """
        try:
            for chunk in self.chat.send_message_stream(message):
                yield chunk.text
                
        except errors.APIError as e:
            raise self._handle_api_error(e)
        except Exception as e:
            raise ValueError(f"Failed to send streaming message: {str(e)}")
    
    def get_history(self) -> List[dict]:
        """
        Get the conversation history from the chat session.
        
        Returns:
            List[dict]: List of messages in the conversation as dictionaries
        """
        try:
            # Use the SDK's built-in history management
            history = self.chat.get_history()
            chat_messages = []
            
            for message in history:
                # Convert Gemini message format to dictionary
                chat_message = {
                    "role": message.role,
                    "content": message.parts[0].text if message.parts and len(message.parts) > 0 else ""
                }
                chat_messages.append(chat_message)
            
            return chat_messages
            
        except Exception as e:
            # Return empty history if retrieval fails
            return []
    

    
    def _handle_api_error(self, error: errors.APIError) -> errors.APIError:
        """
        Handle and enrich API errors with specific messages.
        
        Args:
            error: The original API error
            
        Returns:
            errors.APIError: Enhanced error with specific messaging
        """
        error_messages = {
            404: "Model not found or invalid model name",
            429: "Rate limit exceeded. Please try again later",
            400: "Invalid request format or parameters",
            401: "Invalid API key or authentication failed",
            403: "Access forbidden. Check API key permissions",
            500: "Internal server error. Please try again later"
        }
        
        specific_message = error_messages.get(error.code, "Unknown API error")
        enhanced_message = f"{specific_message}. Original error: {error.message}"
        
        new_error = errors.APIError(enhanced_message, {})
        new_error.code = error.code
        return new_error