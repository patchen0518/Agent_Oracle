# LangChain Integration Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting information for Oracle Chat AI's LangChain integration, covering common issues, diagnostic procedures, and resolution steps.

## Quick Diagnostic Checklist

### 1. Verify LangChain Installation

```bash
# Check LangChain dependencies
uv run python -c "import langchain; print(f'LangChain version: {langchain.__version__}')"
uv run python -c "import langchain_google_genai; print('LangChain Google GenAI available')"
uv run python -c "import langchain_core; print('LangChain Core available')"
```

### 2. Check Configuration

```bash
# Verify LangChain is enabled
grep LANGCHAIN_ENABLED backend/.env

# Check memory strategy configuration
grep LANGCHAIN_MEMORY_STRATEGY backend/.env

# Verify API key configuration
grep GEMINI_API_KEY backend/.env
```

### 3. Test Basic Functionality

```bash
# Test health endpoint
curl http://localhost:8000/health

# Create test session
curl -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"title": "LangChain Test Session"}'

# Send test message
curl -X POST http://localhost:8000/api/v1/sessions/1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, test LangChain integration"}'
```

## Common Issues and Solutions

### 1. LangChain Initialization Errors

#### Issue: `LANGCHAIN_INITIALIZATION_ERROR`

**Symptoms:**
- Application fails to start
- Error logs show LangChain model initialization failures
- Health endpoint shows LangChain as "disabled"

**Diagnostic Steps:**
```bash
# Check API key configuration
echo $GEMINI_API_KEY

# Verify LangChain configuration
uv run python -c "
from backend.config.langchain_config import get_langchain_config
config = get_langchain_config()
print(config.to_dict())
"

# Test ChatGoogleGenerativeAI initialization
uv run python -c "
from langchain_google_genai import ChatGoogleGenerativeAI
import os
chat = ChatGoogleGenerativeAI(
    model='gemini-2.5-flash',
    google_api_key=os.getenv('GEMINI_API_KEY')
)
print('LangChain model initialized successfully')
"
```

**Solutions:**
1. **Missing API Key:**
   ```bash
   # Set API key in environment
   export GEMINI_API_KEY=your_api_key_here
   
   # Or update .env file
   echo "GEMINI_API_KEY=your_api_key_here" >> backend/.env
   ```

2. **Invalid Model Configuration:**
   ```bash
   # Check supported models
   export GEMINI_MODEL=gemini-2.5-flash
   export LANGCHAIN_SUMMARY_MODEL=gemini-2.5-flash
   ```

3. **Network/API Issues:**
   ```bash
   # Test API connectivity
   curl -H "Authorization: Bearer $GEMINI_API_KEY" \
     "https://generativelanguage.googleapis.com/v1beta/models"
   ```

### 2. Memory Strategy Failures

#### Issue: `MEMORY_STRATEGY_ERROR`

**Symptoms:**
- Sessions fall back to basic buffer memory
- Error logs show memory strategy initialization failures
- Inconsistent conversation context

**Diagnostic Steps:**
```bash
# Check memory strategy configuration
grep LANGCHAIN_MEMORY_STRATEGY backend/.env

# Verify memory configuration parameters
grep -E "LANGCHAIN_MAX_BUFFER_SIZE|LANGCHAIN_MAX_TOKENS" backend/.env

# Test memory strategy initialization
uv run python -c "
from backend.services.memory_manager import MemoryManager
from backend.config.langchain_config import get_memory_config
config = get_memory_config()
memory = MemoryManager(session_id=1, memory_strategy=config.strategy.value)
print(f'Memory strategy {config.strategy.value} initialized successfully')
"
```

**Solutions:**
1. **Invalid Memory Strategy:**
   ```bash
   # Set valid memory strategy
   export LANGCHAIN_MEMORY_STRATEGY=hybrid  # buffer, summary, entity, hybrid
   ```

