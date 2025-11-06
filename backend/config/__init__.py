# Configuration package for Oracle Chat backend

from .langchain_config import (
    LangChainConfig,
    MemoryConfig,
    ContextConfig,
    LangChainModelConfig,
    LangChainMonitoringConfig,
    MemoryStrategy,
    get_langchain_config,
    reload_langchain_config,
    is_langchain_enabled,
    get_memory_config,
    get_context_config,
    get_model_config,
    get_monitoring_config
)

from .system_instructions import (
    get_system_instruction,
    get_langchain_enhanced_instruction,
    create_langchain_system_message_dict,
    validate_system_instruction_compatibility,
    get_instruction_metadata,
    list_available_instructions,
    add_custom_instruction,
    create_domain_specific_instruction,
    SYSTEM_INSTRUCTIONS
)

from .compatibility import (
    get_effective_system_instruction,
    get_model_configuration,
    should_use_langchain,
    get_client_type,
    get_migration_status,
    validate_configuration,
    get_feature_flags
)

__all__ = [
    # LangChain configuration
    "LangChainConfig",
    "MemoryConfig", 
    "ContextConfig",
    "LangChainModelConfig",
    "LangChainMonitoringConfig",
    "MemoryStrategy",
    "get_langchain_config",
    "reload_langchain_config",
    "is_langchain_enabled",
    "get_memory_config",
    "get_context_config",
    "get_model_config",
    "get_monitoring_config",
    
    # System instructions
    "get_system_instruction",
    "get_langchain_enhanced_instruction",
    "create_langchain_system_message_dict",
    "validate_system_instruction_compatibility",
    "get_instruction_metadata",
    "list_available_instructions",
    "add_custom_instruction",
    "create_domain_specific_instruction",
    "SYSTEM_INSTRUCTIONS",
    
    # Compatibility utilities
    "get_effective_system_instruction",
    "get_model_configuration",
    "should_use_langchain",
    "get_client_type",
    "get_migration_status",
    "validate_configuration",
    "get_feature_flags"
]