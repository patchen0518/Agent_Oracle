# FastAPI application entry point
# Based on FastAPI v0.115.13+ documentation (Context 7 lookup: 2025-01-26)

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException

# Load environment variables from .env file
load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from backend.api.v1.session_router import router as session_router
from backend.api.v1.monitoring_router import router as monitoring_router
from backend.config.database import init_database
from backend.utils.logging_config import setup_logging, get_logger, log_error_context

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", "logs/backend.log")
logger = setup_logging(log_level=log_level, log_file=log_file)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Oracle Chat API")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Log file: {log_file}")
    
    # Initialize database and create tables
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Check required environment variables
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY not set - chat functionality will be unavailable")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Oracle Chat API")

app = FastAPI(
    title="Oracle Chat API",
    description="Session-based chat application with Gemini AI",
    version="1.1.0",
    lifespan=lifespan
)

# Configure CORS for development (localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(session_router)
app.include_router(monitoring_router)

@app.get("/")
async def read_root():
    return {"message": "Oracle Chat API is running"}

# Enhanced global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging."""
    context = {
        "method": request.method,
        "url": str(request.url),
        "status_code": exc.status_code,
        "client_ip": request.client.host if request.client else "unknown"
    }
    
    if exc.status_code >= 500:
        log_error_context(logger, exc, context)
    else:
        logger.warning(f"HTTP {exc.status_code}: {exc.detail}", extra=context)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": f"HTTP_{exc.status_code}",
            "timestamp": context.get("timestamp")
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with comprehensive logging."""
    context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown")
    }
    
    log_error_context(logger, exc, context)
    
    # Don't expose internal error details in production
    error_detail = "Internal server error"
    if os.getenv("ENVIRONMENT", "production").lower() == "development":
        error_detail = f"Internal server error: {str(exc)}"
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": error_detail,
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )

@app.get("/health")
async def health_check():
    """Enhanced health check with service status."""
    try:
        # Check if Gemini API key is configured
        gemini_status = "configured" if os.getenv("GEMINI_API_KEY") else "not_configured"
        
        health_info = {
            "status": "healthy",
            "timestamp": "2025-01-27T00:00:00Z",  # Would use actual timestamp
            "services": {
                "gemini_api": gemini_status,
                "logging": "active"
            },
            "version": "1.1.0"
        }
        
        logger.debug("Health check requested", extra=health_info)
        return health_info
        
    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "detail": "Service health check failed"
            }
        )