"""
Compatibility utilities for transitioning between direct API and LangChain integration.

This module provides utilities to ensure backward compatibility and smooth
migration from the existing GeminiClient to LangChain-based implementation.
"""

import os
from typing import Dict, Any, Optional
from .langchain_config import get_langchain_config, is_langchain_enabled
from .system_instructions import (
    get_system_instruction,
    get_langchain_enhanced_instruction,
    create_langchain_system_message_dict
)


def get_effective_system_instruction(instruction_type: Optional[str] = None) -> str:
    """
    Get the effective system instruction based on LangChain enablement.
    
    Args:
        instruction_type: The instruction type to retrieve
    
    Returns:
        str: The appropriate system instruction (enhanced if LangChain is enabled)
    """
    if is_langchain_enabled():
        return get_langchain_enhanced_instruction(instruction_type)
    else:
        return get_system_instruction(instruction_type)


def get_model_configuration() -> Dict[str, Any]:
    """
    Get the effective model configuration based on LangChain enablement.
    
    Returns:
        Dict[str, Any]: Model configuration parameters
    """
    if is_langchain_enabled():
        config = get_langchain_config()
        return {
            "model_name": config.model.model_name,
            "temperature": config.model.temperature,
            "max_output_tokens": config.model.max_output_tokens,
            "api_key": config.model.api_key,
            "langchain_enabled": True
        }
    else:
        return {
            "model_name": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "api_key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            "langchain_enabled": False
        }


def should_use_langchain() -> bool:
    """
    Determine if LangChain should be used based on configuration and availability.
    
    Returns:
        bool: True if LangChain should be used, False otherwise
    """
    try:
        return is_langchain_enabled() and get_langchain_config().model.api_key is not None
    except Exception:
        # If there's any issue with LangChain configuration, fall back to direct API
        return False


def get_client_type() -> str:
    """
    Get the client type that should be used.
    
    Returns:
        str: "langchain" or "direct"
    """
    return "langchain" if should_use_langchain() else "direct"


def get_migration_status() -> Dict[str, Any]:
    """
    Get the current migration status and configuration details.
    
    Returns:
        Dict[str, Any]: Migration status information
    """
    langchain_enabled = is_langchain_enabled()
    should_use_lc = should_use_langchain()
    
    status = {
        "langchain_configured": langchain_enabled,
        "langchain_available": should_use_lc,
        "active_client": get_client_type(),
        "system_instruction_type": os.getenv("SYSTEM_INSTRUCTION_TYPE", "default"),
        "model_name": os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    }
    
    if langchain_enabled:
        try:
            config = get_langchain_config()
            status.update({
                "memory_strategy": config.memory.strategy.value,
                "max_tokens": config.context.max_tokens,
                "monitoring_enabled": config.monitoring.enable_performance_monitoring
            })
        except Exception as e:
            status["langchain_error"] = str(e)
    
    return status


def validate_configuration() -> Dict[str, Any]:
    """
    Validate the current configuration and return any issues.
    
    Returns:
        Dict[str, Any]: Validation results with any errors or warnings
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        validation_result["errors"].append("No API key configured (GEMINI_API_KEY or GOOGLE_API_KEY)")
        validation_result["valid"] = False
    
    # Check LangChain configuration if enabled
    if is_langchain_enabled():
        try:
            config = get_langchain_config()
            config.validate()
        except Exception as e:
            validation_result["errors"].append(f"LangChain configuration error: {str(e)}")
            validation_result["valid"] = False
    
    # Check system instruction type
    instruction_type = os.getenv("SYSTEM_INSTRUCTION_TYPE", "default")
    from .system_instructions import validate_system_instruction_compatibility
    if not validate_system_instruction_compatibility(instruction_type):
        validation_result["warnings"].append(f"Unknown system instruction type: {instruction_type}")
    
    return validation_result


def get_feature_flags() -> Dict[str, bool]:
    """
    Get the current feature flag status.
    
    Returns:
        Dict[str, bool]: Feature flag status
    """
    return {
        "langchain_enabled": is_langchain_enabled(),
        "memory_management": is_langchain_enabled(),
        "context_optimization": is_langchain_enabled(),
        "performance_monitoring": is_langchain_enabled() and get_langchain_config().monitoring.enable_performance_monitoring,
        "token_tracking": is_langchain_enabled() and get_langchain_config().monitoring.enable_token_tracking
    }