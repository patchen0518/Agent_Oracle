# FastAPI application entry point
# Based on FastAPI v0.115.13+ documentation (Context 7 lookup: 2025-01-26)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

@app.get("/")
async def read_root():
    return {"message": "Oracle Chat API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}