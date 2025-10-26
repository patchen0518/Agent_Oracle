# Oracle Project Structure

This document describes the project structure created for the Oracle single-session chat application.

## Directory Structure

```
agent-oracle/
├── backend/                    # FastAPI backend application
│   ├── api/                   # API routes and endpoints
│   │   ├── v1/               # API version 1
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── models/               # Pydantic data models
│   │   └── __init__.py
│   ├── services/             # Business logic and external integrations
│   │   └── __init__.py
│   ├── tests/                # Backend tests
│   │   └── __init__.py
│   ├── main.py              # FastAPI application entry point
│   └── .env.example         # Environment variables template
├── frontend/                  # React frontend application
│   ├── src/
│   │   ├── components/       # React components
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── MessageInput.jsx
│   │   │   └── Message.jsx
│   │   ├── services/         # API communication
│   │   │   └── api.js
│   │   ├── test/            # Test setup
│   │   │   └── setup.js
│   │   ├── App.jsx          # Main App component
│   │   └── main.jsx         # React entry point
│   ├── package.json         # Node.js dependencies and scripts
│   ├── vite.config.js       # Vite configuration
│   ├── .env                 # Environment variables (development)
│   └── .env.example         # Environment variables template
├── pyproject.toml           # Python project configuration
├── .gitignore              # Git ignore patterns
└── README.md               # Project documentation
```

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **uvicorn**: ASGI server for FastAPI
- **google-genai**: Google Generative AI SDK (latest unified SDK)
- **python-dotenv**: Environment variable management
- **pydantic**: Data validation and serialization

### Frontend
- **React 19+**: Modern React with latest features
- **Vite**: Fast build tool and development server
- **axios**: HTTP client for API communication
- **Vitest**: Testing framework
- **React Testing Library**: Component testing utilities

## Development Setup

### Backend Setup
```bash
# Install dependencies using uv
uv pip install -e .

# Copy environment template and configure
cp backend/.env.example backend/.env
# Edit backend/.env with your Gemini API key

# Run development server
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev
```

## Environment Configuration

### Backend (.env)
```ini
GEMINI_API_KEY=your_gemini_api_key_here
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
LOG_LEVEL=info
```

### Frontend (.env)
```ini
VITE_API_BASE_URL=http://localhost:8000
```

## API Documentation

When the backend is running, FastAPI automatically generates interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

### Backend Tests
```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=backend
```

### Frontend Tests
```bash
cd frontend

# Run tests once
npm test

# Run tests in watch mode
npm run test:watch
```

## Key Features Implemented

1. **Project Structure**: Organized backend and frontend with clear separation of concerns
2. **Environment Configuration**: Secure API key management with .env files
3. **CORS Setup**: Configured for local development (localhost:5173)
4. **Testing Framework**: Set up for both backend (pytest) and frontend (vitest)
5. **API Client**: Axios-based service with interceptors for error handling
6. **Health Checks**: Backend health endpoint and frontend status monitoring

## Next Steps

This structure provides the foundation for implementing the chat functionality. The next tasks will involve:
1. Creating Pydantic models for chat requests/responses
2. Implementing Gemini API integration
3. Building the chat API endpoints
4. Developing the React chat interface components
5. Adding comprehensive tests

## Documentation References

This structure was created based on:
- FastAPI v0.115.13+ documentation (Context 7 lookup: 2025-01-26)
- React v19+ documentation (Context 7 lookup: 2025-01-26)
- Vite v7+ documentation (Context 7 lookup: 2025-01-26)
- Google Gen AI Python SDK v1.33.0+ documentation (Context 7 lookup: 2025-01-26)