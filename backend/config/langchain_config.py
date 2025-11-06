"""
LangChain configuration management for Oracle Chat AI.

This module provides configuration classes and utilities for managing
LangChain integration settings, including memory strategies, context
optimization, and model configuration.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class MemoryStrategy(str, Enum):
    """Available memory strategies for LangChain integration."""
    BUFFER = "buffer"
    SUMMARY = "summary"
    ENTITY = "entity"
    HYBRID = "hybrid"


@dataclass
class MemoryConfig:
    """Configuration for LangChain memory management."""
    strategy: MemoryStrategy = MemoryStrategy.HYBRID
    max_buffer_size: int = 20
    max_tokens_before_summary: int = 4000
    entity_extraction_enabled: bool = True
    summary_model: str = "gemini-2.5-flash"
    
    @classmethod
    def from_env(cls) -> "MemoryConfig":
        """Create MemoryConfig from environment variables."""
        return cls(
            strategy=MemoryStrategy(os.getenv("LANGCHAIN_MEMORY_STRATEGY", "hybrid")),
            max_buffer_size=int(os.getenv("LANGCHAIN_MAX_BUFFER_SIZE", "20")),
            max_tokens_before_summary=int(os.getenv("LANGCHAIN_MAX_TOKENS_BEFORE_SUMMARY", "4000")),
            entity_extraction_enabled=os.getenv("LANGCHAIN_ENTITY_EXTRACTION_ENABLED", "true").lower() == "true",
            summary_model=os.getenv("LANGCHAIN_SUMMARY_MODEL", "gemini-2.5-flash")
        )


@dataclass
class ContextConfig:
    """Configuration for LangChain context optimization."""
    max_tokens: int = 4000
    messages_to_keep_after_summary: int = 20
    relevance_threshold: float = 0.7
    enable_semantic_search: bool = True
    summarization_trigger_ratio: float = 0.8
    
    @classmethod
    def from_env(cls) -> "ContextConfig":
        """Create ContextConfig from environment variables."""
        return cls(
            max_tokens=int(os.getenv("LANGCHAIN_MAX_TOKENS", "4000")),
            messages_to_keep_after_summary=int(os.getenv("LANGCHAIN_MESSAGES_TO_KEEP_AFTER_SUMMARY", "20")),
            relevance_threshold=float(os.getenv("LANGCHAIN_RELEVANCE_THRESHOLD", "0.7")),
            enable_semantic_search=os.getenv("LANGCHAIN_ENABLE_SEMANTIC_SEARCH", "true").lower() == "true",
            summarization_trigger_ratio=float(os.getenv("LANGCHAIN_SUMMARIZATION_TRIGGER_RATIO", "0.8"))
        )


@dataclass
class LangChainModelConfig:
    """Configuration for LangChain model settings."""
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.7
    max_output_tokens: int = 2048
    api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "LangChainModelConfig":
        """Create LangChainModelConfig from environment variables."""
        return cls(
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            temperature=float(os.getenv("LANGCHAIN_TEMPERATURE", "0.7")),
            max_output_tokens=int(os.getenv("LANGCHAIN_MAX_OUTPUT_TOKENS", "2048")),
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        )


@dataclass
class LangChainMonitoringConfig:
    """Configuration for LangChain monitoring and logging."""
    log_level: str = "info"
    enable_performance_monitoring: bool = True
    enable_token_tracking: bool = True
    
    @classmethod
    def from_env(cls) -> "LangChainMonitoringConfig":
        """Create LangChainMonitoringConfig from environment variables."""
        return cls(
            log_level=os.getenv("LANGCHAIN_LOG_LEVEL", "info"),
            enable_performance_monitoring=os.getenv("LANGCHAIN_ENABLE_PERFORMANCE_MONITORING", "true").lower() == "true",
            enable_token_tracking=os.getenv("LANGCHAIN_ENABLE_TOKEN_TRACKING", "true").lower() == "true"
        )


@dataclass
class LangChainConfig:
    """Main configuration class for LangChain integration."""
    enabled: bool = True
    memory: MemoryConfig = None
    context: ContextConfig = None
    model: LangChainModelConfig = None
    monitoring: LangChainMonitoringConfig = None
    
    def __post_init__(self):
        """Initialize nested configurations if not provided."""
        if self.memory is None:
            self.memory = MemoryConfig()
        if self.context is None:
            self.context = ContextConfig()
        if self.model is None:
            self.model = LangChainModelConfig()
        if self.monitoring is None:
            self.monitoring = LangChainMonitoringConfig()
    
    @classmethod
    def from_env(cls) -> "LangChainConfig":
        """Create LangChainConfig from environment variables."""
        return cls(
            enabled=os.getenv("LANGCHAIN_ENABLED", "true").lower() == "true",
            memory=MemoryConfig.from_env(),
            context=ContextConfig.from_env(),
            model=LangChainModelConfig.from_env(),
            monitoring=LangChainMonitoringConfig.from_env()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for logging/debugging."""
        return {
            "enabled": self.enabled,
            "memory": {
                "strategy": self.memory.strategy.value,
                "max_buffer_size": self.memory.max_buffer_size,
                "max_tokens_before_summary": self.memory.max_tokens_before_summary,
                "entity_extraction_enabled": self.memory.entity_extraction_enabled,
                "summary_model": self.memory.summary_model
            },
            "context": {
                "max_tokens": self.context.max_tokens,
                "messages_to_keep_after_summary": self.context.messages_to_keep_after_summary,
                "relevance_threshold": self.context.relevance_threshold,
                "enable_semantic_search": self.context.enable_semantic_search,
                "summarization_trigger_ratio": self.context.summarization_trigger_ratio
            },
            "model": {
                "model_name": self.model.model_name,
                "temperature": self.model.temperature,
                "max_output_tokens": self.model.max_output_tokens,
                "api_key_configured": bool(self.model.api_key)
            },
            "monitoring": {
                "log_level": self.monitoring.log_level,
                "enable_performance_monitoring": self.monitoring.enable_performance_monitoring,
                "enable_token_tracking": self.monitoring.enable_token_tracking
            }
        }
    
    def validate(self) -> None:
        """Validate configuration settings."""
        if not self.model.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY must be set for LangChain integration")
        
        if self.memory.max_buffer_size <= 0:
            raise ValueError("LANGCHAIN_MAX_BUFFER_SIZE must be greater than 0")
        
        if self.context.max_tokens <= 0:
            raise ValueError("LANGCHAIN_MAX_TOKENS must be greater than 0")
        
        if not 0.0 <= self.context.relevance_threshold <= 1.0:
            raise ValueError("LANGCHAIN_RELEVANCE_THRESHOLD must be between 0.0 and 1.0")
        
        if not 0.0 <= self.context.summarization_trigger_ratio <= 1.0:
            raise ValueError("LANGCHAIN_SUMMARIZATION_TRIGGER_RATIO must be between 0.0 and 1.0")
        
        if not 0.0 <= self.model.temperature <= 2.0:
            raise ValueError("LANGCHAIN_TEMPERATURE must be between 0.0 and 2.0")


