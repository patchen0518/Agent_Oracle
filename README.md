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

### 1. Running the Backend Server

```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment using uv
uv venv

# Activate the environment
source .venv/bin/activate
# (On Windows: .\.venv\Scripts\activate)

# Install Python dependencies
uv pip install -r requirements.txt 

# Run the FastAPI server
uvicorn main:app --reload
```


### 2. Running the Frontend App
```bash
# Open a new terminal
# Navigate to the frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Run the React development server
npm run dev

The application will be running on http://localhost:5173.
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