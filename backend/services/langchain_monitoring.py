"""
LangChain monitoring and observability service.

Provides comprehensive monitoring, logging, and metrics collection for
LangChain operations including memory management, context optimization,
and token usage tracking.
"""

import time
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
from functools import wraps

from backend.utils.logging_config import get_logger


class OperationType(Enum):
    """Types of LangChain operations to monitor."""
    CLIENT_INIT = "client_init"
    SESSION_CREATE = "session_create"
    SESSION_RESTORE = "session_restore"
    MESSAGE_SEND = "message_send"
    MESSAGE_STREAM = "message_stream"
    CONTEXT_OPTIMIZE = "context_optimize"
    MEMORY_OPERATION = "memory_operation"
    SUMMARIZATION = "summarization"
    TOKEN_CALCULATION = "token_calculation"
    FALLBACK_TRIGGER = "fallback_trigger"


class OperationStatus(Enum):
    """Status of monitored operations."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    FALLBACK = "fallback"


@dataclass
class OperationMetrics:
    """Metrics for a single LangChain operation."""
    operation_type: OperationType
    session_id: Optional[int]
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: OperationStatus = OperationStatus.SUCCESS
    
    # Context and optimization metrics
    input_messages: int = 0
    output_messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_saved: int = 0
    
    # Memory strategy metrics
    memory_strategy: Optional[str] = None
    memory_operations: int = 0
    fallback_triggered: bool = False
    
    # Error information
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    
    # Additional context
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def complete(self, status: OperationStatus = OperationStatus.SUCCESS, **kwargs):
        """Mark operation as complete and calculate duration."""
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
        
        # Update any additional metrics
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging."""
        data = asdict(self)
        
        # Convert enums to strings
        data['operation_type'] = self.operation_type.value
        data['status'] = self.status.value
        
        # Convert datetime objects to ISO strings
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        
        return data