2. **Invalid Configuration Parameters:**
   ```bash
   # Fix configuration ranges
   export LANGCHAIN_MAX_BUFFER_SIZE=20  # Must be > 0
   export LANGCHAIN_MAX_TOKENS=4000     # Must be > 0
   export LANGCHAIN_RELEVANCE_THRESHOLD=0.7  # Must be 0.0-1.0
   ```

3. **Entity Extraction Issues:**
   ```bash
   # Disable entity extraction if causing issues
   export LANGCHAIN_ENTITY_EXTRACTION_ENABLED=false
   ```

### 3. Context Optimization Failures

#### Issue: `CONTEXT_OPTIMIZATION_ERROR`

**Symptoms:**
- Long conversations consume excessive tokens
- Summarization fails
- Context selection errors

**Diagnostic Steps:**
```bash
# Check context optimization configuration
grep -E "LANGCHAIN_MAX_TOKENS|LANGCHAIN_SUMMARIZATION" backend/.env

# Test context optimizer
uv run python -c "
from backend.services.context_optimizer import ContextOptimizer
from backend.config.langchain_config import get_context_config
config = get_context_config()
optimizer = ContextOptimizer(
    max_tokens=config.max_tokens,
    messages_to_keep=config.messages_to_keep_after_summary
)
print('Context optimizer initialized successfully')
"
```

**Solutions:**
1. **Summarization Model Issues:**
   ```bash
   # Use reliable model for summarization
   export LANGCHAIN_SUMMARY_MODEL=gemini-2.5-flash
   ```

2. **Token Limit Configuration:**
   ```bash
   # Adjust token limits
   export LANGCHAIN_MAX_TOKENS=4000
   export LANGCHAIN_SUMMARIZATION_TRIGGER_RATIO=0.8
   ```

3. **Disable Problematic Features:**
   ```bash
   # Disable semantic search if causing issues
   export LANGCHAIN_ENABLE_SEMANTIC_SEARCH=false
   ```

### 4. Entity Extraction Problems

#### Issue: `ENTITY_EXTRACTION_ERROR`

**Symptoms:**
- Entity extraction fails silently
- Important facts not remembered
- Performance degradation

**Diagnostic Steps:**
```bash
# Check entity extraction configuration
grep LANGCHAIN_ENTITY_EXTRACTION_ENABLED backend/.env

# Monitor entity extraction logs
grep "entity_extraction" backend/logs/backend.log | tail -10

# Test entity extraction manually
uv run python -c "
from backend.services.memory_manager import MemoryManager
memory = MemoryManager(session_id=1, memory_strategy='entity')
# Test with sample messages
print('Entity extraction test completed')
"
```

**Solutions:**
1. **Disable Entity Extraction:**
   ```bash
   # Temporarily disable if causing issues
   export LANGCHAIN_ENTITY_EXTRACTION_ENABLED=false
   ```

2. **Switch Memory Strategy:**
   ```bash
   # Use simpler memory strategy
   export LANGCHAIN_MEMORY_STRATEGY=buffer
   ```

### 5. Performance Issues

#### Issue: Slow Response Times or High Memory Usage

**Symptoms:**
- Increased response times compared to direct Gemini integration
- High memory usage
- Session timeouts

**Diagnostic Steps:**
```bash
# Monitor memory usage
ps aux | grep uvicorn

# Check session cache size
curl http://localhost:8000/health | jq '.langchain_metrics'

# Monitor token usage
grep "token_usage" backend/logs/backend.log | tail -5
```

**Solutions:**
1. **Optimize Memory Configuration:**
   ```bash
   # Reduce buffer sizes
   export LANGCHAIN_MAX_BUFFER_SIZE=10
   export LANGCHAIN_MESSAGES_TO_KEEP_AFTER_SUMMARY=10
   ```

2. **Adjust Summarization Frequency:**
   ```bash
   # Trigger summarization earlier
   export LANGCHAIN_SUMMARIZATION_TRIGGER_RATIO=0.6
   export LANGCHAIN_MAX_TOKENS_BEFORE_SUMMARY=2000
   ```

3. **Use Simpler Memory Strategy:**
   ```bash
   # Switch to buffer memory for better performance
   export LANGCHAIN_MEMORY_STRATEGY=buffer
   ```

