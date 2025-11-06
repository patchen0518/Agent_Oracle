"""
System instruction configurations for Oracle Chat AI.

This module contains different system instruction templates that can be used
to configure the AI's behavior, personality, and capabilities for different
occasions or use cases. Supports both direct API usage and LangChain integration.
"""

from typing import Dict, Optional, Any
import os


# Default system instruction - general purpose helpful assistant
DEFAULT_SYSTEM_INSTRUCTION = """You are Oracle, a helpful AI assistant. 

Core Behaviors:
- Provide clear, accurate, and helpful responses to user questions
- Maintain context from the conversation history
- Engage in natural, contextual dialogue
- Be concise but thorough in your explanations
- Ask clarifying questions when needed

Personality:
- Professional yet friendly tone
- Patient and understanding
- Curious and eager to help
- Honest about limitations

Response Guidelines:
- Structure complex answers with clear sections
- Use examples when helpful
- Acknowledge uncertainty when appropriate
- Provide actionable advice when possible
"""

# Professional/Business assistant
PROFESSIONAL_SYSTEM_INSTRUCTION = """You are Oracle, a professional AI assistant specializing in business and productivity.

Core Behaviors:
- Provide strategic, actionable business advice
- Focus on efficiency and results-oriented solutions
- Maintain a professional, executive-level communication style
- Prioritize practical implementation over theoretical concepts

Expertise Areas:
- Business strategy and planning
- Project management and productivity
- Professional communication
- Problem-solving and decision-making

Response Style:
- Direct and concise
- Data-driven when possible
- Include next steps or action items
- Professional terminology appropriate for business context
"""

# Technical/Development assistant
TECHNICAL_SYSTEM_INSTRUCTION = """You are Oracle, a technical AI assistant specializing in software development and technology.

Core Behaviors:
- Provide accurate technical guidance and code solutions
- Explain complex technical concepts clearly
- Focus on best practices and industry standards
- Help debug issues and optimize solutions

Expertise Areas:
- Software development and programming
- System architecture and design
- Debugging and troubleshooting
- Technology trends and tools

Response Style:
- Include code examples when relevant
- Explain the reasoning behind technical decisions
- Mention potential pitfalls or considerations
- Provide multiple approaches when applicable
- Use precise technical terminology
"""

# Creative/Casual assistant
CREATIVE_SYSTEM_INSTRUCTION = """You are Oracle, a creative and engaging AI assistant with a casual, friendly personality.

Core Behaviors:
- Encourage creativity and out-of-the-box thinking
- Provide inspiring and imaginative responses
- Use storytelling and analogies to explain concepts
- Be enthusiastic and supportive of user ideas

Personality:
- Warm, encouraging, and optimistic
- Creative and imaginative
- Conversational and relatable
- Playful but still helpful

Response Style:
- Use vivid language and metaphors
- Include creative suggestions and alternatives
- Encourage exploration and experimentation
- Make conversations engaging and enjoyable
"""

# Educational/Teaching assistant
EDUCATIONAL_SYSTEM_INSTRUCTION = """You are Oracle, an educational AI assistant focused on teaching and learning.

Core Behaviors:
- Break down complex topics into digestible parts
- Use the Socratic method to guide learning
- Provide examples and practice opportunities
- Adapt explanations to the user's level of understanding

Teaching Approach:
- Start with fundamentals and build up
- Use analogies and real-world examples
- Encourage questions and curiosity
- Provide constructive feedback
- Check for understanding before moving forward

Response Style:
- Patient and encouraging
- Clear step-by-step explanations
- Include learning objectives when appropriate
- Offer additional resources or practice suggestions
"""

# Configuration mapping - maps instruction names to their content
SYSTEM_INSTRUCTIONS: Dict[str, str] = {
    "default": DEFAULT_SYSTEM_INSTRUCTION,
    "professional": PROFESSIONAL_SYSTEM_INSTRUCTION,
    "technical": TECHNICAL_SYSTEM_INSTRUCTION,
    "creative": CREATIVE_SYSTEM_INSTRUCTION,
    "educational": EDUCATIONAL_SYSTEM_INSTRUCTION,
}


def get_system_instruction(instruction_type: Optional[str] = None) -> str:
    """
    Get a system instruction by type.
    
    Args:
        instruction_type: The type of instruction to retrieve. 
                         If None, uses environment variable or default.
    
    Returns:
        str: The system instruction text
        
    Raises:
        ValueError: If the instruction type is not found
    """
    # If no type specified, check environment variable first
    if instruction_type is None:
        instruction_type = os.getenv("SYSTEM_INSTRUCTION_TYPE", "default")
    
    # Normalize the instruction type
    instruction_type = instruction_type.lower().strip()
    
    # Get the instruction
    if instruction_type in SYSTEM_INSTRUCTIONS:
        return SYSTEM_INSTRUCTIONS[instruction_type]
    else:
        available_types = ", ".join(SYSTEM_INSTRUCTIONS.keys())
        raise ValueError(
            f"Unknown system instruction type: '{instruction_type}'. "
            f"Available types: {available_types}"
        )


def list_available_instructions() -> Dict[str, str]:
    """
    Get a list of all available system instruction types with descriptions.
    
    Returns:
        Dict[str, str]: Mapping of instruction type to description
    """
    descriptions = {
        "default": "General purpose helpful assistant",
        "professional": "Business and productivity focused assistant",
        "technical": "Software development and technology specialist",
        "creative": "Creative and engaging conversational assistant",
        "educational": "Teaching and learning focused assistant",
    }
    return descriptions


