# Services package

# Existing services
from .gemini_client import GeminiClient
from .session_service import SessionService
from .session_chat_service import SessionChatService

# LangChain integration services
from .langchain_client import LangChainClient
from .langchain_chat_session import LangChainChatSession
from .memory_manager import MemoryManager
from .context_optimizer import ContextOptimizer

__all__ = [
    # Existing services
    "GeminiClient",
    "SessionService", 
    "SessionChatService",
    # LangChain services
    "LangChainClient",
    "LangChainChatSession",
    "MemoryManager",
    "ContextOptimizer",
]