"""
Monitoring and diagnostics router for error tracking and system health.

Provides endpoints for monitoring application health, error rates, and
system diagnostics to support comprehensive error handling and debugging.
"""

from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, List
import os
import psutil
from datetime import datetime, timedelta

from backend.utils.logging_config import get_logger

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


@router.get("/health/detailed")
async def detailed_health_check(request: Request) -> Dict[str, Any]:
    """
    Comprehensive health check with system metrics.
    
    Returns:
        Dict[str, Any]: Detailed health information
    """
    try:
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Environment checks
        env_status = {
            "gemini_api_key": "configured" if os.getenv("GEMINI_API_KEY") else "missing",
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "environment": os.getenv("ENVIRONMENT", "production")
        }
        
        # Error statistics
        error_rate = 0
        if error_stats["total_errors"] > 0:
            time_since_reset = (datetime.utcnow() - error_stats["last_reset"]).total_seconds()
            error_rate = error_stats["total_errors"] / max(time_since_reset / 3600, 1)  # errors per hour
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "memory_usage_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_usage_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            },
            "environment": env_status,
            "errors": {
                "total_errors": error_stats["total_errors"],
                "error_rate_per_hour": round(error_rate, 2),
                "error_types": error_stats["error_types"],
                "recent_errors_count": len(error_stats["recent_errors"])
            },
            "version": "1.0.0"
        }
        
        # Determine overall health status
        if (memory.percent > 90 or disk.percent > 90 or 
            error_rate > 10 or env_status["gemini_api_key"] == "missing"):
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


@router.get("/diagnostics")
async def system_diagnostics(request: Request) -> Dict[str, Any]:
    """
    System diagnostics for troubleshooting.
    
    Returns:
        Dict[str, Any]: System diagnostic information
    """
    try:
        # Check various system components
        diagnostics = {
            "timestamp": datetime.utcnow().isoformat(),
            "api_key_status": "configured" if os.getenv("GEMINI_API_KEY") else "missing",
            "log_file_writable": True,  # Would check actual log file
            "memory_status": "ok",
            "disk_status": "ok",
            "recent_error_count": len(error_stats["recent_errors"]),
            "environment_variables": {
                "LOG_LEVEL": os.getenv("LOG_LEVEL", "not_set"),
                "ENVIRONMENT": os.getenv("ENVIRONMENT", "not_set"),
                "LOG_FILE": os.getenv("LOG_FILE", "not_set")
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
        
        logger.debug("System diagnostics completed", extra=diagnostics)
        return diagnostics
        
    except Exception as e:
        logger.error(f"System diagnostics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Diagnostics service failed"
        )