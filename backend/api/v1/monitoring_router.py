"""
Monitoring and diagnostics router for error tracking and system health.

Provides endpoints for monitoring application health, error rates, and
system diagnostics to support comprehensive error handling and debugging.
Includes session-based metrics and database connectivity monitoring.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Dict, Any, List
import os
import psutil
from datetime import datetime, timedelta
from sqlmodel import Session, select, func

from backend.utils.logging_config import get_logger
from backend.config.database import get_session, check_database_connection
from backend.models.session_models import Session as SessionModel, Message as MessageModel

# Create the router
router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

# Get logger instance
logger = get_logger("monitoring")

# Simple in-memory error tracking (in production, use proper monitoring)
error_stats = {
    "total_errors": 0,
    "error_types": {},
    "recent_errors": [],
    "last_reset": datetime.utcnow()
}

# Session analytics tracking
session_analytics = {
    "session_operations": 0,
    "message_operations": 0,
    "last_activity": datetime.utcnow(),
    "operation_times": []
}

def track_error(error_type: str, error_message: str, context: Dict[str, Any] = None):
    """Track error for monitoring purposes."""
    global error_stats
    
    error_stats["total_errors"] += 1
    
    if error_type not in error_stats["error_types"]:
        error_stats["error_types"][error_type] = 0
    error_stats["error_types"][error_type] += 1
    
    # Keep only last 100 errors
    error_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": error_type,
        "message": error_message,
        "context": context or {}
    }
    
    error_stats["recent_errors"].append(error_entry)
    if len(error_stats["recent_errors"]) > 100:
        error_stats["recent_errors"] = error_stats["recent_errors"][-100:]


def track_session_operation(operation_type: str, duration_ms: float = None):
    """Track session operation for analytics."""
    global session_analytics
    
    session_analytics["last_activity"] = datetime.utcnow()
    
    if operation_type in ["create_session", "delete_session", "update_session", "list_sessions", "get_session"]:
        session_analytics["session_operations"] += 1
    elif operation_type in ["send_message", "get_messages", "add_message"]:
        session_analytics["message_operations"] += 1
    
    if duration_ms is not None:
        operation_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation_type,
            "duration_ms": duration_ms
        }
        session_analytics["operation_times"].append(operation_entry)
        # Keep only last 100 operation times
        if len(session_analytics["operation_times"]) > 100:
            session_analytics["operation_times"] = session_analytics["operation_times"][-100:]


async def get_session_metrics(db: Session) -> Dict[str, Any]:
    """Get session-related metrics from the database."""
    try:
        # Total session count
        total_sessions = db.exec(select(func.count(SessionModel.id))).first() or 0
        
        # Total message count
        total_messages = db.exec(select(func.count(MessageModel.id))).first() or 0
        
        # Sessions created in last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_sessions = db.exec(
            select(func.count(SessionModel.id))
            .where(SessionModel.created_at >= yesterday)
        ).first() or 0
        
        # Messages sent in last 24 hours
        recent_messages = db.exec(
            select(func.count(MessageModel.id))
            .where(MessageModel.timestamp >= yesterday)
        ).first() or 0
        
        # Average messages per session
        avg_messages_per_session = 0
        if total_sessions > 0:
            avg_messages_per_session = round(total_messages / total_sessions, 2)
        
        # Most active session (by message count)
        most_active_session = db.exec(
            select(SessionModel.id, SessionModel.title, SessionModel.message_count)
            .order_by(SessionModel.message_count.desc())
            .limit(1)
        ).first()
        
        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "recent_sessions_24h": recent_sessions,
            "recent_messages_24h": recent_messages,
            "average_messages_per_session": avg_messages_per_session,
            "most_active_session": {
                "id": most_active_session[0] if most_active_session else None,
                "title": most_active_session[1] if most_active_session else None,
                "message_count": most_active_session[2] if most_active_session else 0
            } if most_active_session else None,
            "session_operations_count": session_analytics["session_operations"],
            "message_operations_count": session_analytics["message_operations"],
            "last_activity": session_analytics["last_activity"].isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get session metrics: {e}")
        return {
            "total_sessions": 0,
            "total_messages": 0,
            "recent_sessions_24h": 0,
            "recent_messages_24h": 0,
            "average_messages_per_session": 0,
            "most_active_session": None,
            "session_operations_count": session_analytics["session_operations"],
            "message_operations_count": session_analytics["message_operations"],
            "last_activity": session_analytics["last_activity"].isoformat(),
            "error": str(e)
        }


@router.get("/health/detailed")
async def detailed_health_check(request: Request, db: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    Comprehensive health check with system metrics and session analytics.
    
    Returns:
        Dict[str, Any]: Detailed health information including session metrics
    """
    try:
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Database connectivity check
        db_healthy = check_database_connection()
        
        # Environment checks
        env_status = {
            "gemini_api_key": "configured" if os.getenv("GEMINI_API_KEY") else "missing",
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "environment": os.getenv("ENVIRONMENT", "production"),
            "database_url": os.getenv("DATABASE_URL", "sqlite:///./oracle_sessions.db")
        }
        
        # Error statistics
        error_rate = 0
        if error_stats["total_errors"] > 0:
            time_since_reset = (datetime.utcnow() - error_stats["last_reset"]).total_seconds()
            error_rate = error_stats["total_errors"] / max(time_since_reset / 3600, 1)  # errors per hour
        
        # Session metrics (only if database is healthy)
        session_metrics = {}
        if db_healthy:
            try:
                session_metrics = await get_session_metrics(db)
            except Exception as e:
                logger.warning(f"Failed to get session metrics: {e}")
                session_metrics = {"error": "Failed to retrieve session metrics"}
        else:
            session_metrics = {"error": "Database connection unavailable"}
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "memory_usage_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_usage_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            },
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "connection_test": "passed" if db_healthy else "failed"
            },
            "environment": env_status,
            "errors": {
                "total_errors": error_stats["total_errors"],
                "error_rate_per_hour": round(error_rate, 2),
                "error_types": error_stats["error_types"],
                "recent_errors_count": len(error_stats["recent_errors"])
            },
            "sessions": session_metrics,
            "version": "1.1.0"
        }
        
        # Determine overall health status
        if (memory.percent > 90 or disk.percent > 90 or 
            error_rate > 10 or env_status["gemini_api_key"] == "missing" or
            not db_healthy):
            health_data["status"] = "degraded"
        
        logger.debug("Detailed health check completed", extra=health_data)
        return health_data
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Health check service unavailable"
        )


