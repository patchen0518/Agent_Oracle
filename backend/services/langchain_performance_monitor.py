"""
LangChain performance monitoring and metrics collection.

Provides comprehensive performance tracking, health checks, and metrics
comparison between LangChain and previous implementations.
"""

import time
import psutil
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import statistics

from backend.utils.logging_config import get_logger
from backend.services.langchain_monitoring import langchain_monitor


@dataclass
class PerformanceMetrics:
    """Performance metrics for LangChain operations."""
    timestamp: datetime
    operation_type: str
    session_id: Optional[int]
    duration_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    
    # Token metrics
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_saved: int = 0
    
    # Context metrics
    input_messages: int = 0
    output_messages: int = 0
    context_compression_ratio: float = 1.0
    
    # Memory strategy metrics
    memory_strategy: Optional[str] = None
    fallback_triggered: bool = False
    optimization_applied: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class PerformanceComparator:
    """
    Compares LangChain performance with previous implementation.
    
    Tracks improvements in token usage, response times, and memory efficiency.
    """
    
    def __init__(self):
        """Initialize the performance comparator."""
        self.logger = get_logger("langchain_performance")
        
        # Baseline metrics (from previous implementation)
        self.baseline_metrics = {
            "avg_response_time_ms": 1500.0,  # Estimated baseline
            "avg_tokens_per_request": 2000,   # Estimated baseline
            "memory_usage_mb": 150.0,         # Estimated baseline
            "error_rate": 0.05                # 5% error rate baseline
        }
        
        # Current metrics tracking
        self.current_metrics: deque = deque(maxlen=1000)  # Keep last 1000 operations
        self.session_metrics: Dict[int, List[PerformanceMetrics]] = defaultdict(list)
        
        # Performance statistics
        self.total_operations = 0
        self.total_errors = 0
        self.total_tokens_saved = 0
        self.total_response_time = 0.0
        
        # Health status tracking
        self.health_status = "healthy"
        self.last_health_check = datetime.utcnow()
        self.health_issues: List[str] = []
        
        self.logger.info("LangChain performance monitor initialized")
    
    def record_operation_performance(
        self,
        operation_type: str,
        session_id: Optional[int],
        duration_ms: float,
        **metrics
    ) -> None:
        """
        Record performance metrics for a LangChain operation.
        
        Args:
            operation_type: Type of operation performed
            session_id: Session ID if applicable
            duration_ms: Operation duration in milliseconds
            **metrics: Additional performance metrics
        """
        try:
            # Get system metrics
            memory_usage = psutil.virtual_memory().used / (1024 * 1024)  # MB
            cpu_usage = psutil.cpu_percent(interval=None)
            
            # Create performance metrics
            perf_metrics = PerformanceMetrics(
                timestamp=datetime.utcnow(),
                operation_type=operation_type,
                session_id=session_id,
                duration_ms=duration_ms,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage,
                input_tokens=metrics.get('input_tokens', 0),
                output_tokens=metrics.get('output_tokens', 0),
                tokens_saved=metrics.get('tokens_saved', 0),
                input_messages=metrics.get('input_messages', 0),
                output_messages=metrics.get('output_messages', 0),
                context_compression_ratio=metrics.get('context_compression_ratio', 1.0),
                memory_strategy=metrics.get('memory_strategy'),
                fallback_triggered=metrics.get('fallback_triggered', False),
                optimization_applied=metrics.get('optimization_applied', False)
            )
            
            # Add to tracking collections
            self.current_metrics.append(perf_metrics)
            if session_id:
                self.session_metrics[session_id].append(perf_metrics)
            
            # Update aggregate statistics
            self.total_operations += 1
            self.total_response_time += duration_ms
            self.total_tokens_saved += metrics.get('tokens_saved', 0)
            
            # Log performance data
            self.logger.debug(
                f"Performance recorded: {operation_type} - {duration_ms:.2f}ms",
                extra={
                    "operation_type": operation_type,
                    "session_id": session_id,
                    "duration_ms": duration_ms,
                    "memory_usage_mb": memory_usage,
                    "tokens_saved": metrics.get('tokens_saved', 0),
                    "optimization_applied": metrics.get('optimization_applied', False)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to record performance metrics: {e}")
    
    def get_performance_comparison(self) -> Dict[str, Any]:
        """
        Get performance comparison between LangChain and baseline.
        
        Returns:
            Dictionary containing performance comparison metrics
        """
        if not self.current_metrics:
            return {
                "status": "no_data",
                "message": "No performance data available for comparison"
            }
        
        try:
            # Calculate current performance statistics
            recent_metrics = list(self.current_metrics)[-100:]  # Last 100 operations
            
            current_stats = self._calculate_current_stats(recent_metrics)
            improvements = self._calculate_improvements(current_stats)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "comparison_period": "last_100_operations",
                "baseline_metrics": self.baseline_metrics,
                "current_metrics": current_stats,
                "improvements": improvements,
                "total_operations": self.total_operations,
                "total_tokens_saved": self.total_tokens_saved,
                "performance_trend": self._analyze_performance_trend()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate performance comparison: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate comparison: {str(e)}"
            }
    
    def _calculate_current_stats(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Calculate current performance statistics."""
        if not metrics:
            return {}
        
        durations = [m.duration_ms for m in metrics]
        memory_usage = [m.memory_usage_mb for m in metrics]
        tokens_per_request = [m.input_tokens + m.output_tokens for m in metrics if m.input_tokens + m.output_tokens > 0]
        
        # Calculate error rate from monitoring data
        monitoring_stats = langchain_monitor.get_monitoring_stats()
        total_ops = sum(monitoring_stats.get('operation_counts', {}).values())
        total_errors = sum(monitoring_stats.get('error_counts', {}).values())
        error_rate = total_errors / max(1, total_ops)
        
        return {
            "avg_response_time_ms": statistics.mean(durations) if durations else 0,
            "median_response_time_ms": statistics.median(durations) if durations else 0,
            "p95_response_time_ms": self._calculate_percentile(durations, 95) if durations else 0,
            "avg_memory_usage_mb": statistics.mean(memory_usage) if memory_usage else 0,
            "avg_tokens_per_request": statistics.mean(tokens_per_request) if tokens_per_request else 0,
            "error_rate": error_rate,
            "operations_with_optimization": sum(1 for m in metrics if m.optimization_applied),
            "operations_with_fallback": sum(1 for m in metrics if m.fallback_triggered),
            "total_tokens_saved": sum(m.tokens_saved for m in metrics)
        }
    
    def _calculate_improvements(self, current_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate improvements over baseline."""
        if not current_stats:
            return {}
        
        improvements = {}
        
        # Response time improvement
        if current_stats.get("avg_response_time_ms", 0) > 0:
            response_time_improvement = (
                (self.baseline_metrics["avg_response_time_ms"] - current_stats["avg_response_time_ms"]) /
                self.baseline_metrics["avg_response_time_ms"] * 100
            )
            improvements["response_time_improvement_percent"] = response_time_improvement
        
        # Token usage improvement
        if current_stats.get("avg_tokens_per_request", 0) > 0:
            token_improvement = (
                (self.baseline_metrics["avg_tokens_per_request"] - current_stats["avg_tokens_per_request"]) /
                self.baseline_metrics["avg_tokens_per_request"] * 100
            )
            improvements["token_usage_improvement_percent"] = token_improvement
        
        # Memory usage improvement
        if current_stats.get("avg_memory_usage_mb", 0) > 0:
            memory_improvement = (
                (self.baseline_metrics["memory_usage_mb"] - current_stats["avg_memory_usage_mb"]) /
                self.baseline_metrics["memory_usage_mb"] * 100
            )
            improvements["memory_usage_improvement_percent"] = memory_improvement
        
        # Error rate improvement
        error_improvement = (
            (self.baseline_metrics["error_rate"] - current_stats["error_rate"]) /
            self.baseline_metrics["error_rate"] * 100
        )
        improvements["error_rate_improvement_percent"] = error_improvement
        
        # Overall performance score (weighted average)
        weights = {
            "response_time": 0.3,
            "token_usage": 0.4,
            "memory_usage": 0.2,
            "error_rate": 0.1
        }
        
        overall_score = (
            improvements.get("response_time_improvement_percent", 0) * weights["response_time"] +
            improvements.get("token_usage_improvement_percent", 0) * weights["token_usage"] +
            improvements.get("memory_usage_improvement_percent", 0) * weights["memory_usage"] +
            improvements.get("error_rate_improvement_percent", 0) * weights["error_rate"]
        )
        
        improvements["overall_performance_improvement_percent"] = overall_score
        
        return improvements
    
    def _analyze_performance_trend(self) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        if len(self.current_metrics) < 20:
            return {"status": "insufficient_data"}
        
        # Split metrics into two halves for trend analysis
        metrics_list = list(self.current_metrics)
        mid_point = len(metrics_list) // 2
        
        first_half = metrics_list[:mid_point]
        second_half = metrics_list[mid_point:]
        
        first_half_avg = statistics.mean([m.duration_ms for m in first_half])
        second_half_avg = statistics.mean([m.duration_ms for m in second_half])
        
        trend_direction = "improving" if second_half_avg < first_half_avg else "degrading"
        trend_magnitude = abs(second_half_avg - first_half_avg) / first_half_avg * 100
        
        return {
            "trend_direction": trend_direction,
            "trend_magnitude_percent": trend_magnitude,
            "first_half_avg_ms": first_half_avg,
            "second_half_avg_ms": second_half_avg
        }
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_session_performance_stats(self, session_id: int) -> Dict[str, Any]:
        """
        Get performance statistics for a specific session.
        
        Args:
            session_id: Session ID to analyze
            
        Returns:
            Dictionary containing session performance statistics
        """
        if session_id not in self.session_metrics:
            return {
                "session_id": session_id,
                "status": "no_data",
                "message": "No performance data available for this session"
            }
        
        session_data = self.session_metrics[session_id]
        
        # Calculate session statistics
        durations = [m.duration_ms for m in session_data]
        total_tokens_saved = sum(m.tokens_saved for m in session_data)
        optimizations_applied = sum(1 for m in session_data if m.optimization_applied)
        fallbacks_triggered = sum(1 for m in session_data if m.fallback_triggered)
        
        # Memory strategy usage
        strategy_usage = defaultdict(int)
        for metric in session_data:
            if metric.memory_strategy:
                strategy_usage[metric.memory_strategy] += 1
        
        return {
            "session_id": session_id,
            "total_operations": len(session_data),
            "avg_response_time_ms": statistics.mean(durations) if durations else 0,
            "median_response_time_ms": statistics.median(durations) if durations else 0,
            "total_tokens_saved": total_tokens_saved,
            "optimizations_applied": optimizations_applied,
            "fallbacks_triggered": fallbacks_triggered,
            "optimization_rate": optimizations_applied / len(session_data) if session_data else 0,
            "fallback_rate": fallbacks_triggered / len(session_data) if session_data else 0,
            "memory_strategy_usage": dict(strategy_usage),
            "first_operation": session_data[0].timestamp.isoformat() if session_data else None,
            "last_operation": session_data[-1].timestamp.isoformat() if session_data else None
        }
    
    def check_langchain_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check for LangChain components.
        
        Returns:
            Dictionary containing health status and diagnostics
        """
        self.last_health_check = datetime.utcnow()
        self.health_issues.clear()
        
        health_data = {
            "timestamp": self.last_health_check.isoformat(),
            "overall_status": "healthy",
            "components": {},
            "performance_indicators": {},
            "recommendations": []
        }
        
        try:
            # Check monitoring system health
            monitoring_stats = langchain_monitor.get_monitoring_stats()
            health_data["components"]["monitoring"] = self._check_monitoring_health(monitoring_stats)
            
            # Check performance metrics
            health_data["components"]["performance"] = self._check_performance_health()
            
            # Check system resources
            health_data["components"]["system_resources"] = self._check_system_resources()
            
            # Check error rates
            health_data["components"]["error_rates"] = self._check_error_rates(monitoring_stats)
            
            # Generate performance indicators
            health_data["performance_indicators"] = self._generate_performance_indicators()
            
            # Generate recommendations
            health_data["recommendations"] = self._generate_health_recommendations()
            
            # Determine overall health status
            component_statuses = [comp.get("status", "unknown") for comp in health_data["components"].values()]
            if "critical" in component_statuses:
                health_data["overall_status"] = "critical"
            elif "warning" in component_statuses:
                health_data["overall_status"] = "warning"
            elif "degraded" in component_statuses:
                health_data["overall_status"] = "degraded"
            
            self.health_status = health_data["overall_status"]
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            health_data["overall_status"] = "error"
            health_data["error"] = str(e)
        
        return health_data
    
    def _check_monitoring_health(self, monitoring_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check monitoring system health."""
        status = "healthy"
        issues = []
        
        # Check if monitoring is collecting data
        if monitoring_stats.get("completed_operations", 0) == 0:
            status = "warning"
            issues.append("No completed operations recorded")
        
        # Check for excessive active operations
        active_ops = monitoring_stats.get("active_operations", 0)
        if active_ops > 50:
            status = "warning"
            issues.append(f"High number of active operations: {active_ops}")
        
        return {
            "status": status,
            "active_operations": active_ops,
            "completed_operations": monitoring_stats.get("completed_operations", 0),
            "issues": issues
        }
    
    def _check_performance_health(self) -> Dict[str, Any]:
        """Check performance health indicators."""
        status = "healthy"
        issues = []
        
        if not self.current_metrics:
            return {
                "status": "warning",
                "issues": ["No performance data available"]
            }
        
        # Check recent performance
        recent_metrics = list(self.current_metrics)[-20:]  # Last 20 operations
        avg_duration = statistics.mean([m.duration_ms for m in recent_metrics])
        
        # Performance thresholds
        if avg_duration > 5000:  # 5 seconds
            status = "critical"
            issues.append(f"High average response time: {avg_duration:.2f}ms")
        elif avg_duration > 3000:  # 3 seconds
            status = "warning"
            issues.append(f"Elevated response time: {avg_duration:.2f}ms")
        
        # Check fallback rate
        fallback_rate = sum(1 for m in recent_metrics if m.fallback_triggered) / len(recent_metrics)
        if fallback_rate > 0.2:  # 20% fallback rate
            status = "warning"
            issues.append(f"High fallback rate: {fallback_rate:.1%}")
        
        return {
            "status": status,
            "avg_response_time_ms": avg_duration,
            "fallback_rate": fallback_rate,
            "sample_size": len(recent_metrics),
            "issues": issues
        }
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        status = "healthy"
        issues = []
        
        # Memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            status = "critical"
            issues.append(f"Critical memory usage: {memory.percent:.1f}%")
        elif memory.percent > 80:
            status = "warning"
            issues.append(f"High memory usage: {memory.percent:.1f}%")
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            status = "critical"
            issues.append(f"Critical CPU usage: {cpu_percent:.1f}%")
        elif cpu_percent > 80:
            status = "warning"
            issues.append(f"High CPU usage: {cpu_percent:.1f}%")
        
        return {
            "status": status,
            "memory_usage_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "cpu_usage_percent": cpu_percent,
            "issues": issues
        }
    
    def _check_error_rates(self, monitoring_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Check error rates and patterns."""
        status = "healthy"
        issues = []
        
        total_ops = sum(monitoring_stats.get("operation_counts", {}).values())
        total_errors = sum(monitoring_stats.get("error_counts", {}).values())
        
        if total_ops > 0:
            error_rate = total_errors / total_ops
            
            if error_rate > 0.1:  # 10% error rate
                status = "critical"
                issues.append(f"High error rate: {error_rate:.1%}")
            elif error_rate > 0.05:  # 5% error rate
                status = "warning"
                issues.append(f"Elevated error rate: {error_rate:.1%}")
        
        return {
            "status": status,
            "total_operations": total_ops,
            "total_errors": total_errors,
            "error_rate": total_errors / max(1, total_ops),
            "error_breakdown": monitoring_stats.get("error_counts", {}),
            "issues": issues
        }
    
    def _generate_performance_indicators(self) -> Dict[str, Any]:
        """Generate key performance indicators."""
        if not self.current_metrics:
            return {}
        
        recent_metrics = list(self.current_metrics)[-50:]  # Last 50 operations
        
        return {
            "avg_response_time_ms": statistics.mean([m.duration_ms for m in recent_metrics]),
            "total_tokens_saved": sum(m.tokens_saved for m in recent_metrics),
            "optimization_rate": sum(1 for m in recent_metrics if m.optimization_applied) / len(recent_metrics),
            "fallback_rate": sum(1 for m in recent_metrics if m.fallback_triggered) / len(recent_metrics),
            "avg_context_compression": statistics.mean([m.context_compression_ratio for m in recent_metrics if m.context_compression_ratio != 1.0]) or 1.0
        }
    
    def _generate_health_recommendations(self) -> List[str]:
        """Generate health and performance recommendations."""
        recommendations = []
        
        if not self.current_metrics:
            recommendations.append("Start using LangChain operations to collect performance data")
            return recommendations
        
        recent_metrics = list(self.current_metrics)[-20:]
        
        # Response time recommendations
        avg_duration = statistics.mean([m.duration_ms for m in recent_metrics])
        if avg_duration > 3000:
            recommendations.append("Consider optimizing context size or using more aggressive summarization")
        
        # Fallback rate recommendations
        fallback_rate = sum(1 for m in recent_metrics if m.fallback_triggered) / len(recent_metrics)
        if fallback_rate > 0.1:
            recommendations.append("High fallback rate detected - review memory strategy configuration")
        
        # Token usage recommendations
        total_tokens_saved = sum(m.tokens_saved for m in recent_metrics)
        if total_tokens_saved == 0:
            recommendations.append("No token savings detected - verify context optimization is enabled")
        
        # Memory strategy recommendations
        strategy_usage = defaultdict(int)
        for metric in recent_metrics:
            if metric.memory_strategy:
                strategy_usage[metric.memory_strategy] += 1
        
        if len(strategy_usage) == 1 and "fallback" in list(strategy_usage.keys())[0]:
            recommendations.append("Only fallback strategies being used - check primary memory strategy health")
        
        return recommendations
    
    def reset_performance_data(self) -> None:
        """Reset all performance tracking data."""
        self.current_metrics.clear()
        self.session_metrics.clear()
        self.total_operations = 0
        self.total_errors = 0
        self.total_tokens_saved = 0
        self.total_response_time = 0.0
        self.health_issues.clear()
        
        self.logger.info("Performance monitoring data reset")
    
    def export_performance_data(self, hours: int = 24) -> Dict[str, Any]:
        """
        Export performance data for analysis.
        
        Args:
            hours: Number of hours of data to export
            
        Returns:
            Dictionary containing exported performance data
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Filter metrics by time
        filtered_metrics = [
            m for m in self.current_metrics 
            if m.timestamp >= cutoff_time
        ]
        
        return {
            "export_timestamp": datetime.utcnow().isoformat(),
            "time_period_hours": hours,
            "total_operations": len(filtered_metrics),
            "metrics": [m.to_dict() for m in filtered_metrics],
            "summary": {
                "avg_response_time_ms": statistics.mean([m.duration_ms for m in filtered_metrics]) if filtered_metrics else 0,
                "total_tokens_saved": sum(m.tokens_saved for m in filtered_metrics),
                "optimization_rate": sum(1 for m in filtered_metrics if m.optimization_applied) / len(filtered_metrics) if filtered_metrics else 0,
                "fallback_rate": sum(1 for m in filtered_metrics if m.fallback_triggered) / len(filtered_metrics) if filtered_metrics else 0
            }
        }


# Global performance monitor instance
performance_monitor = PerformanceComparator()