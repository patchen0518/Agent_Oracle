"""
LangChain monitoring dashboard service.

Provides dashboard data aggregation, real-time monitoring capabilities,
and alert management for LangChain integration metrics.
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import statistics

from backend.utils.logging_config import get_logger
from backend.services.langchain_monitoring import langchain_monitor
from backend.services.langchain_performance_monitor import performance_monitor


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DashboardAlert:
    """Dashboard alert information."""
    id: str
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    component: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


class LangChainDashboard:
    """
    LangChain monitoring dashboard service.
    
    Aggregates metrics, generates dashboard data, and manages alerts
    for comprehensive LangChain integration monitoring.
    """
    
    def __init__(self):
        """Initialize the dashboard service."""
        self.logger = get_logger("langchain_dashboard")
        
        # Alert management
        self.active_alerts: List[DashboardAlert] = []
        self.alert_history: List[DashboardAlert] = []
        self.max_alert_history = 500
        
        # Alert thresholds
        self.alert_thresholds = {
            "response_time_ms": {"warning": 3000, "critical": 5000},
            "error_rate": {"warning": 0.05, "critical": 0.1},
            "fallback_rate": {"warning": 0.1, "critical": 0.2},
            "memory_usage_percent": {"warning": 80, "critical": 90},
            "cpu_usage_percent": {"warning": 80, "critical": 90}
        }
        
        # Dashboard refresh tracking
        self.last_refresh = datetime.utcnow()
        self.refresh_count = 0
        
        self.logger.info("LangChain dashboard service initialized")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for LangChain monitoring.
        
        Returns:
            Dictionary containing all dashboard metrics and visualizations
        """
        try:
            self.last_refresh = datetime.utcnow()
            self.refresh_count += 1
            
            # Get core metrics
            monitoring_stats = langchain_monitor.get_monitoring_stats()
            performance_data = performance_monitor.get_performance_comparison()
            health_data = performance_monitor.check_langchain_health()
            
            # Process alerts
            self._process_alerts(monitoring_stats, performance_data, health_data)
            
            # Build dashboard data
            dashboard_data = {
                "timestamp": self.last_refresh.isoformat(),
                "refresh_count": self.refresh_count,
                "overview": self._build_overview_metrics(monitoring_stats, performance_data),
                "performance": self._build_performance_metrics(performance_data),
                "operations": self._build_operations_metrics(monitoring_stats),
                "health": self._build_health_metrics(health_data),
                "alerts": self._build_alerts_data(),
                "charts": self._build_chart_data(monitoring_stats, performance_data),
                "recommendations": self._build_recommendations(health_data)
            }
            
            self.logger.debug("Dashboard data generated successfully")
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate dashboard data: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "status": "error"
            }
    
    def _build_overview_metrics(
        self, 
        monitoring_stats: Dict[str, Any], 
        performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build overview metrics for dashboard."""
        token_stats = monitoring_stats.get("token_statistics", {})
        improvements = performance_data.get("improvements", {})
        
        return {
            "total_operations": sum(monitoring_stats.get("operation_counts", {}).values()),
            "active_operations": monitoring_stats.get("active_operations", 0),
            "total_tokens_saved": token_stats.get("total_tokens_saved", 0),
            "total_fallbacks": token_stats.get("total_fallbacks_triggered", 0),
            "overall_improvement_percent": improvements.get("overall_performance_improvement_percent", 0),
            "system_health": self._determine_system_health(),
            "uptime_hours": self._calculate_uptime_hours()
        }
    
    def _build_performance_metrics(self, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build performance metrics for dashboard."""
        current_metrics = performance_data.get("current_metrics", {})
        improvements = performance_data.get("improvements", {})
        trend = performance_data.get("performance_trend", {})
        
        return {
            "response_time": {
                "current_avg_ms": current_metrics.get("avg_response_time_ms", 0),
                "median_ms": current_metrics.get("median_response_time_ms", 0),
                "p95_ms": current_metrics.get("p95_response_time_ms", 0),
                "improvement_percent": improvements.get("response_time_improvement_percent", 0)
            },
            "token_usage": {
                "avg_tokens_per_request": current_metrics.get("avg_tokens_per_request", 0),
                "total_tokens_saved": current_metrics.get("total_tokens_saved", 0),
                "improvement_percent": improvements.get("token_usage_improvement_percent", 0)
            },
            "memory_efficiency": {
                "avg_memory_usage_mb": current_metrics.get("avg_memory_usage_mb", 0),
                "improvement_percent": improvements.get("memory_usage_improvement_percent", 0)
            },
            "trend": {
                "direction": trend.get("trend_direction", "stable"),
                "magnitude_percent": trend.get("trend_magnitude_percent", 0)
            }
        }
    
    def _build_operations_metrics(self, monitoring_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Build operations metrics for dashboard."""
        operation_counts = monitoring_stats.get("operation_counts", {})
        error_counts = monitoring_stats.get("error_counts", {})
        performance_stats = monitoring_stats.get("performance_stats", {})
        
        # Calculate success rates
        success_rates = {}
        for op_type, count in operation_counts.items():
            error_count = sum(
                error_count for error_key, error_count in error_counts.items()
                if error_key.startswith(op_type)
            )
            success_rates[op_type] = (count - error_count) / max(1, count) * 100
        
        return {
            "operation_counts": operation_counts,
            "success_rates": success_rates,
            "performance_breakdown": performance_stats,
            "most_frequent_operation": max(operation_counts.items(), key=lambda x: x[1])[0] if operation_counts else None,
            "error_summary": {
                "total_errors": sum(error_counts.values()),
                "error_types": len(error_counts),
                "most_common_error": max(error_counts.items(), key=lambda x: x[1])[0] if error_counts else None
            }
        }
    
    def _build_health_metrics(self, health_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build health metrics for dashboard."""
        components = health_data.get("components", {})
        performance_indicators = health_data.get("performance_indicators", {})
        
        # Count component statuses
        status_counts = {"healthy": 0, "warning": 0, "critical": 0, "degraded": 0}
        for component_data in components.values():
            status = component_data.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
        
        return {
            "overall_status": health_data.get("overall_status", "unknown"),
            "component_status_counts": status_counts,
            "component_details": components,
            "performance_indicators": performance_indicators,
            "health_score": self._calculate_health_score(components)
        }
    
    def _build_alerts_data(self) -> Dict[str, Any]:
        """Build alerts data for dashboard."""
        # Count alerts by severity
        severity_counts = {"info": 0, "warning": 0, "critical": 0}
        for alert in self.active_alerts:
            if not alert.resolved:
                severity_counts[alert.severity.value] += 1
        
        # Get recent alerts
        recent_alerts = sorted(
            [alert for alert in self.active_alerts if not alert.resolved],
            key=lambda x: x.timestamp,
            reverse=True
        )[:10]
        
        return {
            "active_count": len([a for a in self.active_alerts if not a.resolved]),
            "severity_counts": severity_counts,
            "recent_alerts": [alert.to_dict() for alert in recent_alerts],
            "total_alerts_today": len([
                a for a in self.alert_history 
                if a.timestamp.date() == datetime.utcnow().date()
            ])
        }
    
    def _build_chart_data(
        self, 
        monitoring_stats: Dict[str, Any], 
        performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build chart data for dashboard visualizations."""
        recent_operations = monitoring_stats.get("recent_operations", [])
        
        # Time series data for response times
        response_time_series = []
        token_savings_series = []
        operation_counts_series = {}
        
        # Process recent operations for time series
        for op in recent_operations[-50:]:  # Last 50 operations
            timestamp = op.get("timestamp", "")
            
            # Response time series
            if op.get("duration_ms"):
                response_time_series.append({
                    "timestamp": timestamp,
                    "value": op["duration_ms"]
                })
            
            # Token savings series
            if op.get("tokens_saved", 0) > 0:
                token_savings_series.append({
                    "timestamp": timestamp,
                    "value": op["tokens_saved"]
                })
            
            # Operation counts by type
            op_type = op.get("operation_type", "unknown")
            if op_type not in operation_counts_series:
                operation_counts_series[op_type] = []
            operation_counts_series[op_type].append({
                "timestamp": timestamp,
                "count": 1
            })
        
        return {
            "response_times": response_time_series,
            "token_savings": token_savings_series,
            "operation_counts": operation_counts_series,
            "performance_trend": self._build_performance_trend_data(recent_operations)
        }
    
    def _build_performance_trend_data(self, recent_operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build performance trend data for charts."""
        if len(recent_operations) < 10:
            return []
        
        # Group operations by time windows (e.g., 5-minute intervals)
        time_windows = {}
        
        for op in recent_operations:
            timestamp_str = op.get("timestamp", "")
            if not timestamp_str:
                continue
            
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                # Round to 5-minute intervals
                window = timestamp.replace(minute=(timestamp.minute // 5) * 5, second=0, microsecond=0)
                window_key = window.isoformat()
                
                if window_key not in time_windows:
                    time_windows[window_key] = {
                        "timestamp": window_key,
                        "operations": [],
                        "total_duration": 0,
                        "total_tokens_saved": 0
                    }
                
                time_windows[window_key]["operations"].append(op)
                time_windows[window_key]["total_duration"] += op.get("duration_ms", 0)
                time_windows[window_key]["total_tokens_saved"] += op.get("tokens_saved", 0)
                
            except (ValueError, TypeError):
                continue
        
        # Calculate averages for each window
        trend_data = []
        for window_data in sorted(time_windows.values(), key=lambda x: x["timestamp"]):
            op_count = len(window_data["operations"])
            if op_count > 0:
                trend_data.append({
                    "timestamp": window_data["timestamp"],
                    "avg_response_time": window_data["total_duration"] / op_count,
                    "total_tokens_saved": window_data["total_tokens_saved"],
                    "operation_count": op_count
                })
        
        return trend_data
    
    def _build_recommendations(self, health_data: Dict[str, Any]) -> List[str]:
        """Build recommendations based on current metrics."""
        recommendations = health_data.get("recommendations", [])
        
        # Add dashboard-specific recommendations
        if len(self.active_alerts) > 10:
            recommendations.append("High number of active alerts - review system configuration")
        
        if self._determine_system_health() == "degraded":
            recommendations.append("System health is degraded - check component status and performance metrics")
        
        return recommendations
    
    def _process_alerts(
        self, 
        monitoring_stats: Dict[str, Any], 
        performance_data: Dict[str, Any], 
        health_data: Dict[str, Any]
    ) -> None:
        """Process and generate alerts based on current metrics."""
        current_time = datetime.utcnow()
        
        # Check response time alerts
        current_metrics = performance_data.get("current_metrics", {})
        avg_response_time = current_metrics.get("avg_response_time_ms", 0)
        
        if avg_response_time > self.alert_thresholds["response_time_ms"]["critical"]:
            self._create_alert(
                "response_time_critical",
                AlertSeverity.CRITICAL,
                "Critical Response Time",
                f"Average response time is {avg_response_time:.0f}ms (threshold: {self.alert_thresholds['response_time_ms']['critical']}ms)",
                "performance",
                avg_response_time,
                self.alert_thresholds["response_time_ms"]["critical"]
            )
        elif avg_response_time > self.alert_thresholds["response_time_ms"]["warning"]:
            self._create_alert(
                "response_time_warning",
                AlertSeverity.WARNING,
                "High Response Time",
                f"Average response time is {avg_response_time:.0f}ms (threshold: {self.alert_thresholds['response_time_ms']['warning']}ms)",
                "performance",
                avg_response_time,
                self.alert_thresholds["response_time_ms"]["warning"]
            )
        
        # Check error rate alerts
        total_ops = sum(monitoring_stats.get("operation_counts", {}).values())
        total_errors = sum(monitoring_stats.get("error_counts", {}).values())
        error_rate = total_errors / max(1, total_ops)
        
        if error_rate > self.alert_thresholds["error_rate"]["critical"]:
            self._create_alert(
                "error_rate_critical",
                AlertSeverity.CRITICAL,
                "Critical Error Rate",
                f"Error rate is {error_rate:.1%} (threshold: {self.alert_thresholds['error_rate']['critical']:.1%})",
                "operations",
                error_rate,
                self.alert_thresholds["error_rate"]["critical"]
            )
        elif error_rate > self.alert_thresholds["error_rate"]["warning"]:
            self._create_alert(
                "error_rate_warning",
                AlertSeverity.WARNING,
                "High Error Rate",
                f"Error rate is {error_rate:.1%} (threshold: {self.alert_thresholds['error_rate']['warning']:.1%})",
                "operations",
                error_rate,
                self.alert_thresholds["error_rate"]["warning"]
            )
        
        # Check system health alerts
        overall_status = health_data.get("overall_status", "unknown")
        if overall_status == "critical":
            self._create_alert(
                "system_health_critical",
                AlertSeverity.CRITICAL,
                "Critical System Health",
                "System health status is critical - immediate attention required",
                "system"
            )
        elif overall_status == "degraded":
            self._create_alert(
                "system_health_degraded",
                AlertSeverity.WARNING,
                "Degraded System Health",
                "System health status is degraded - monitoring recommended",
                "system"
            )
        
        # Clean up old alerts (auto-resolve after 1 hour)
        self._cleanup_old_alerts()
    
    def _create_alert(
        self, 
        alert_id: str, 
        severity: AlertSeverity, 
        title: str, 
        message: str, 
        component: str,
        metric_value: Optional[float] = None,
        threshold: Optional[float] = None
    ) -> None:
        """Create or update an alert."""
        # Check if alert already exists
        existing_alert = next((a for a in self.active_alerts if a.id == alert_id and not a.resolved), None)
        
        if existing_alert:
            # Update existing alert
            existing_alert.timestamp = datetime.utcnow()
            existing_alert.message = message
            existing_alert.metric_value = metric_value
        else:
            # Create new alert
            alert = DashboardAlert(
                id=alert_id,
                severity=severity,
                title=title,
                message=message,
                timestamp=datetime.utcnow(),
                component=component,
                metric_value=metric_value,
                threshold=threshold
            )
            
            self.active_alerts.append(alert)
            self.logger.warning(f"Alert created: {title} - {message}")
    
    def _cleanup_old_alerts(self) -> None:
        """Clean up old alerts and move to history."""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=1)
        
        # Move old alerts to history
        for alert in self.active_alerts[:]:
            if alert.timestamp < cutoff_time:
                alert.resolved = True
                self.alert_history.append(alert)
                self.active_alerts.remove(alert)
        
        # Maintain history size limit
        if len(self.alert_history) > self.max_alert_history:
            self.alert_history = self.alert_history[-self.max_alert_history:]
    
    def _determine_system_health(self) -> str:
        """Determine overall system health status."""
        critical_alerts = [a for a in self.active_alerts if a.severity == AlertSeverity.CRITICAL and not a.resolved]
        warning_alerts = [a for a in self.active_alerts if a.severity == AlertSeverity.WARNING and not a.resolved]
        
        if critical_alerts:
            return "critical"
        elif warning_alerts:
            return "degraded"
        else:
            return "healthy"
    
    def _calculate_uptime_hours(self) -> float:
        """Calculate system uptime in hours (simplified)."""
        # This is a simplified calculation - in a real system, you'd track actual uptime
        return (datetime.utcnow() - datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() / 3600
    
    def _calculate_health_score(self, components: Dict[str, Any]) -> float:
        """Calculate overall health score (0-100)."""
        if not components:
            return 100.0
        
        status_scores = {"healthy": 100, "warning": 70, "degraded": 50, "critical": 20, "error": 0}
        
        total_score = 0
        component_count = 0
        
        for component_data in components.values():
            status = component_data.get("status", "unknown")
            score = status_scores.get(status, 50)  # Default to 50 for unknown
            total_score += score
            component_count += 1
        
        return total_score / max(1, component_count)
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Get real-time metrics for dashboard updates.
        
        Returns:
            Dictionary containing current real-time metrics
        """
        try:
            monitoring_stats = langchain_monitor.get_monitoring_stats()
            
            # Get latest operations
            recent_ops = monitoring_stats.get("recent_operations", [])[-10:]
            
            # Calculate current rates
            current_time = datetime.utcnow()
            one_minute_ago = current_time - timedelta(minutes=1)
            
            recent_minute_ops = []
            for op in recent_ops:
                try:
                    op_time = datetime.fromisoformat(op.get("timestamp", "").replace('Z', '+00:00'))
                    if op_time >= one_minute_ago:
                        recent_minute_ops.append(op)
                except (ValueError, TypeError):
                    continue
            
            return {
                "timestamp": current_time.isoformat(),
                "active_operations": monitoring_stats.get("active_operations", 0),
                "operations_per_minute": len(recent_minute_ops),
                "latest_operations": recent_ops,
                "system_health": self._determine_system_health(),
                "active_alerts_count": len([a for a in self.active_alerts if not a.resolved]),
                "total_tokens_saved": monitoring_stats.get("token_statistics", {}).get("total_tokens_saved", 0)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get real-time metrics: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Manually resolve an alert.
        
        Args:
            alert_id: ID of the alert to resolve
            
        Returns:
            True if alert was found and resolved
        """
        for alert in self.active_alerts:
            if alert.id == alert_id and not alert.resolved:
                alert.resolved = True
                self.alert_history.append(alert)
                self.active_alerts.remove(alert)
                self.logger.info(f"Alert resolved manually: {alert_id}")
                return True
        
        return False
    
    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get alert history for the specified time period.
        
        Args:
            hours: Number of hours of history to retrieve
            
        Returns:
            List of alert dictionaries
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Combine active and historical alerts
        all_alerts = self.active_alerts + self.alert_history
        
        # Filter by time period
        filtered_alerts = [
            alert for alert in all_alerts 
            if alert.timestamp >= cutoff_time
        ]
        
        # Sort by timestamp (newest first)
        filtered_alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [alert.to_dict() for alert in filtered_alerts]
    
    def update_alert_thresholds(self, thresholds: Dict[str, Dict[str, float]]) -> None:
        """
        Update alert thresholds.
        
        Args:
            thresholds: Dictionary of threshold configurations
        """
        for metric, levels in thresholds.items():
            if metric in self.alert_thresholds:
                self.alert_thresholds[metric].update(levels)
        
        self.logger.info(f"Alert thresholds updated: {thresholds}")


# Global dashboard instance
langchain_dashboard = LangChainDashboard()