@router.get("/errors/recent")
async def get_recent_errors(
    request: Request,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get recent error information for debugging.
    
    Args:
        limit: Maximum number of recent errors to return
        
    Returns:
        Dict[str, Any]: Recent error information
    """
    try:
        recent_errors = error_stats["recent_errors"][-limit:] if error_stats["recent_errors"] else []
        
        return {
            "total_errors": error_stats["total_errors"],
            "recent_errors": recent_errors,
            "error_types": error_stats["error_types"],
            "last_reset": error_stats["last_reset"].isoformat(),
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve recent errors: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieval failed"
        )


@router.get("/sessions/usage")
async def session_usage_tracking(
    request: Request, 
    db: Session = Depends(get_session),
    days: int = 7
) -> Dict[str, Any]:
    """
    Get session usage tracking and activity patterns over specified time period.
    
    Args:
        days: Number of days to analyze (default: 7, max: 30)
        
    Returns:
        Dict[str, Any]: Session usage patterns and activity metrics
    """
    try:
        # Validate days parameter
        if days < 1 or days > 30:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 30")
        
        # Database connectivity check
        db_healthy = check_database_connection()
        if not db_healthy:
            raise HTTPException(
                status_code=503,
                detail="Database connection unavailable for usage tracking"
            )
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Session creation patterns
        sessions_by_day = {}
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            daily_sessions = db.exec(
                select(func.count(SessionModel.id))
                .where(SessionModel.created_at >= day_start)
                .where(SessionModel.created_at < day_end)
            ).first() or 0
            
            sessions_by_day[day_start.strftime("%Y-%m-%d")] = daily_sessions
        
        # Message activity patterns
        messages_by_day = {}
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            daily_messages = db.exec(
                select(func.count(MessageModel.id))
                .where(MessageModel.timestamp >= day_start)
                .where(MessageModel.timestamp < day_end)
            ).first() or 0
            
            messages_by_day[day_start.strftime("%Y-%m-%d")] = daily_messages
        
        # Session activity levels
        active_sessions = db.exec(
            select(func.count(SessionModel.id))
            .where(SessionModel.updated_at >= start_date)
        ).first() or 0
        
        # Top sessions by activity
        top_sessions = db.exec(
            select(SessionModel.id, SessionModel.title, SessionModel.message_count, SessionModel.updated_at)
            .where(SessionModel.updated_at >= start_date)
            .order_by(SessionModel.message_count.desc())
            .limit(10)
        ).all()
        
        usage_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "session_creation_patterns": sessions_by_day,
            "message_activity_patterns": messages_by_day,
            "activity_summary": {
                "active_sessions_in_period": active_sessions,
                "total_sessions_created": sum(sessions_by_day.values()),
                "total_messages_sent": sum(messages_by_day.values()),
                "average_sessions_per_day": round(sum(sessions_by_day.values()) / days, 2),
                "average_messages_per_day": round(sum(messages_by_day.values()) / days, 2)
            },
            "top_active_sessions": [
                {
                    "id": session[0],
                    "title": session[1],
                    "message_count": session[2],
                    "last_activity": session[3].isoformat()
                }
                for session in top_sessions
            ]
        }
        
        logger.debug(f"Session usage tracking completed for {days} days", extra=usage_data)
        return usage_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session usage tracking failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Session usage tracking service failed"
        )


@router.get("/sessions/performance")
async def session_performance_metrics(request: Request, db: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    Get session operation performance metrics and optimization insights.
    
    Returns:
        Dict[str, Any]: Performance metrics for session operations
    """
    try:
        # Database connectivity check
        db_healthy = check_database_connection()
        if not db_healthy:
            raise HTTPException(
                status_code=503,
                detail="Database connection unavailable for performance metrics"
            )
        
        # Calculate performance metrics from tracked operations
        performance_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "database_status": "healthy",
            "operation_metrics": {},
            "optimization_insights": []
        }
        
        # Analyze operation performance
        if session_analytics["operation_times"]:
            operations_by_type = {}
            for op in session_analytics["operation_times"]:
                op_type = op["operation"]
                if op_type not in operations_by_type:
                    operations_by_type[op_type] = []
                operations_by_type[op_type].append(op["duration_ms"])
            
            for op_type, durations in operations_by_type.items():
                avg_duration = sum(durations) / len(durations)
                performance_data["operation_metrics"][op_type] = {
                    "total_operations": len(durations),
                    "average_duration_ms": round(avg_duration, 2),
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations),
                    "median_duration_ms": round(sorted(durations)[len(durations)//2], 2)
                }
                
                # Generate optimization insights
                if avg_duration > 1000:  # Operations taking more than 1 second
                    performance_data["optimization_insights"].append(
                        f"{op_type} operations are averaging {avg_duration:.0f}ms - consider optimization"
                    )
                elif avg_duration > 500:  # Operations taking more than 500ms
                    performance_data["optimization_insights"].append(
                        f"{op_type} operations are taking {avg_duration:.0f}ms - monitor for performance"
                    )
        
        # Database query performance test
        start_time = datetime.utcnow()
        session_count = db.exec(select(func.count(SessionModel.id))).first()
        query_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        performance_data["database_performance"] = {
            "session_count_query_ms": round(query_duration, 2),
            "total_sessions": session_count or 0
        }
        
        # Overall performance assessment
        if not performance_data["optimization_insights"]:
            performance_data["optimization_insights"].append("All operations performing within acceptable ranges")
        
        logger.debug("Session performance metrics completed", extra=performance_data)
        return performance_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session performance metrics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Session performance metrics service failed"
        )


