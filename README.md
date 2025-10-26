# Agent_Oracle
Agent that will have its own memory about you

# [Oracle]: An Intelligent Conversational AI Agent

![Project Status: In Development](https://img.shields.io/badge/status-Development-blue)

This project is an intelligent, conversational AI agent designed to provide context-aware responses and access external information. It's built with a modern Python backend and a responsive React frontend.

## 🎯 Project Goal

The primary goal is to build a robust, well-designed, and maintainable software project that replicates and expands upon the core functionalities of modern AI assistants like Google Gemini or ChatGPT. This includes integrating with a large language model (LLM), managing conversational memory, and enabling the agent to use external tools like web search.

---

## 🗺️ Project Roadmap

We are following an iterative, phased development plan.

### MVP 1.0: Core Chat
* **Backend:** A `FastAPI` server.
* **Frontend:** A `React` (with `Vite`) single-page chat application.
* **Core Logic:** The app will connect to the Gemini API.
* **Memory:** The app will maintain short-term (session) memory by passing the current chat history with each request.

### MVP 1.1: Web Search (Tool Use)
* **Capability:** The agent will gain the ability to perform general internet searches to answer questions.
* **Mechanism:** This will be implemented using the Gemini API's "function calling" (tool use) feature.

### MVP 1.2: Agentic Reflection (Self-Correction)
* **Capability:** The agent will review its own search results *before* answering the user to determine if the information is sufficient.
* **Mechanism:** This introduces a "self-correction loop," which will be managed using the `LangChain` framework.

### MVP 2.0: Multi-Session Support
* **Capability:** Users will be able to create, save, and switch between different chat sessions, each with its own independent context.

### MVP 3.0: Long-Term Memory
* **Capability:** The agent will remember key user preferences (e.g., "my favorite programming language is Python") across all sessions.
* **Mechanism:** This will likely involve a vector database for persistent, retrieval-augmented generation (RAG).

---

## 🏛️ Core Components & Architecture

The project is built on a decoupled frontend/backend architecture.

1.  **Frontend (Client):** A `React` application built with `Vite`. It provides the user interface, manages UI state, and communicates with the backend via REST API calls.
2.  **Backend (Server):** A `FastAPI` (Python) server. It exposes API endpoints, manages business logic, and orchestrates communication with all external services (LLM, Search APIs, etc.).
3.  **LLM Service:** `google-generativeai` (Gemini API) provides the core natural language understanding and generation.
4.  **Agentic Framework:** `LangChain` will be introduced in MVP 1.2 to manage multi-step agentic chains and the reflection loop.

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
│   ├── models/                # Pydantic data models
│   ├── services/              # Business logic and external integrations
│   ├── tests/                 # Backend tests
│   ├── main.py               # FastAPI application entry point
│   └── .env.example          # Environment variables template
├── frontend/                  # React frontend application
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── services/         # API communication
│   │   └── test/            # Test setup
│   ├── package.json         # Node.js dependencies and scripts
│   └── vite.config.js       # Vite configuration
├── scripts/                   # Development scripts
│   └── dev-setup.sh         # Automated development setup
├── pyproject.toml            # Python project configuration
├── PROJECT_STRUCTURE.md      # Detailed structure documentation
└── README.md                 # Project documentation
```

---

## 🛠️ Tech Stack

| Component | Technology | Package(s) / Tool(s) |
| :--- | :--- | :--- |
| **Backend** | Python 3.14+ | `fastapi`, `uvicorn`, `google-generativeai`, `python-dotenv` |
| **Frontend** | JavaScript / React | `react`, `vite`, `axios` |
| **Package Mgmt** | Python | `uv` |
| **Package Mgmt** | Node.js | `npm` |
| **Orchestration** | Python | `langchain` (from MVP 1.2) |

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

1.  Clone this repository.
2.  In the `backend/` directory, create a file named `.env`.
3.  Add your API key to the file:

    ```ini
    GEMINI_API_KEY="YOUR_API_KEY_HERE"
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

#### Backend Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=backend

# Run specific test file
uv run pytest backend/tests/test_main.py -v
```

#### Frontend Tests
```bash
cd frontend

# Run tests once
npm test

# Run tests in watch mode
npm run test:watch
```

### API Endpoints

```ini
POST /chat
```

Description: Sends a user message and the current conversation history to the agent and receives a response.

Request Body:
```JSON
{
  "message": "What is FastAPI?",
  "history": [
    { "role": "user", "parts": "Hello" },
    { "role": "model", "parts": "Hi there! How can I help you today?" }
  ]
}
```

Response Body:
```JSON
{
  "response": "FastAPI is a modern, fast (high-performance), web framework for building APIs with Python 3.7+ based on standard Python type hints."
}
```
---