# Oracle: An Intelligent Conversational AI Agent

![Project Status: MVP 1.0 Complete](https://img.shields.io/badge/status-MVP%201.0%20Complete-green)
![Backend Tests](https://img.shields.io/badge/backend%20tests-passing-green)
![Frontend Tests](https://img.shields.io/badge/frontend%20tests-passing-green)

Oracle is an intelligent, conversational AI agent designed to provide context-aware responses with session memory. Built with a modern Python FastAPI backend and a responsive React frontend, it demonstrates production-ready architecture and comprehensive testing.

## 🎯 Project Goal

The primary goal is to build a robust, well-designed, and maintainable software project that replicates and expands upon the core functionalities of modern AI assistants like Google Gemini or ChatGPT. This includes integrating with a large language model (LLM), managing conversational memory, and enabling the agent to use external tools like web search.

---

## 🗺️ Project Status & Roadmap

### ✅ MVP 1.0: Core Chat (COMPLETE)
* **Backend:** FastAPI server with comprehensive error handling and logging
* **Frontend:** React (with Vite) single-page chat application with responsive UI
* **Core Logic:** Full integration with Gemini API with configurable models
* **Memory:** Stateless conversation history passed with each request
* **Testing:** Comprehensive test suite with 80%+ coverage
* **Features:**
  - Real-time chat interface with message history
  - Configurable AI personality via system instructions
  - Model selection via environment variables
  - Production-ready error handling and monitoring
  - Health check endpoints and service diagnostics

### 🔄 Current Development

### MVP 1.1: Session Management & Persistence (IN PROGRESS)
* **Database:** SQLite integration with SQLModel for type-safe database operations
* **Session Storage:** Persistent chat sessions with message history stored server-side
* **Performance:** Significant reduction in API token usage and improved response times
* **API Enhancement:** New session-based endpoints for chat management
* **Frontend Migration:** Complete UI overhaul to support session management
* **Features:**
  - Create, manage, and switch between multiple chat sessions
  - Persistent conversation history stored in database
  - Session metadata (title, creation date, message count, model used)
  - Optimized token usage by maintaining server-side context
  - Session-based health monitoring and analytics
  - **Frontend UI Updates:**
    - Session sidebar for managing multiple conversations
    - Session creation, switching, and management interface
    - Session metadata display (title, message count, last activity)
    - Removal of client-side conversation history storage
    - Session-based chat interface with context headers
    - Mobile-responsive session management

### MVP 1.2: LangChain Integration & Smart Memory (PLANNED)
* **Memory Management:** LangChain integration for intelligent conversation handling
* **Summarization:** Automatic summarization of long conversations to manage token limits
* **Entity Extraction:** Remember important facts and preferences within sessions
* **Context Optimization:** Smart selection of relevant conversation history
* **Memory Types:** Configurable memory strategies (buffer, summary, entity-based)
* **Features:**
  - Intelligent conversation summarization for long chats
  - Entity extraction and fact retention across conversations
  - Optimized context selection for better AI responses
  - Multiple memory strategies per session type
  - Enhanced conversation continuity and relevance

### 🔮 Future Phases (Planned)

### MVP 1.3: Web Search & Tool Use
* **Capability:** Agent will perform internet searches to answer questions
* **Mechanism:** Gemini API's function calling (tool use) feature integrated with sessions
* **Context:** Tools will have access to session history and extracted entities

### MVP 1.4: Agentic Reflection (Self-Correction)
* **Capability:** Agent will review search results before responding
* **Mechanism:** Self-correction loop managed with LangChain framework
* **Session Integration:** Reflection results stored in session context

### MVP 2.0: Advanced Session Features
* **Multi-User Support:** User authentication and personal session management
* **Session Sharing:** Ability to share sessions between users
* **Session Templates:** Pre-configured session types for different use cases
* **Export/Import:** Session backup and restoration capabilities

### MVP 3.0: Long-Term Memory & RAG
* **Vector Database:** Integration with vector database for semantic memory
* **Cross-Session Memory:** User preferences and facts remembered across all sessions
* **RAG Integration:** Retrieval-augmented generation for enhanced responses
* **Knowledge Base:** Personal knowledge base built from conversation history

---

## 🏛️ Architecture & Implementation

The project implements a production-ready, decoupled frontend/backend architecture.

### Current Architecture (MVP 1.0)

#### Backend (FastAPI)
- **API Layer:** RESTful endpoints with comprehensive validation and error handling
- **Business Logic:** Modular service layer for chat processing and AI integration
- **AI Integration:** Configurable Gemini API client with multiple model support
- **Memory:** Stateless conversation handling (history passed with each request)
- **Monitoring:** Health checks, error tracking, and comprehensive logging
- **Configuration:** Environment-based configuration with multiple AI personalities

#### Frontend (React + Vite)
- **UI Components:** Responsive chat interface with real-time message display
- **State Management:** React hooks for conversation state and error handling
- **Memory Management:** Client-side conversation history storage
- **API Communication:** Axios-based service layer with error recovery
- **Testing:** Component and integration tests with React Testing Library

### Planned Architecture (MVP 1.1+)

#### Enhanced Backend
- **Database Layer:** SQLite with SQLModel for type-safe database operations
- **Session Management:** Persistent chat sessions with server-side history storage
- **Memory Optimization:** Intelligent context management with LangChain integration
- **Performance:** Reduced API token usage and improved response times
- **Advanced Features:** Session analytics, conversation summarization, entity extraction

#### Enhanced Frontend (MVP 1.1)
- **Session Management UI:** Complete interface redesign for multi-session support
- **Session Sidebar:** Dedicated panel for creating, viewing, and switching between sessions
- **Optimized State Management:** Minimal client-side state (sessions managed server-side)
- **Session Context Interface:** Headers showing current session info and controls
- **Enhanced UX:** Intuitive session switching, history browsing, and session management
- **Mobile Responsive:** Adaptive session management for mobile devices
- **Real-Time Updates:** Live session updates and message synchronization

### Key Features Implemented
- **Configurable AI Models:** Switch between Gemini models via environment variables
- **System Instructions:** Multiple AI personality types (default, professional, technical, creative, educational)
- **Error Handling:** Production-grade error handling with user-friendly messages
- **Logging & Monitoring:** Comprehensive logging with structured error tracking
- **Testing:** Full test coverage for both backend and frontend components

---

## ✨ Design Principles

* **Modularity:** The frontend, backend, and agent logic are strictly decoupled to allow for independent development, testing, and scaling.
* **Simplicity:** We prioritize the simplest, cleanest solution that meets the requirements for the current MVP, avoiding over-engineering.
* **Performance:** We use high-performance, asynchronous frameworks (`FastAPI`, `uvicorn`) and efficient frontend libraries (`React`) to ensure a responsive user experience.
* **Scalability:** The architecture is designed to be stateless (where possible) to support future scaling (e.g., containerization, serverless deployment).
* **Testability:** Logic, especially in the backend, is written in a way that encourages unit and integration testing.
* **Current Documentation:** All API integrations must reference the latest official documentation via Context 7 (MCP) to ensure implementations follow current best practices.

---

## 📁 Project Structure

```
oracle/
├── backend/                    # FastAPI backend application
│   ├── api/v1/                # API routes and endpoints
│   │   ├── chat_router.py     # Legacy stateless chat endpoints
│   │   ├── session_router.py  # Session-based chat endpoints (MVP 1.1)
│   │   └── monitoring_router.py # Health checks and diagnostics
│   ├── config/                # Configuration management
│   │   ├── database.py        # Database configuration (MVP 1.1)
│   │   └── system_instructions.py # AI personality configurations
│   ├── models/                # Pydantic data models
│   │   ├── chat_models.py     # Legacy chat request/response models
│   │   ├── session_models.py  # Session and message models (MVP 1.1)
│   │   └── error_models.py    # Error response models
│   ├── services/              # Business logic and external integrations
│   │   ├── chat_service.py    # Legacy stateless chat service
│   │   ├── session_service.py # Session management service (MVP 1.1)
│   │   ├── session_chat_service.py # Session-based chat service (MVP 1.1)
│   │   └── gemini_client.py   # Gemini API client wrapper
│   ├── tests/                 # Comprehensive test suite
│   │   ├── test_main.py       # API integration tests
│   │   ├── test_gemini_integration.py # Service layer tests
│   │   ├── test_models.py     # Data model tests
│   │   └── test_e2e_integration.py # End-to-end tests
│   ├── utils/                 # Utility modules
│   │   └── logging_config.py  # Structured logging setup
│   ├── main.py               # FastAPI application entry point
│   ├── .env.example          # Environment variables template
│   └── .env                  # Local environment configuration
├── frontend/                  # React frontend application
│   ├── src/
│   │   ├── components/       # React UI components
│   │   │   ├── ChatInterface.jsx # Main chat component
│   │   │   ├── Message.jsx   # Message display component
│   │   │   ├── MessageInput.jsx # Message input component
│   │   │   └── ErrorDisplay.jsx # Error handling component
│   │   ├── hooks/            # Custom React hooks
│   │   │   └── useErrorHandler.js # Error handling hook
│   │   ├── services/         # API communication
│   │   │   └── api.js        # Axios-based API client
│   │   └── test/            # Frontend test suite
│   ├── package.json         # Node.js dependencies and scripts
│   └── vite.config.js       # Vite configuration
├── scripts/                   # Development and deployment scripts
│   └── dev-setup.sh         # Automated development setup
├── logs/                     # Application logs
├── .kiro/                    # Kiro IDE configuration
│   └── steering/            # Development guidelines and standards
├── pyproject.toml            # Python project configuration
├── PROJECT_STRUCTURE.md      # Detailed structure documentation
└── README.md                 # Project documentation
```

---

## 🛠️ Tech Stack

| Component | Technology | Package(s) / Tool(s) | Status |
| :--- | :--- | :--- | :--- |
| **Backend** | Python 3.14+ | `fastapi`, `uvicorn`, `google-genai`, `python-dotenv` | ✅ Implemented |
| **Database** | SQLite | `sqlmodel`, `sqlalchemy` | 🔄 MVP 1.1 |
| **Frontend** | JavaScript / React | `react`, `vite`, `axios` | ✅ Implemented |
| **Testing** | Python | `pytest`, `pytest-mock`, `pytest-asyncio` | ✅ Implemented |
| **Testing** | JavaScript | `vitest`, `@testing-library/react` | ✅ Implemented |
| **Package Mgmt** | Python | `uv` | ✅ Implemented |
| **Package Mgmt** | Node.js | `npm` | ✅ Implemented |
| **Logging** | Python | Custom structured logging | ✅ Implemented |
| **Memory & AI** | Python | `langchain` | 🔄 MVP 1.2 |
| **Session Mgmt** | Python | SQLModel + SQLite | 🔄 MVP 1.1 |

---

## � Develop ment Standards

### Library and API Integration Requirements

**MANDATORY**: Before implementing any library integration or external API, developers must:

1. **Use Context 7 (MCP)** to lookup the latest official documentation
2. **Verify current best practices** and check for any recent changes or deprecations
3. **Implement based on latest specifications** found in the documentation
4. **Document the library/API version** and retrieval date in code comments

This ensures all implementations follow current standards and avoid issues with outdated patterns.

### Key Libraries and APIs Requiring Context 7 Lookup

#### Backend
- **FastAPI**: Routing, middleware, validation patterns
- **Gemini API**: Authentication, chat sessions, message formatting, error handling
- **Pydantic**: Model validation and serialization
- **pytest**: Testing patterns and fixtures

#### Frontend
- **React**: Hooks, components, state management patterns
- **Vite**: Build configuration and development setup
- **Axios**: HTTP client configuration and best practices
- **React Testing Library**: Component testing patterns

#### Future Integrations
- **LangChain** (MVP 1.2+): Agent orchestration and framework patterns
- **Web Search APIs** (MVP 1.1+): Integration and usage patterns

---

## 🚀 Getting Started

### Prerequisites

* Python 3.14+ and `uv` (as specified in .python-version)
* Node.js 18+ and `npm`
* A **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/app/apikey)
* **Context 7 (MCP)** configured for API documentation lookup

### Configuration

1. Clone this repository
2. Copy the environment template and configure your settings:

```bash
# Backend configuration
cp backend/.env.example backend/.env

# Frontend configuration (optional)
cp frontend/.env.example frontend/.env
```

3. Edit `backend/.env` with your configuration:

```ini
# Required: Gemini API key from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Choose your AI model
GEMINI_MODEL=gemini-2.5-flash-lite

# Optional: Set AI personality
SYSTEM_INSTRUCTION_TYPE=default

# Optional: Server configuration
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
LOG_LEVEL=info
```

### Quick Setup

```bash
# Run the automated setup script
./scripts/dev-setup.sh

# Edit backend/.env and add your Gemini API key
# GEMINI_API_KEY=your_api_key_here
```

### Manual Setup

```bash
# Create virtual environment and install backend dependencies
uv venv
uv pip install -e ".[dev]"

# Set up environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Edit backend/.env with your Gemini API key

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Running the Application

```bash
# Terminal 1: Start backend
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

The application will be running on http://localhost:5173.

### API Documentation

When the backend is running, FastAPI automatically generates interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Testing

The project includes comprehensive test coverage for both backend and frontend.

#### Backend Tests
```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=backend --cov-report=html

# Run specific test categories
uv run pytest backend/tests/test_main.py -v                    # API integration tests
uv run pytest backend/tests/test_gemini_integration.py -v      # Service layer tests
uv run pytest backend/tests/test_models.py -v                 # Data model tests
uv run pytest backend/tests/test_e2e_integration.py -v        # End-to-end tests

# Run tests with detailed output
uv run pytest -v --tb=short
```

#### Frontend Tests
```bash
cd frontend

# Run all tests once
npm test

# Run tests in watch mode (development)
npm run test:watch

# Run tests with UI (interactive)
npm run test:ui

# Run specific test files
npm test -- ChatInterface.test.jsx
```

#### Test Coverage
- **Backend:** 80%+ coverage on core business logic
- **Frontend:** Component and integration test coverage
- **E2E:** Full user workflow testing
- **API:** Comprehensive endpoint testing with error scenarios

## 🔌 API Endpoints

### Chat Endpoints

#### `POST /api/v1/chat`
Send a message to the AI agent and receive a response.

**Request Body:**
```json
{
  "message": "What is FastAPI?",
  "history": [
    { "role": "user", "parts": "Hello" },
    { "role": "model", "parts": "Hi there! How can I help you today?" }
  ]
}
```

**Response:**
```json
{
  "response": "FastAPI is a modern, fast web framework for building APIs with Python 3.7+ based on standard Python type hints.",
  "timestamp": "2025-01-27T12:00:00Z"
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid request data
- `401` - Authentication failed
- `429` - Rate limit exceeded
- `500` - Internal server error

#### `GET /api/v1/chat/health`
Check the health status of the chat service.

**Response:**
```json
{
  "status": "healthy",
  "service": "chat",
  "model": "gemini-2.5-flash-lite",
  "active_sessions": 0,
  "service_status": "active",
  "timestamp": "2025-01-27T12:00:00Z"
}
```

### System Endpoints

#### `GET /health`
Overall system health check.

#### `GET /`
API status endpoint.

### Configuration Options

#### Available AI Models
- `gemini-2.5-flash` (default) - Balanced performance and speed
- `gemini-2.5-flash-lite` - Faster responses, lighter processing
- `gemini-1.5-pro` - Enhanced reasoning capabilities
- `gemini-1.5-flash` - Fast responses with good quality

#### Available AI Personalities
- `default` - General purpose helpful assistant
- `professional` - Business and productivity focused
- `technical` - Software development specialist
- `creative` - Creative and engaging conversational style
- `educational` - Teaching and learning focused

Set via `SYSTEM_INSTRUCTION_TYPE` in your `.env` file.

---

## 🚀 Current Features (MVP 1.0)

### Core Chat Functionality
- **Real-time Conversation:** Seamless chat interface with message history
- **Context Awareness:** AI maintains conversation context across messages (stateless)
- **Multiple AI Models:** Switch between different Gemini models via configuration
- **AI Personalities:** Choose from 5 different AI personality types
- **Error Recovery:** Graceful error handling with user-friendly messages

### Technical Features
- **Production Ready:** Comprehensive error handling, logging, and monitoring
- **Configurable:** Environment-based configuration for all settings
- **Stateless Architecture:** Current design passes full history with each request
- **Comprehensive Testing:** Full test coverage with automated testing
- **API Documentation:** Auto-generated OpenAPI/Swagger documentation
- **Health Monitoring:** Service health checks and diagnostics

### User Experience
- **Responsive Design:** Works on desktop and mobile devices
- **Fast Performance:** Optimized for quick response times
- **Accessibility:** Built with accessibility best practices
- **Error Feedback:** Clear error messages and recovery guidance

## 🔄 Upcoming Features (MVP 1.1 & 1.2)

### Session Management (MVP 1.1)
- **Persistent Sessions:** Create and manage multiple independent chat sessions
- **Server-Side History:** Conversation history stored in database, not client
- **Performance Optimization:** 70-80% reduction in API token usage
- **Session Metadata:** Track session creation, last activity, message counts
- **Database Integration:** SQLite with SQLModel for type-safe operations

### Smart Memory (MVP 1.2)
- **Conversation Summarization:** Automatic summarization of long conversations
- **Entity Extraction:** Remember important facts and user preferences
- **Context Optimization:** Intelligent selection of relevant conversation history
- **Memory Strategies:** Multiple memory types (buffer, summary, entity-based)
- **LangChain Integration:** Advanced conversation management and memory

---
## 📝 Development Updates

### Model Configuration Abstraction (MVP 1.0 Complete)
- **Configurable AI Models:** Switch between Gemini models via `GEMINI_MODEL` environment variable
- **Dynamic Model Selection:** No code changes required to use different models
- **Backward Compatible:** Defaults to `gemini-2.5-flash` if no model is specified
- **Test Coverage:** Comprehensive tests for model configuration scenarios

### Available Models
- `gemini-2.5-flash` - Default balanced model
- `gemini-2.5-flash-lite` - Faster, lighter responses  
- `gemini-2.5-pro` - Enhanced reasoning capabilities

Simply update your `.env` file:
```ini
GEMINI_MODEL=gemini-2.5-flash-lite
```

### Next: Session Management (MVP 1.1)
**Objective:** Replace stateless conversation handling with persistent session management

**Key Changes:**
- **Database Integration:** SQLite + SQLModel for session and message storage
- **API Evolution:** New session-based endpoints (`/api/v1/sessions/`)
- **Performance Improvement:** Reduce API token usage by 70-80%
- **Frontend UI Overhaul:** Complete redesign to support multi-session management
- **Session Interface:** New sidebar, session controls, and context-aware chat interface
- **State Management:** Migration from client-side to server-side conversation storage
- **Backward Compatibility:** Maintain existing endpoints during transition

**Benefits:**
- Dramatically reduced API costs through server-side history management
- Better user experience with persistent conversation sessions
- Foundation for advanced features (summarization, entity extraction)
- Improved scalability and performance

**Development Approach:**
- **Phase 1:** Implement backend session management alongside existing stateless system
- **Phase 2:** Design and implement new frontend UI for session management
- **Phase 3:** Update frontend to use session-based endpoints and new UI
- **Phase 4:** Deprecate and eventually remove stateless endpoints
- **Testing:** Comprehensive test coverage for both backend session functionality and frontend UI
- **Migration:** Smooth transition without breaking existing functionality

---

## 🤝 Contributing

This project follows strict development standards:

1. **Context 7 Documentation Lookup:** All library integrations must reference latest official documentation
2. **Comprehensive Testing:** Maintain 80%+ test coverage for new features
3. **Code Standards:** Follow the established patterns in `.kiro/steering/` guidelines
4. **Security First:** All secrets via environment variables, input validation, and error handling

See the development guidelines in `.kiro/steering/` for detailed standards.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.