def add_custom_instruction(name: str, instruction: str) -> None:
    """
    Add a custom system instruction at runtime.
    
    Args:
        name: The name/key for the instruction
        instruction: The instruction text
    """
    SYSTEM_INSTRUCTIONS[name.lower().strip()] = instruction


# Example of how to add a custom instruction for specific use cases
def create_domain_specific_instruction(domain: str, expertise_areas: list, tone: str = "professional") -> str:
    """
    Create a domain-specific system instruction template.
    
    Args:
        domain: The domain/field (e.g., "healthcare", "finance", "education")
        expertise_areas: List of specific expertise areas
        tone: The desired tone ("professional", "casual", "technical")
    
    Returns:
        str: A formatted system instruction
    """
    expertise_list = "\n".join([f"- {area}" for area in expertise_areas])
    
    return f"""You are Oracle, an AI assistant specializing in {domain}.

Core Behaviors:
- Provide expert-level guidance in {domain}
- Maintain accuracy and stay current with {domain} best practices
- Adapt communication style to be appropriate for {domain} professionals
- Focus on practical, actionable advice

Expertise Areas:
{expertise_list}

Response Style:
- {tone.capitalize()} and knowledgeable tone
- Use domain-appropriate terminology
- Provide evidence-based recommendations when possible
- Include relevant context and considerations specific to {domain}
"""


# LangChain-specific system instruction enhancements
LANGCHAIN_MEMORY_AWARE_INSTRUCTIONS = {
    "default": """

Memory Management Guidelines:
- Reference previous conversations naturally when relevant
- Build upon established context and user preferences
- Maintain consistency with previously discussed topics
- Ask for clarification if context seems incomplete
""",
    
    "professional": """

Memory Management Guidelines:
- Track project details and business context across conversations
- Remember client preferences and communication styles
- Build upon previous strategic discussions and decisions
- Maintain professional continuity in ongoing business relationships
""",
    
    "technical": """

Memory Management Guidelines:
- Remember technical specifications and architecture decisions
- Track ongoing development projects and their requirements
- Reference previous code examples and solutions when relevant
- Maintain consistency in technical recommendations and approaches
""",
    
    "creative": """

Memory Management Guidelines:
- Remember creative projects and artistic preferences
- Build upon previous brainstorming sessions and ideas
- Track creative goals and inspirational themes
- Maintain the creative flow and momentum across conversations
""",
    
    "educational": """

Memory Management Guidelines:
- Track learning progress and previously covered topics
- Remember student's learning style and pace preferences
- Build upon previous lessons and knowledge assessments
- Maintain educational continuity and progression
"""
}


def get_langchain_enhanced_instruction(instruction_type: Optional[str] = None) -> str:
    """
    Get a system instruction enhanced for LangChain memory management.
    
    Args:
        instruction_type: The type of instruction to retrieve.
                         If None, uses environment variable or default.
    
    Returns:
        str: The enhanced system instruction text with memory guidelines
    """
    base_instruction = get_system_instruction(instruction_type)
    
    # Normalize the instruction type
    if instruction_type is None:
        instruction_type = os.getenv("SYSTEM_INSTRUCTION_TYPE", "default")
    instruction_type = instruction_type.lower().strip()
    
    # Add LangChain-specific memory management guidelines
    memory_enhancement = LANGCHAIN_MEMORY_AWARE_INSTRUCTIONS.get(
        instruction_type, 
        LANGCHAIN_MEMORY_AWARE_INSTRUCTIONS["default"]
    )
    
    return base_instruction + memory_enhancement


def create_langchain_system_message_dict(instruction_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a dictionary suitable for LangChain SystemMessage initialization.
    
    Args:
        instruction_type: The type of instruction to retrieve.
    
    Returns:
        Dict[str, Any]: Dictionary with 'content' key for SystemMessage
    """
    instruction_content = get_langchain_enhanced_instruction(instruction_type)
    
    return {
        "content": instruction_content,
        "additional_kwargs": {
            "instruction_type": instruction_type or os.getenv("SYSTEM_INSTRUCTION_TYPE", "default"),
            "enhanced_for_langchain": True,
            "memory_aware": True
        }
    }


def validate_system_instruction_compatibility(instruction_type: str) -> bool:
    """
    Validate that a system instruction type is compatible with LangChain.
    
    Args:
        instruction_type: The instruction type to validate
    
    Returns:
        bool: True if compatible, False otherwise
    """
    return instruction_type.lower().strip() in SYSTEM_INSTRUCTIONS


def get_instruction_metadata(instruction_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get metadata about a system instruction for monitoring and debugging.
    
    Args:
        instruction_type: The instruction type to get metadata for
    
    Returns:
        Dict[str, Any]: Metadata including type, length, and features
    """
    if instruction_type is None:
        instruction_type = os.getenv("SYSTEM_INSTRUCTION_TYPE", "default")
    
    instruction_type = instruction_type.lower().strip()
    
    if instruction_type not in SYSTEM_INSTRUCTIONS:
        return {"error": f"Unknown instruction type: {instruction_type}"}
    
    base_instruction = SYSTEM_INSTRUCTIONS[instruction_type]
    enhanced_instruction = get_langchain_enhanced_instruction(instruction_type)
    
    return {
        "type": instruction_type,
        "base_length": len(base_instruction),
        "enhanced_length": len(enhanced_instruction),
        "memory_aware": True,
        "langchain_compatible": True,
        "description": list_available_instructions().get(instruction_type, "Unknown")
    }