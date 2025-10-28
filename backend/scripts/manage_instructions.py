#!/usr/bin/env python3
"""
Utility script for managing system instructions.

This script helps you view, test, and manage different system instruction
configurations for Oracle Chat.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config.system_instructions import (
    get_system_instruction, 
    list_available_instructions,
    add_custom_instruction,
    create_domain_specific_instruction
)


def main():
    """Main function to demonstrate system instruction management."""
    
    print("=== Oracle Chat System Instructions Manager ===\n")
    
    # List available instructions
    print("Available System Instructions:")
    print("-" * 40)
    descriptions = list_available_instructions()
    for instruction_type, description in descriptions.items():
        print(f"• {instruction_type}: {description}")
    
    print("\n" + "=" * 50)
    
    # Show current default instruction
    print("\nCurrent Default Instruction:")
    print("-" * 30)
    try:
        current_instruction = get_system_instruction()
        # Show first 200 characters
        preview = current_instruction[:200] + "..." if len(current_instruction) > 200 else current_instruction
        print(preview)
    except Exception as e:
        print(f"Error getting instruction: {e}")
    
    print("\n" + "=" * 50)
    
    # Show how to get specific instructions
    print("\nExample: Getting Technical Instruction:")
    print("-" * 40)
    try:
        tech_instruction = get_system_instruction("technical")
        preview = tech_instruction[:200] + "..." if len(tech_instruction) > 200 else tech_instruction
        print(preview)
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    
    # Example of creating custom instruction
    print("\nExample: Creating Custom Domain-Specific Instruction:")
    print("-" * 55)
    custom_instruction = create_domain_specific_instruction(
        domain="healthcare",
        expertise_areas=["medical terminology", "patient care", "healthcare regulations"],
        tone="professional"
    )
    preview = custom_instruction[:200] + "..." if len(custom_instruction) > 200 else custom_instruction
    print(preview)
    
    print("\n" + "=" * 50)
    print("\nTo use different instructions:")
    print("1. Set SYSTEM_INSTRUCTION_TYPE in your .env file")
    print("2. Or modify the system_instructions.py file")
    print("3. Restart your backend server")
    print("\nExample .env setting:")
    print("SYSTEM_INSTRUCTION_TYPE=technical")


if __name__ == "__main__":
    main()