# Global configuration instance
_langchain_config: Optional[LangChainConfig] = None


def get_langchain_config() -> LangChainConfig:
    """
    Get the global LangChain configuration instance.
    
    Returns:
        LangChainConfig: The configuration instance
    """
    global _langchain_config
    if _langchain_config is None:
        _langchain_config = LangChainConfig.from_env()
        _langchain_config.validate()
    return _langchain_config


def reload_langchain_config() -> LangChainConfig:
    """
    Reload the LangChain configuration from environment variables.
    
    Returns:
        LangChainConfig: The reloaded configuration instance
    """
    global _langchain_config
    _langchain_config = LangChainConfig.from_env()
    _langchain_config.validate()
    return _langchain_config


def is_langchain_enabled() -> bool:
    """
    Check if LangChain integration is enabled.
    
    Returns:
        bool: True if LangChain is enabled, False otherwise
    """
    return get_langchain_config().enabled


def get_memory_config() -> MemoryConfig:
    """
    Get the memory configuration.
    
    Returns:
        MemoryConfig: The memory configuration
    """
    return get_langchain_config().memory


def get_context_config() -> ContextConfig:
    """
    Get the context optimization configuration.
    
    Returns:
        ContextConfig: The context configuration
    """
    return get_langchain_config().context


def get_model_config() -> LangChainModelConfig:
    """
    Get the model configuration.
    
    Returns:
        LangChainModelConfig: The model configuration
    """
    return get_langchain_config().model


def get_monitoring_config() -> LangChainMonitoringConfig:
    """
    Get the monitoring configuration.
    
    Returns:
        LangChainMonitoringConfig: The monitoring configuration
    """
    return get_langchain_config().monitoring