## Fallback and Recovery Procedures

### 1. Immediate Fallback to Direct Gemini Integration

```bash
# Disable LangChain integration
export LANGCHAIN_ENABLED=false

# Restart application
pkill -f "uvicorn main:app"
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Partial Feature Rollback

```bash
# Keep LangChain but disable advanced features
export LANGCHAIN_MEMORY_STRATEGY=buffer
export LANGCHAIN_ENTITY_EXTRACTION_ENABLED=false
export LANGCHAIN_ENABLE_SEMANTIC_SEARCH=false

# Restart application
pkill -f "uvicorn main:app"
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. Configuration Reset

```bash
# Reset to minimal LangChain configuration
cat > backend/.env.langchain.minimal << 'EOF'
LANGCHAIN_ENABLED=true
LANGCHAIN_MEMORY_STRATEGY=buffer
LANGCHAIN_MAX_BUFFER_SIZE=10
LANGCHAIN_MAX_TOKENS=2000
LANGCHAIN_ENTITY_EXTRACTION_ENABLED=false
LANGCHAIN_ENABLE_SEMANTIC_SEARCH=false
LANGCHAIN_ENABLE_PERFORMANCE_MONITORING=true
EOF

# Apply minimal configuration
cat backend/.env.langchain.minimal >> backend/.env
```

## Monitoring and Logging

### 1. Enable Debug Logging

```bash
# Enable detailed LangChain logging
export LANGCHAIN_LOG_LEVEL=debug
export LOG_LEVEL=debug

# Monitor logs in real-time
tail -f backend/logs/backend.log | grep -E "langchain|memory|context"
```

### 2. Performance Monitoring

```bash
# Monitor LangChain metrics
curl http://localhost:8000/api/v1/monitoring/langchain

# Check token usage trends
grep "token_usage_reduction" backend/logs/backend.log | tail -10

# Monitor memory strategy performance
grep "memory_strategy_performance" backend/logs/backend.log | tail -10
```

### 3. Health Checks

```bash
# Comprehensive health check
curl http://localhost:8000/health | jq '.'

# LangChain-specific health check
curl http://localhost:8000/api/v1/monitoring/langchain/health
```

## Prevention and Best Practices

### 1. Configuration Validation

Always validate LangChain configuration before deployment:

```bash
# Validate configuration
uv run python -c "
from backend.config.langchain_config import get_langchain_config
config = get_langchain_config()
config.validate()
print('Configuration is valid')
"
```

### 2. Gradual Rollout

Use feature flags for gradual deployment:

1. Start with 10% of users
2. Monitor error rates and performance
3. Gradually increase percentage
4. Full rollout only after validation

### 3. Monitoring Setup

Implement comprehensive monitoring:

1. **Error Rate Monitoring**: Track LangChain-specific errors
2. **Performance Monitoring**: Monitor response times and token usage
3. **Memory Usage Monitoring**: Track memory strategy performance
4. **Fallback Monitoring**: Monitor fallback mechanism usage

### 4. Regular Maintenance

1. **Log Rotation**: Rotate LangChain logs regularly
2. **Configuration Review**: Review and optimize configuration monthly
3. **Performance Analysis**: Analyze token usage improvements
4. **Update Management**: Keep LangChain dependencies updated

## Getting Help

If issues persist after following this guide:

1. **Check Application Logs**: Review detailed error logs
2. **Verify Configuration**: Ensure all configuration parameters are correct
3. **Test Components**: Test individual LangChain components
4. **Fallback**: Use fallback mechanisms to maintain service availability
5. **Documentation**: Refer to LangChain official documentation for advanced troubleshooting

## Emergency Contacts and Escalation

For critical issues:

1. **Immediate**: Disable LangChain integration (`LANGCHAIN_ENABLED=false`)
2. **Fallback**: Ensure direct Gemini integration continues working
3. **Investigation**: Collect logs and configuration for analysis
4. **Resolution**: Apply fixes and gradually re-enable features