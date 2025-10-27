# FastAPI application entry point
# Based on FastAPI v0.115.13+ documentation (Context 7 lookup: 2025-01-26)

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from backend.api.v1.chat_router import router as chat_router

app = FastAPI(
    title="Oracle Chat API",
    description="Single-session chat application with Gemini AI",
    version="1.0.0"
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
app.include_router(chat_router)

@app.get("/")
async def read_root():
    return {"message": "Oracle Chat API is running"}

# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}