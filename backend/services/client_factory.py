"""
Client factory for Oracle application.

Provides factory methods to create appropriate AI clients based on
feature flags, enabling gradual rollout and rollback capabilities.
"""

import os
from typing import Optional, Union, Dict, Any

from backend.utils.logging_config import get_logger
from backend.exceptions import ConfigurationError, AIServiceError
from backend.services.feature_flags import is_langchain_enabled, get_feature_flag_manager


class ClientFactory:
    """
    Factory for creating AI clients based on feature flags.
    
    Supports gradual rollout by switching between GeminiClient and
    LangChainClient based on feature flag configuration.
    """
    
    def __init__(self):
        """Initialize client factory."""
        self.logger = get_logger("client_factory")
        self.feature_manager = get_feature_flag_manager()
        
        # Cache for client instances
        self._gemini_client = None
        self._langchain_client = None
    
    def create_client(
        self, 
        session_id: Optional[int] = None, 
        user_id: Optional[str] = None,
        force_client_type: Optional[str] = None
    ) -> Union["GeminiClient", "LangChainClient"]:
        """
        Create appropriate AI client based on feature flags.
        
        Args:
            session_id: Optional session ID for feature flag evaluation
            user_id: Optional user ID for feature flag evaluation
            force_client_type: Optional client type to force ("gemini" or "langchain")
            
        Returns:
            AI client instance (GeminiClient or LangChainClient)
            
        Raises:
            ConfigurationError: If client creation fails
        """
        try:
            # Determine which client to use
            use_langchain = self._should_use_langchain(session_id, user_id, force_client_type)
            
            if use_langchain:
                return self._get_langchain_client()
            else:
                return self._get_gemini_client()
                
        except Exception as e:
            self.logger.error(f"Failed to create client: {str(e)}")
            
            # Fallback to GeminiClient if LangChain fails
            if use_langchain:
                self.logger.warning("LangChain client creation failed, falling back to GeminiClient")
                return self._get_gemini_client()
            else:
                raise ConfigurationError(f"Failed to create AI client: {str(e)}")
    
    def _should_use_langchain(
        self, 
        session_id: Optional[int], 
        user_id: Optional[str], 
        force_client_type: Optional[str]
    ) -> bool:
        """
        Determine whether to use LangChain client.
        
        Args:
            session_id: Session ID for feature flag evaluation
            user_id: User ID for feature flag evaluation
            force_client_type: Forced client type
            
        Returns:
            bool: True if LangChain client should be used
        """
        # Check for forced client type
        if force_client_type:
            if force_client_type.lower() == "langchain":
                self.logger.info(f"Forced to use LangChain client for session {session_id}")
                return True
            elif force_client_type.lower() == "gemini":
                self.logger.info(f"Forced to use Gemini client for session {session_id}")
                return False
        
        # Check feature flag
        langchain_enabled = is_langchain_enabled(session_id=session_id, user_id=user_id)
        
        self.logger.debug(
            f"LangChain feature flag evaluation: session_id={session_id}, "
            f"user_id={user_id}, enabled={langchain_enabled}"
        )
        
        return langchain_enabled
    
    def _get_langchain_client(self) -> "LangChainClient":
        """Get or create LangChain client instance."""
        if self._langchain_client is None:
            try:
                from backend.services.langchain_client import LangChainClient
                
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                
                self._langchain_client = LangChainClient(api_key=api_key, model=model)
                self.logger.info("Created LangChain client instance")
                
            except Exception as e:
                self.logger.error(f"Failed to create LangChain client: {str(e)}")
                raise ConfigurationError(f"LangChain client creation failed: {str(e)}")
        
        return self._langchain_client
    
    def _get_gemini_client(self) -> "GeminiClient":
        """Get or create Gemini client instance."""
        if self._gemini_client is None:
            try:
                from backend.services.gemini_client import GeminiClient
                
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                
                self._gemini_client = GeminiClient(api_key=api_key, model=model)
                self.logger.info("Created Gemini client instance")
                
            except Exception as e:
                self.logger.error(f"Failed to create Gemini client: {str(e)}")
                raise ConfigurationError(f"Gemini client creation failed: {str(e)}")
        
        return self._gemini_client
    
    def get_client_type(
        self, 
        session_id: Optional[int] = None, 
        user_id: Optional[str] = None
    ) -> str:
        """
        Get the client type that would be used for the given context.
        
        Args:
            session_id: Optional session ID
            user_id: Optional user ID
            
        Returns:
            str: "langchain" or "gemini"
        """
        use_langchain = self._should_use_langchain(session_id, user_id, None)
        return "langchain" if use_langchain else "gemini"
    
    def get_client_stats(self) -> Dict[str, Any]:
        """
        Get statistics about client usage and feature flag status.
        
        Returns:
            Dictionary with client statistics
        """
        stats = {
            "langchain_client_created": self._langchain_client is not None,
            "gemini_client_created": self._gemini_client is not None,
            "feature_flags": {}
        }
        
        # Get feature flag status
        try:
            flag_manager = get_feature_flag_manager()
            langchain_flag = flag_manager.get_flag_status("langchain_integration")
            if langchain_flag:
                stats["feature_flags"]["langchain_integration"] = langchain_flag
        except Exception as e:
            self.logger.warning(f"Failed to get feature flag status: {str(e)}")
        
        # Get client-specific stats if available
        if self._langchain_client:
            try:
                stats["langchain_stats"] = self._langchain_client.get_session_stats()
            except Exception as e:
                self.logger.warning(f"Failed to get LangChain client stats: {str(e)}")
        
        if self._gemini_client:
            try:
                stats["gemini_stats"] = self._gemini_client.get_session_stats()
            except Exception as e:
                self.logger.warning(f"Failed to get Gemini client stats: {str(e)}")
        
        return stats
    
    def reset_clients(self) -> None:
        """Reset client instances (useful for testing or configuration changes)."""
        self._langchain_client = None
        self._gemini_client = None
        self.logger.info("Reset client instances")
    
    def test_client_creation(self, client_type: str) -> Dict[str, Any]:
        """
        Test client creation without caching.
        
        Args:
            client_type: "langchain" or "gemini"
            
        Returns:
            Dictionary with test results
        """
        result = {
            "client_type": client_type,
            "success": False,
            "error": None,
            "client_info": None
        }
        
        try:
            if client_type.lower() == "langchain":
                from backend.services.langchain_client import LangChainClient
                
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                
                test_client = LangChainClient(api_key=api_key, model=model)
                result["success"] = True
                result["client_info"] = {
                    "model": test_client.model,
                    "has_api_key": bool(test_client.api_key)
                }
                
            elif client_type.lower() == "gemini":
                from backend.services.gemini_client import GeminiClient
                
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                
                test_client = GeminiClient(api_key=api_key, model=model)
                result["success"] = True
                result["client_info"] = {
                    "model": test_client.model,
                    "has_api_key": bool(test_client.api_key)
                }
                
            else:
                result["error"] = f"Unknown client type: {client_type}"
                
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Client creation test failed for {client_type}: {str(e)}")
        
        return result


