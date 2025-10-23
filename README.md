# agent_Oracle
Agent that will have its own memory about you

# [Oracle]: An Intelligent Conversational AI Agent

![Project Status: In Development](https://github.com/patchen0518/agent_Oracle)

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

---

## 🛠️ Tech Stack

| Component | Technology | Package(s) / Tool(s) |
| :--- | :--- | :--- |
| **Backend** | Python 3.11+ | `fastapi`, `uvicorn`, `google-generativeai`, `python-dotenv` |
| **Frontend** | JavaScript / React | `react`, `vite`, `axios` |
| **Package Mgmt** | Python | `uv` |
| **Package Mgmt** | Node.js | `npm` |
| **Orchestration** | Python | `langchain` (from MVP 1.2) |

---

## 🚀 Getting Started

### Prerequisites

* Python 3.11+ and `uv`
* Node.js 18+ and `npm`
* A **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/app/apikey)

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