@router.post("/errors/reset")
async def reset_error_stats(request: Request) -> Dict[str, str]:
    """
    Reset error statistics (for development/testing).
    
    Returns:
        Dict[str, str]: Reset confirmation
    """
    global error_stats
    
    try:
        error_stats = {
            "total_errors": 0,
            "error_types": {},
            "recent_errors": [],
            "last_reset": datetime.utcnow()
        }
        
        logger.info("Error statistics reset")
        
        return {
            "status": "success",
            "message": "Error statistics have been reset",
            "reset_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to reset error stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error reset failed"
        )


@router.post("/sessions/analytics/reset")
async def reset_session_analytics(request: Request) -> Dict[str, str]:
    """
    Reset session analytics tracking (for development/testing).
    
    Returns:
        Dict[str, str]: Reset confirmation
    """
    global session_analytics
    
    try:
        session_analytics = {
            "session_operations": 0,
            "message_operations": 0,
            "last_activity": datetime.utcnow(),
            "operation_times": []
        }
        
        logger.info("Session analytics reset")
        
        return {
            "status": "success",
            "message": "Session analytics have been reset",
            "reset_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to reset session analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Session analytics reset failed"
        )


@router.get("/sessions/analytics")
async def session_analytics_endpoint(request: Request, db: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    Get detailed session analytics and usage tracking.
    
    Returns:
        Dict[str, Any]: Session analytics and usage statistics
    """
    try:
        # Database connectivity check
        db_healthy = check_database_connection()
        
        if not db_healthy:
            raise HTTPException(
                status_code=503,
                detail="Database connection unavailable for analytics"
            )
        
        # Get comprehensive session metrics
        session_metrics = await get_session_metrics(db)
        
        # Calculate operation performance metrics
        operation_performance = {}
        if session_analytics["operation_times"]:
            operations_by_type = {}
            for op in session_analytics["operation_times"]:
                op_type = op["operation"]
                if op_type not in operations_by_type:
                    operations_by_type[op_type] = []
                operations_by_type[op_type].append(op["duration_ms"])
            
            for op_type, durations in operations_by_type.items():
                operation_performance[op_type] = {
                    "count": len(durations),
                    "avg_duration_ms": round(sum(durations) / len(durations), 2),
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations)
                }
        
        analytics_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "database_status": "healthy",
            "session_metrics": session_metrics,
            "operation_performance": operation_performance,
            "activity_summary": {
                "total_session_operations": session_analytics["session_operations"],
                "total_message_operations": session_analytics["message_operations"],
                "last_activity": session_analytics["last_activity"].isoformat(),
                "operations_tracked": len(session_analytics["operation_times"])
            }
        }
        
        logger.debug("Session analytics retrieved", extra=analytics_data)
        return analytics_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session analytics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Session analytics service failed"
        )


@router.get("/diagnostics")
async def system_diagnostics(request: Request, db: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    System diagnostics for troubleshooting including session operations.
    
    Returns:
        Dict[str, Any]: System diagnostic information
    """
    try:
        # Database connectivity check
        db_healthy = check_database_connection()
        
        # Check various system components
        diagnostics = {
            "timestamp": datetime.utcnow().isoformat(),
            "api_key_status": "configured" if os.getenv("GEMINI_API_KEY") else "missing",
            "log_file_writable": True,  # Would check actual log file
            "memory_status": "ok",
            "disk_status": "ok",
            "database_status": "healthy" if db_healthy else "unhealthy",
            "recent_error_count": len(error_stats["recent_errors"]),
            "session_operations_health": "ok",
            "environment_variables": {
                "LOG_LEVEL": os.getenv("LOG_LEVEL", "not_set"),
                "ENVIRONMENT": os.getenv("ENVIRONMENT", "not_set"),
                "LOG_FILE": os.getenv("LOG_FILE", "not_set"),
                "DATABASE_URL": os.getenv("DATABASE_URL", "not_set")
            }
        }
        
        # Check memory status
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            diagnostics["memory_status"] = "critical"
        elif memory.percent > 75:
            diagnostics["memory_status"] = "warning"
        
        # Check disk status
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            diagnostics["disk_status"] = "critical"
        elif disk.percent > 80:
            diagnostics["disk_status"] = "warning"
        
        # Check session operations health
        if db_healthy:
            try:
                # Test basic session query
                session_count = db.exec(select(func.count(SessionModel.id))).first()
                if session_count is not None:
                    diagnostics["session_operations_health"] = "ok"
                    diagnostics["session_count_test"] = session_count
                else:
                    diagnostics["session_operations_health"] = "warning"
                    diagnostics["session_count_test"] = "query_returned_none"
            except Exception as e:
                diagnostics["session_operations_health"] = "error"
                diagnostics["session_operations_error"] = str(e)
        else:
            diagnostics["session_operations_health"] = "unavailable"
        
        logger.debug("System diagnostics completed", extra=diagnostics)
        return diagnostics
        
    except Exception as e:
        logger.error(f"System diagnostics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Diagnostics service failed"
        )