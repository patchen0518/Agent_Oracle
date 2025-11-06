"""
Feature flag system for Oracle application.

Provides configuration-based feature toggles for gradual rollout
and rollback capabilities, particularly for LangChain integration.
"""

import os
import json
import hashlib
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from backend.utils.logging_config import get_logger
from backend.exceptions import ConfigurationError


class FeatureState(Enum):
    """Feature flag states."""
    DISABLED = "disabled"
    ENABLED = "enabled"
    PERCENTAGE_ROLLOUT = "percentage_rollout"
    USER_WHITELIST = "user_whitelist"
    SESSION_WHITELIST = "session_whitelist"


@dataclass
class FeatureFlagConfig:
    """Configuration for a feature flag."""
    name: str
    state: FeatureState
    description: str
    percentage: int = 0  # For percentage rollout (0-100)
    user_whitelist: List[str] = None  # For user-based rollout
    session_whitelist: List[int] = None  # For session-based rollout
    environment_override: Optional[str] = None  # Environment variable to check
    created_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.user_whitelist is None:
            self.user_whitelist = []
        if self.session_whitelist is None:
            self.session_whitelist = []
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at


class FeatureFlagManager:
    """
    Manages feature flags for gradual rollout and rollback capabilities.
    
    Supports multiple rollout strategies including percentage-based,
    user-based, and session-based feature enablement.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize feature flag manager.
        
        Args:
            config_file: Optional path to feature flag configuration file
        """
        self.logger = get_logger("feature_flags")
        self.config_file = config_file or os.getenv("FEATURE_FLAGS_CONFIG", "backend/config/feature_flags.json")
        self.flags: Dict[str, FeatureFlagConfig] = {}
        
        # Initialize default flags
        self._initialize_default_flags()
        
        # Load configuration
        self._load_configuration()
        
        self.logger.info(f"FeatureFlagManager initialized with {len(self.flags)} flags")
    
    def _initialize_default_flags(self) -> None:
        """Initialize default feature flags."""
        default_flags = {
            "langchain_integration": FeatureFlagConfig(
                name="langchain_integration",
                state=FeatureState.DISABLED,
                description="Enable LangChain integration for chat sessions",
                environment_override="ENABLE_LANGCHAIN"
            ),
            "langchain_memory_strategies": FeatureFlagConfig(
                name="langchain_memory_strategies",
                state=FeatureState.DISABLED,
                description="Enable advanced LangChain memory strategies",
                environment_override="ENABLE_LANGCHAIN_MEMORY"
            ),
            "context_optimization": FeatureFlagConfig(
                name="context_optimization",
                state=FeatureState.DISABLED,
                description="Enable context optimization and summarization",
                environment_override="ENABLE_CONTEXT_OPTIMIZATION"
            ),
            "memory_fallback": FeatureFlagConfig(
                name="memory_fallback",
                state=FeatureState.ENABLED,
                description="Enable memory fallback mechanisms",
                environment_override="ENABLE_MEMORY_FALLBACK"
            ),
            "hybrid_persistence": FeatureFlagConfig(
                name="hybrid_persistence",
                state=FeatureState.DISABLED,
                description="Enable hybrid memory-database persistence",
                environment_override="ENABLE_HYBRID_PERSISTENCE"
            )
        }
        
        self.flags.update(default_flags)
    
    def _load_configuration(self) -> None:
        """Load feature flag configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                for flag_name, flag_data in config_data.get("flags", {}).items():
                    try:
                        # Convert state string to enum
                        state = FeatureState(flag_data.get("state", "disabled"))
                        
                        flag_config = FeatureFlagConfig(
                            name=flag_name,
                            state=state,
                            description=flag_data.get("description", ""),
                            percentage=flag_data.get("percentage", 0),
                            user_whitelist=flag_data.get("user_whitelist", []),
                            session_whitelist=flag_data.get("session_whitelist", []),
                            environment_override=flag_data.get("environment_override"),
                            created_at=flag_data.get("created_at"),
                            updated_at=flag_data.get("updated_at")
                        )
                        
                        self.flags[flag_name] = flag_config
                        
                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"Invalid flag configuration for '{flag_name}': {str(e)}")
                
                self.logger.info(f"Loaded feature flag configuration from {self.config_file}")
            else:
                self.logger.info(f"No feature flag configuration file found at {self.config_file}, using defaults")
                
        except Exception as e:
            self.logger.error(f"Failed to load feature flag configuration: {str(e)}")
    
    def _save_configuration(self) -> None:
        """Save current feature flag configuration to file."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            config_data = {
                "flags": {
                    name: {
                        **asdict(flag),
                        "state": flag.state.value  # Convert enum to string
                    }
                    for name, flag in self.flags.items()
                },
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            self.logger.info(f"Saved feature flag configuration to {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save feature flag configuration: {str(e)}")
    
    def is_enabled(
        self, 
        flag_name: str, 
        user_id: Optional[str] = None, 
        session_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if a feature flag is enabled for the given context.
        
        Args:
            flag_name: Name of the feature flag
            user_id: Optional user ID for user-based rollout
            session_id: Optional session ID for session-based rollout
            context: Optional additional context for decision making
            
        Returns:
            bool: True if the feature is enabled
        """
        try:
            flag = self.flags.get(flag_name)
            if not flag:
                self.logger.warning(f"Unknown feature flag: {flag_name}")
                return False
            
            # Check environment override first
            if flag.environment_override:
                env_value = os.getenv(flag.environment_override)
                if env_value is not None:
                    env_enabled = env_value.lower() in ("true", "1", "yes", "on")
                    self.logger.debug(f"Feature '{flag_name}' overridden by environment: {env_enabled}")
                    return env_enabled
            
            # Check based on flag state
            if flag.state == FeatureState.DISABLED:
                return False
            elif flag.state == FeatureState.ENABLED:
                return True
            elif flag.state == FeatureState.PERCENTAGE_ROLLOUT:
                return self._check_percentage_rollout(flag, user_id, session_id)
            elif flag.state == FeatureState.USER_WHITELIST:
                return self._check_user_whitelist(flag, user_id)
            elif flag.state == FeatureState.SESSION_WHITELIST:
                return self._check_session_whitelist(flag, session_id)
            else:
                self.logger.warning(f"Unknown feature state for '{flag_name}': {flag.state}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking feature flag '{flag_name}': {str(e)}")
            return False
    
    def _check_percentage_rollout(
        self, 
        flag: FeatureFlagConfig, 
        user_id: Optional[str], 
        session_id: Optional[int]
    ) -> bool:
        """Check percentage-based rollout."""
        if flag.percentage <= 0:
            return False
        if flag.percentage >= 100:
            return True
        
        # Use user_id or session_id for consistent hashing
        identifier = user_id or str(session_id) if session_id else "anonymous"
        
        # Create deterministic hash
        hash_input = f"{flag.name}:{identifier}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
        percentage_bucket = hash_value % 100
        
        enabled = percentage_bucket < flag.percentage
        
        self.logger.debug(
            f"Percentage rollout for '{flag.name}': identifier={identifier}, "
            f"bucket={percentage_bucket}, threshold={flag.percentage}, enabled={enabled}"
        )
        
        return enabled
    
    def _check_user_whitelist(self, flag: FeatureFlagConfig, user_id: Optional[str]) -> bool:
        """Check user whitelist."""
        if not user_id:
            return False
        return user_id in flag.user_whitelist
    
    def _check_session_whitelist(self, flag: FeatureFlagConfig, session_id: Optional[int]) -> bool:
        """Check session whitelist."""
        if session_id is None:
            return False
        return session_id in flag.session_whitelist
    
    def enable_flag(self, flag_name: str, save: bool = True) -> bool:
        """
        Enable a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            save: Whether to save configuration to file
            
        Returns:
            bool: True if flag was enabled successfully
        """
        try:
            if flag_name not in self.flags:
                self.logger.error(f"Cannot enable unknown flag: {flag_name}")
                return False
            
            self.flags[flag_name].state = FeatureState.ENABLED
            self.flags[flag_name].updated_at = datetime.now(timezone.utc).isoformat()
            
            if save:
                self._save_configuration()
            
            self.logger.info(f"Enabled feature flag: {flag_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enable flag '{flag_name}': {str(e)}")
            return False
    
    def disable_flag(self, flag_name: str, save: bool = True) -> bool:
        """
        Disable a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            save: Whether to save configuration to file
            
        Returns:
            bool: True if flag was disabled successfully
        """
        try:
            if flag_name not in self.flags:
                self.logger.error(f"Cannot disable unknown flag: {flag_name}")
                return False
            
            self.flags[flag_name].state = FeatureState.DISABLED
            self.flags[flag_name].updated_at = datetime.now(timezone.utc).isoformat()
            
            if save:
                self._save_configuration()
            
            self.logger.info(f"Disabled feature flag: {flag_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to disable flag '{flag_name}': {str(e)}")
            return False
    
    def set_percentage_rollout(self, flag_name: str, percentage: int, save: bool = True) -> bool:
        """
        Set percentage rollout for a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            percentage: Percentage of users to enable (0-100)
            save: Whether to save configuration to file
            
        Returns:
            bool: True if percentage was set successfully
        """
        try:
            if flag_name not in self.flags:
                self.logger.error(f"Cannot set percentage for unknown flag: {flag_name}")
                return False
            
            if not 0 <= percentage <= 100:
                self.logger.error(f"Invalid percentage: {percentage}. Must be 0-100")
                return False
            
            self.flags[flag_name].state = FeatureState.PERCENTAGE_ROLLOUT
            self.flags[flag_name].percentage = percentage
            self.flags[flag_name].updated_at = datetime.now(timezone.utc).isoformat()
            
            if save:
                self._save_configuration()
            
            self.logger.info(f"Set percentage rollout for '{flag_name}': {percentage}%")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set percentage for flag '{flag_name}': {str(e)}")
            return False
    
    def add_to_whitelist(
        self, 
        flag_name: str, 
        user_id: Optional[str] = None, 
        session_id: Optional[int] = None,
        save: bool = True
    ) -> bool:
        """
        Add user or session to whitelist.
        
        Args:
            flag_name: Name of the feature flag
            user_id: User ID to add to whitelist
            session_id: Session ID to add to whitelist
            save: Whether to save configuration to file
            
        Returns:
            bool: True if added successfully
        """
        try:
            if flag_name not in self.flags:
                self.logger.error(f"Cannot modify whitelist for unknown flag: {flag_name}")
                return False
            
            flag = self.flags[flag_name]
            
            if user_id:
                if user_id not in flag.user_whitelist:
                    flag.user_whitelist.append(user_id)
                    flag.state = FeatureState.USER_WHITELIST
                    self.logger.info(f"Added user '{user_id}' to whitelist for flag '{flag_name}'")
            
            if session_id is not None:
                if session_id not in flag.session_whitelist:
                    flag.session_whitelist.append(session_id)
                    flag.state = FeatureState.SESSION_WHITELIST
                    self.logger.info(f"Added session {session_id} to whitelist for flag '{flag_name}'")
            
            flag.updated_at = datetime.now(timezone.utc).isoformat()
            
            if save:
                self._save_configuration()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add to whitelist for flag '{flag_name}': {str(e)}")
            return False
    
    def remove_from_whitelist(
        self, 
        flag_name: str, 
        user_id: Optional[str] = None, 
        session_id: Optional[int] = None,
        save: bool = True
    ) -> bool:
        """
        Remove user or session from whitelist.
        
        Args:
            flag_name: Name of the feature flag
            user_id: User ID to remove from whitelist
            session_id: Session ID to remove from whitelist
            save: Whether to save configuration to file
            
        Returns:
            bool: True if removed successfully
        """
        try:
            if flag_name not in self.flags:
                self.logger.error(f"Cannot modify whitelist for unknown flag: {flag_name}")
                return False
            
            flag = self.flags[flag_name]
            
            if user_id and user_id in flag.user_whitelist:
                flag.user_whitelist.remove(user_id)
                self.logger.info(f"Removed user '{user_id}' from whitelist for flag '{flag_name}'")
            
            if session_id is not None and session_id in flag.session_whitelist:
                flag.session_whitelist.remove(session_id)
                self.logger.info(f"Removed session {session_id} from whitelist for flag '{flag_name}'")
            
            flag.updated_at = datetime.now(timezone.utc).isoformat()
            
            if save:
                self._save_configuration()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove from whitelist for flag '{flag_name}': {str(e)}")
            return False
    
    def get_flag_status(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status of a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            
        Returns:
            Dictionary with flag status or None if flag doesn't exist
        """
        flag = self.flags.get(flag_name)
        if not flag:
            return None
        
        status = asdict(flag)
        status["state"] = flag.state.value  # Convert enum to string
        
        # Add environment override status
        if flag.environment_override:
            env_value = os.getenv(flag.environment_override)
            status["environment_override_value"] = env_value
            status["environment_override_active"] = env_value is not None
        
        return status
    
    def get_all_flags_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all feature flags."""
        return {name: self.get_flag_status(name) for name in self.flags.keys()}
    
    def reload_configuration(self) -> bool:
        """
        Reload feature flag configuration from file.
        
        Returns:
            bool: True if configuration was reloaded successfully
        """
        try:
            self._load_configuration()
            self.logger.info("Feature flag configuration reloaded")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {str(e)}")
            return False


# Global feature flag manager instance
_feature_flag_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Get the global feature flag manager instance."""
    global _feature_flag_manager
    if _feature_flag_manager is None:
        _feature_flag_manager = FeatureFlagManager()
    return _feature_flag_manager


def is_feature_enabled(
    flag_name: str, 
    user_id: Optional[str] = None, 
    session_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Convenience function to check if a feature is enabled.
    
    Args:
        flag_name: Name of the feature flag
        user_id: Optional user ID for user-based rollout
        session_id: Optional session ID for session-based rollout
        context: Optional additional context
        
    Returns:
        bool: True if the feature is enabled
    """
    return get_feature_flag_manager().is_enabled(flag_name, user_id, session_id, context)


def is_langchain_enabled(session_id: Optional[int] = None, user_id: Optional[str] = None) -> bool:
    """
    Check if LangChain integration is enabled for the given session/user.
    
    Args:
        session_id: Optional session ID
        user_id: Optional user ID
        
    Returns:
        bool: True if LangChain integration is enabled
    """
    return is_feature_enabled("langchain_integration", user_id=user_id, session_id=session_id)


def is_memory_fallback_enabled(session_id: Optional[int] = None) -> bool:
    """
    Check if memory fallback mechanisms are enabled.
    
    Args:
        session_id: Optional session ID
        
    Returns:
        bool: True if memory fallback is enabled
    """
    return is_feature_enabled("memory_fallback", session_id=session_id)


def is_context_optimization_enabled(session_id: Optional[int] = None) -> bool:
    """
    Check if context optimization is enabled.
    
    Args:
        session_id: Optional session ID
        
    Returns:
        bool: True if context optimization is enabled
    """
    return is_feature_enabled("context_optimization", session_id=session_id)