# System Instructions Configuration

This directory contains configuration files for Oracle Chat's system instructions, which define the AI's behavior, personality, and capabilities.

## Available Instruction Types

- **default**: General purpose helpful assistant
- **professional**: Business and productivity focused assistant  
- **technical**: Software development and technology specialist
- **creative**: Creative and engaging conversational assistant
- **educational**: Teaching and learning focused assistant

## Usage

### Method 1: Environment Variable (Recommended)
Set the instruction type in your `.env` file:
```env
SYSTEM_INSTRUCTION_TYPE=technical
```

### Method 2: Programmatic Selection
```python
from backend.config.system_instructions import get_system_instruction

# Get specific instruction
instruction = get_system_instruction("professional")

# Get default (respects environment variable)
instruction = get_system_instruction()
```

## Adding Custom Instructions

### Option 1: Edit system_instructions.py
Add your custom instruction to the `SYSTEM_INSTRUCTIONS` dictionary:

```python
CUSTOM_INSTRUCTION = """Your custom system instruction here..."""

SYSTEM_INSTRUCTIONS["custom"] = CUSTOM_INSTRUCTION
```

### Option 2: Runtime Addition
```python
from backend.config.system_instructions import add_custom_instruction

add_custom_instruction("my_custom", "Your instruction text here...")
```

### Option 3: Domain-Specific Generator
```python
from backend.config.system_instructions import create_domain_specific_instruction

instruction = create_domain_specific_instruction(
    domain="finance",
    expertise_areas=["investment analysis", "risk management", "financial planning"],
    tone="professional"
)
```

## Testing Instructions

Run the management script to preview instructions:
```bash
cd backend
python scripts/manage_instructions.py
```

## File Structure

```
backend/config/
├── __init__.py
├── system_instructions.py  # Main configuration file
└── README.md              # This file

backend/scripts/
└── manage_instructions.py  # Utility script for testing
```