# Global client factory instance
_client_factory: Optional[ClientFactory] = None


def get_client_factory() -> ClientFactory:
    """Get the global client factory instance."""
    global _client_factory
    if _client_factory is None:
        _client_factory = ClientFactory()
    return _client_factory


def create_ai_client(
    session_id: Optional[int] = None, 
    user_id: Optional[str] = None,
    force_client_type: Optional[str] = None
) -> Union["GeminiClient", "LangChainClient"]:
    """
    Convenience function to create an AI client.
    
    Args:
        session_id: Optional session ID for feature flag evaluation
        user_id: Optional user ID for feature flag evaluation
        force_client_type: Optional client type to force
        
    Returns:
        AI client instance
    """
    return get_client_factory().create_client(session_id, user_id, force_client_type)


class FeatureFlaggedSessionChatService:
    """
    Session chat service that uses feature flags to determine client type.
    
    This service wraps the existing SessionChatService and automatically
    selects the appropriate AI client based on feature flags.
    """
    
    def __init__(self, db_session):
        """
        Initialize feature-flagged session chat service.
        
        Args:
            db_session: Database session for operations
        """
        self.db = db_session
        self.client_factory = get_client_factory()
        self.logger = get_logger("feature_flagged_session_chat_service")
    
    async def send_message(self, session_id: int, message: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a message using the appropriate client based on feature flags.
        
        Args:
            session_id: Session ID
            message: Message to send
            user_id: Optional user ID for feature flag evaluation
            
        Returns:
            Chat response with client type information
        """
        try:
            # Determine which client to use
            client_type = self.client_factory.get_client_type(session_id=session_id, user_id=user_id)
            
            # Create appropriate client
            ai_client = self.client_factory.create_client(session_id=session_id, user_id=user_id)
            
            # Create session chat service with the selected client
            from backend.services.session_chat_service import SessionChatService
            chat_service = SessionChatService(self.db, ai_client)
            
            # Send message
            response = await chat_service.send_message(session_id, message)
            
            # Add client type information to response
            if hasattr(response, 'assistant_message') and hasattr(response.assistant_message, 'message_metadata'):
                if response.assistant_message.message_metadata is None:
                    response.assistant_message.message_metadata = {}
                response.assistant_message.message_metadata["client_type"] = client_type
            
            self.logger.info(f"Message sent using {client_type} client for session {session_id}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to send message for session {session_id}: {str(e)}")
            
            # Try fallback to Gemini client if LangChain failed
            if client_type == "langchain":
                self.logger.warning("Attempting fallback to Gemini client")
                try:
                    gemini_client = self.client_factory._get_gemini_client()
                    from backend.services.session_chat_service import SessionChatService
                    fallback_service = SessionChatService(self.db, gemini_client)
                    
                    response = await fallback_service.send_message(session_id, message)
                    
                    # Mark as fallback
                    if hasattr(response, 'assistant_message') and hasattr(response.assistant_message, 'message_metadata'):
                        if response.assistant_message.message_metadata is None:
                            response.assistant_message.message_metadata = {}
                        response.assistant_message.message_metadata["client_type"] = "gemini"
                        response.assistant_message.message_metadata["fallback_from_langchain"] = True
                    
                    self.logger.info(f"Fallback successful for session {session_id}")
                    return response
                    
                except Exception as fallback_error:
                    self.logger.error(f"Fallback also failed for session {session_id}: {str(fallback_error)}")
                    raise AIServiceError(f"Both primary and fallback clients failed: {str(e)} | {str(fallback_error)}")
            
            raise
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
        return {
            "client_factory_stats": self.client_factory.get_client_stats(),
            "feature_flags": get_feature_flag_manager().get_all_flags_status()
        }