class LangChainMonitor:
    """
    Comprehensive monitoring service for LangChain operations.
    
    Provides structured logging, metrics collection, and performance tracking
    for all LangChain-related operations in the system.
    """
    
    def __init__(self):
        """Initialize the LangChain monitor."""
        self.logger = get_logger("langchain_monitor")
        
        # Operation tracking
        self.active_operations: Dict[str, OperationMetrics] = {}
        self.completed_operations: List[OperationMetrics] = []
        self.max_completed_operations = 1000  # Keep last 1000 operations
        
        # Aggregated statistics
        self.operation_counts: Dict[str, int] = {}
        self.error_counts: Dict[str, int] = {}
        self.total_tokens_processed = 0
        self.total_tokens_saved = 0
        self.total_fallbacks_triggered = 0
        
        # Performance tracking
        self.performance_stats: Dict[str, Dict[str, float]] = {}
        
        self.logger.info("LangChain monitor initialized")
    
    def start_operation(
        self, 
        operation_type: OperationType, 
        session_id: Optional[int] = None,
        **metadata
    ) -> str:
        """
        Start monitoring a LangChain operation.
        
        Args:
            operation_type: Type of operation being monitored
            session_id: Optional session ID
            **metadata: Additional metadata for the operation
            
        Returns:
            Operation ID for tracking
        """
        operation_id = f"{operation_type.value}_{int(time.time() * 1000000)}"
        
        metrics = OperationMetrics(
            operation_type=operation_type,
            session_id=session_id,
            start_time=datetime.utcnow(),
            metadata=metadata
        )
        
        self.active_operations[operation_id] = metrics
        
        # Log operation start
        self.logger.debug(
            f"Started {operation_type.value} operation",
            extra={
                "operation_id": operation_id,
                "session_id": session_id,
                "operation_type": operation_type.value,
                "metadata": metadata
            }
        )
        
        return operation_id
    
    def complete_operation(
        self, 
        operation_id: str, 
        status: OperationStatus = OperationStatus.SUCCESS,
        **metrics
    ) -> None:
        """
        Complete a monitored operation and record metrics.
        
        Args:
            operation_id: ID of the operation to complete
            status: Final status of the operation
            **metrics: Additional metrics to record
        """
        if operation_id not in self.active_operations:
            self.logger.warning(f"Unknown operation ID: {operation_id}")
            return
        
        operation_metrics = self.active_operations.pop(operation_id)
        operation_metrics.complete(status, **metrics)
        
        # Add to completed operations
        self.completed_operations.append(operation_metrics)
        
        # Maintain size limit
        if len(self.completed_operations) > self.max_completed_operations:
            self.completed_operations = self.completed_operations[-self.max_completed_operations:]
        
        # Update aggregated statistics
        self._update_statistics(operation_metrics)
        
        # Record performance metrics if available
        try:
            # Import here to avoid circular imports
            from backend.services.langchain_performance_monitor import performance_monitor
            
            # Calculate context compression ratio
            context_compression_ratio = 1.0
            if operation_metrics.input_messages > 0 and operation_metrics.output_messages > 0:
                context_compression_ratio = operation_metrics.output_messages / operation_metrics.input_messages
            
            # Record performance data
            performance_monitor.record_operation_performance(
                operation_type=operation_metrics.operation_type.value,
                session_id=operation_metrics.session_id,
                duration_ms=operation_metrics.duration_ms or 0,
                input_tokens=operation_metrics.input_tokens,
                output_tokens=operation_metrics.output_tokens,
                tokens_saved=operation_metrics.tokens_saved,
                input_messages=operation_metrics.input_messages,
                output_messages=operation_metrics.output_messages,
                context_compression_ratio=context_compression_ratio,
                memory_strategy=operation_metrics.memory_strategy,
                fallback_triggered=operation_metrics.fallback_triggered,
                optimization_applied=operation_metrics.tokens_saved > 0
            )
        except ImportError:
            # Performance monitor not available
            pass
        except Exception as e:
            self.logger.debug(f"Failed to record performance metrics: {e}")
        
        # Log operation completion
        log_level = "info" if status == OperationStatus.SUCCESS else "warning"
        log_data = {
            "operation_id": operation_id,
            "operation_type": operation_metrics.operation_type.value,
            "session_id": operation_metrics.session_id,
            "duration_ms": operation_metrics.duration_ms,
            "status": status.value,
            "input_messages": operation_metrics.input_messages,
            "output_messages": operation_metrics.output_messages,
            "input_tokens": operation_metrics.input_tokens,
            "output_tokens": operation_metrics.output_tokens,
            "tokens_saved": operation_metrics.tokens_saved,
            "memory_strategy": operation_metrics.memory_strategy,
            "fallback_triggered": operation_metrics.fallback_triggered
        }
        
        if status == OperationStatus.ERROR:
            log_data.update({
                "error_type": operation_metrics.error_type,
                "error_message": operation_metrics.error_message
            })
        
        getattr(self.logger, log_level)(
            f"Completed {operation_metrics.operation_type.value} operation: {status.value}",
            extra=log_data
        )
    
    def record_error(
        self, 
        operation_id: str, 
        error: Exception, 
        additional_context: Dict[str, Any] = None
    ) -> None:
        """
        Record an error for a monitored operation.
        
        Args:
            operation_id: ID of the operation that failed
            error: The exception that occurred
            additional_context: Additional error context
        """
        if operation_id in self.active_operations:
            operation_metrics = self.active_operations[operation_id]
            operation_metrics.error_type = type(error).__name__
            operation_metrics.error_message = str(error)
            
            if additional_context:
                operation_metrics.metadata.update(additional_context)
        
        # Complete the operation with error status
        self.complete_operation(operation_id, OperationStatus.ERROR)
        
        # Log detailed error information
        self.logger.error(
            f"Operation {operation_id} failed: {type(error).__name__}",
            extra={
                "operation_id": operation_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "additional_context": additional_context or {}
            },
            exc_info=True
        )
    
    def record_fallback(
        self, 
        operation_id: str, 
        fallback_reason: str,
        fallback_strategy: str = None
    ) -> None:
        """
        Record a fallback event for a monitored operation.
        
        Args:
            operation_id: ID of the operation that triggered fallback
            fallback_reason: Reason for the fallback
            fallback_strategy: Strategy used for fallback
        """
        if operation_id in self.active_operations:
            operation_metrics = self.active_operations[operation_id]
            operation_metrics.fallback_triggered = True
            operation_metrics.metadata.update({
                "fallback_reason": fallback_reason,
                "fallback_strategy": fallback_strategy
            })
        
        self.total_fallbacks_triggered += 1
        
        # Log fallback event
        self.logger.warning(
            f"Fallback triggered for operation {operation_id}: {fallback_reason}",
            extra={
                "operation_id": operation_id,
                "fallback_reason": fallback_reason,
                "fallback_strategy": fallback_strategy
            }
        )
    
    def log_memory_strategy_usage(
        self, 
        session_id: int, 
        strategy: str, 
        operation_details: Dict[str, Any]
    ) -> None:
        """
        Log memory strategy usage and performance.
        
        Args:
            session_id: Session ID using the memory strategy
            strategy: Memory strategy name
            operation_details: Details about the memory operation
        """
        self.logger.info(
            f"Memory strategy '{strategy}' used for session {session_id}",
            extra={
                "session_id": session_id,
                "memory_strategy": strategy,
                "operation_details": operation_details,
                "event_type": "memory_strategy_usage"
            }
        )
    
    def log_context_optimization(
        self, 
        session_id: int, 
        optimization_details: Dict[str, Any]
    ) -> None:
        """
        Log context optimization decisions and results.
        
        Args:
            session_id: Session ID being optimized
            optimization_details: Details about the optimization
        """
        self.logger.info(
            f"Context optimization performed for session {session_id}",
            extra={
                "session_id": session_id,
                "optimization_details": optimization_details,
                "event_type": "context_optimization"
            }
        )
    
    def log_token_usage(
        self, 
        session_id: int, 
        token_details: Dict[str, Any]
    ) -> None:
        """
        Log token usage statistics and optimization results.
        
        Args:
            session_id: Session ID for token usage
            token_details: Token usage details
        """
        # Update total tokens processed
        if "tokens_processed" in token_details:
            self.total_tokens_processed += token_details["tokens_processed"]
        
        if "tokens_saved" in token_details:
            self.total_tokens_saved += token_details["tokens_saved"]
        
        self.logger.info(
            f"Token usage recorded for session {session_id}",
            extra={
                "session_id": session_id,
                "token_details": token_details,
                "event_type": "token_usage"
            }
        )
    
    def _update_statistics(self, operation_metrics: OperationMetrics) -> None:
        """Update aggregated statistics with completed operation."""
        op_type = operation_metrics.operation_type.value
        
        # Update operation counts
        self.operation_counts[op_type] = self.operation_counts.get(op_type, 0) + 1
        
        # Update error counts
        if operation_metrics.status == OperationStatus.ERROR:
            error_key = f"{op_type}_{operation_metrics.error_type or 'unknown'}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Update token statistics
        self.total_tokens_processed += operation_metrics.input_tokens + operation_metrics.output_tokens
        self.total_tokens_saved += operation_metrics.tokens_saved
        
        # Update fallback statistics
        if operation_metrics.fallback_triggered:
            self.total_fallbacks_triggered += 1
        
        # Update performance statistics
        if operation_metrics.duration_ms is not None:
            if op_type not in self.performance_stats:
                self.performance_stats[op_type] = {
                    "count": 0,
                    "total_duration": 0.0,
                    "min_duration": float('inf'),
                    "max_duration": 0.0
                }
            
            stats = self.performance_stats[op_type]
            stats["count"] += 1
            stats["total_duration"] += operation_metrics.duration_ms
            stats["min_duration"] = min(stats["min_duration"], operation_metrics.duration_ms)
            stats["max_duration"] = max(stats["max_duration"], operation_metrics.duration_ms)
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring statistics.
        
        Returns:
            Dictionary containing all monitoring statistics
        """
        # Calculate performance averages
        performance_summary = {}
        for op_type, stats in self.performance_stats.items():
            if stats["count"] > 0:
                performance_summary[op_type] = {
                    "count": stats["count"],
                    "avg_duration_ms": stats["total_duration"] / stats["count"],
                    "min_duration_ms": stats["min_duration"],
                    "max_duration_ms": stats["max_duration"]
                }
        
        # Recent operations (last 100)
        recent_operations = []
        for op in self.completed_operations[-100:]:
            recent_operations.append({
                "operation_type": op.operation_type.value,
                "session_id": op.session_id,
                "duration_ms": op.duration_ms,
                "status": op.status.value,
                "tokens_saved": op.tokens_saved,
                "fallback_triggered": op.fallback_triggered,
                "timestamp": op.start_time.isoformat()
            })
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_operations": len(self.active_operations),
            "completed_operations": len(self.completed_operations),
            "operation_counts": self.operation_counts,
            "error_counts": self.error_counts,
            "performance_stats": performance_summary,
            "token_statistics": {
                "total_tokens_processed": self.total_tokens_processed,
                "total_tokens_saved": self.total_tokens_saved,
                "total_fallbacks_triggered": self.total_fallbacks_triggered
            },
            "recent_operations": recent_operations
        }
    
    def get_session_stats(self, session_id: int) -> Dict[str, Any]:
        """
        Get monitoring statistics for a specific session.
        
        Args:
            session_id: Session ID to get stats for
            
        Returns:
            Dictionary containing session-specific statistics
        """
        session_operations = [
            op for op in self.completed_operations 
            if op.session_id == session_id
        ]
        
        if not session_operations:
            return {
                "session_id": session_id,
                "operations_count": 0,
                "message": "No operations found for this session"
            }
        
        # Calculate session statistics
        total_duration = sum(op.duration_ms or 0 for op in session_operations)
        total_tokens_saved = sum(op.tokens_saved for op in session_operations)
        fallback_count = sum(1 for op in session_operations if op.fallback_triggered)
        error_count = sum(1 for op in session_operations if op.status == OperationStatus.ERROR)
        
        # Operation type breakdown
        operation_breakdown = {}
        for op in session_operations:
            op_type = op.operation_type.value
            if op_type not in operation_breakdown:
                operation_breakdown[op_type] = {"count": 0, "avg_duration": 0, "total_duration": 0}
            
            operation_breakdown[op_type]["count"] += 1
            operation_breakdown[op_type]["total_duration"] += op.duration_ms or 0
        
        # Calculate averages
        for op_type, stats in operation_breakdown.items():
            if stats["count"] > 0:
                stats["avg_duration"] = stats["total_duration"] / stats["count"]
        
        return {
            "session_id": session_id,
            "operations_count": len(session_operations),
            "total_duration_ms": total_duration,
            "total_tokens_saved": total_tokens_saved,
            "fallback_count": fallback_count,
            "error_count": error_count,
            "success_rate": (len(session_operations) - error_count) / len(session_operations),
            "operation_breakdown": operation_breakdown,
            "first_operation": session_operations[0].start_time.isoformat(),
            "last_operation": session_operations[-1].start_time.isoformat()
        }
    
    def reset_stats(self) -> None:
        """Reset all monitoring statistics."""
        self.completed_operations.clear()
        self.operation_counts.clear()
        self.error_counts.clear()
        self.performance_stats.clear()
        self.total_tokens_processed = 0
        self.total_tokens_saved = 0
        self.total_fallbacks_triggered = 0
        
        self.logger.info("Monitoring statistics reset")
    
    @contextmanager
    def monitor_operation(
        self, 
        operation_type: OperationType, 
        session_id: Optional[int] = None,
        **metadata
    ):
        """
        Context manager for monitoring LangChain operations.
        
        Args:
            operation_type: Type of operation to monitor
            session_id: Optional session ID
            **metadata: Additional metadata
            
        Yields:
            Operation ID for additional logging
        """
        operation_id = self.start_operation(operation_type, session_id, **metadata)
        
        try:
            yield operation_id
            self.complete_operation(operation_id, OperationStatus.SUCCESS)
        except Exception as e:
            self.record_error(operation_id, e)
            raise


# Global monitor instance
langchain_monitor = LangChainMonitor()


def monitor_langchain_operation(
    operation_type: OperationType,
    session_id: Optional[int] = None,
    **metadata
):
    """
    Decorator for monitoring LangChain operations.
    
    Args:
        operation_type: Type of operation to monitor
        session_id: Optional session ID
        **metadata: Additional metadata
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract session_id from args/kwargs if not provided
            actual_session_id = session_id
            if actual_session_id is None:
                # Try to extract from self.session_id or kwargs
                if args and hasattr(args[0], 'session_id'):
                    actual_session_id = args[0].session_id
                elif 'session_id' in kwargs:
                    actual_session_id = kwargs['session_id']
            
            with langchain_monitor.monitor_operation(
                operation_type, 
                actual_session_id, 
                **metadata
            ) as operation_id:
                try:
                    result = func(*args, **kwargs)
                    
                    # Try to extract metrics from result if it's a dict
                    if isinstance(result, dict) and 'metrics' in result:
                        metrics = result['metrics']
                        langchain_monitor.complete_operation(operation_id, **metrics)
                    
                    return result
                except Exception as e:
                    langchain_monitor.record_error(operation_id, e)
                    raise
        
        return wrapper
    return decorator