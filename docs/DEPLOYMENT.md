# Oracle Chat AI - Deployment Guide with LangChain Integration

## Overview

This guide provides comprehensive deployment instructions for Oracle Chat AI with LangChain integration, including configuration, monitoring, and troubleshooting for the intelligent memory management system.

## Prerequisites

- Python 3.14+ with `uv` package manager
- Node.js 18+ and `npm`
- Valid Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Quick Deployment

### 1. Setup Environment

```bash
# Clone and setup
git clone <repository-url>
cd oracle-chat

# Run automated setup
./scripts/dev-setup.sh

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env and add your GEMINI_API_KEY
```

### 2. Start Services

```bash
# Terminal 1: Backend
cd backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend  
cd frontend
npm run dev
```

### 3. Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# Test API
curl -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Session"}'
```

## Production Deployment

### Environment Configuration

Required environment variables:

```ini
# Required
GEMINI_API_KEY=your_api_key_here

# Core Application Configuration
GEMINI_MODEL=gemini-2.5-flash
SYSTEM_INSTRUCTION_TYPE=default
LOG_LEVEL=info
ENVIRONMENT=production
DATABASE_URL=sqlite:///./oracle_sessions.db

# LangChain Integration Configuration
LANGCHAIN_ENABLED=true
LANGCHAIN_MEMORY_STRATEGY=hybrid
LANGCHAIN_MAX_BUFFER_SIZE=20
LANGCHAIN_MAX_TOKENS_BEFORE_SUMMARY=4000
LANGCHAIN_ENTITY_EXTRACTION_ENABLED=true
LANGCHAIN_MAX_TOKENS=4000
LANGCHAIN_MESSAGES_TO_KEEP_AFTER_SUMMARY=20
LANGCHAIN_RELEVANCE_THRESHOLD=0.7
LANGCHAIN_ENABLE_SEMANTIC_SEARCH=true
LANGCHAIN_SUMMARIZATION_TRIGGER_RATIO=0.8
LANGCHAIN_SUMMARY_MODEL=gemini-2.5-flash
LANGCHAIN_TEMPERATURE=0.7
LANGCHAIN_MAX_OUTPUT_TOKENS=2048
LANGCHAIN_LOG_LEVEL=info
LANGCHAIN_ENABLE_PERFORMANCE_MONITORING=true
LANGCHAIN_ENABLE_TOKEN_TRACKING=true

# Feature Flag Overrides (optional)
ENABLE_LANGCHAIN=true
ENABLE_LANGCHAIN_MEMORY=true
ENABLE_CONTEXT_OPTIMIZATION=true
ENABLE_MEMORY_FALLBACK=true
ENABLE_HYBRID_PERSISTENCE=true
```

### Database Management

```bash
# View database stats
uv run python backend/scripts/manage_db.py stats

# Initialize database (if needed)
uv run python backend/scripts/manage_db.py init

# Backup database
cp oracle_sessions.db oracle_sessions_backup_$(date +%Y%m%d).db
```

### Health Monitoring

Monitor the application using the health endpoint:

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response with LangChain integration
{
  "status": "healthy",
  "services": {
    "gemini_api": "configured",
    "database": "connected",
    "logging": "active",
    "langchain": "enabled"
  },
  "session_metrics": {
    "total_sessions": 5,
    "active_sessions": 2,
    "total_messages": 47
  },
  "langchain_metrics": {
    "memory_strategy": "hybrid",
    "active_memory_sessions": 3,
    "token_usage_reduction": "72%",
    "entity_extraction_enabled": true
  }
}
```

### Troubleshooting

#### Common Issues

1. **API Key Issues**
   ```bash
   # Check if API key is configured
   grep GEMINI_API_KEY backend/.env
   
   # Test API connectivity
   curl -I https://generativelanguage.googleapis.com/
   ```

2. **LangChain Integration Issues**
   ```bash
   # Check LangChain configuration
   grep LANGCHAIN_ENABLED backend/.env
   
   # Verify LangChain dependencies
   uv run python -c "import langchain; print('LangChain installed')"
   
   # Test LangChain model initialization
   uv run python -c "from langchain_google_genai import ChatGoogleGenerativeAI; print('LangChain Google GenAI available')"
   ```

3. **Memory Strategy Issues**
   ```bash
   # Check memory strategy configuration
   grep LANGCHAIN_MEMORY_STRATEGY backend/.env
   
   # Verify memory configuration values
   grep LANGCHAIN_MAX_BUFFER_SIZE backend/.env
   grep LANGCHAIN_MAX_TOKENS backend/.env
   ```

4. **Database Issues**
   ```bash
   # Check database file
   ls -la oracle_sessions.db
   
   # Test database integrity
   sqlite3 oracle_sessions.db "PRAGMA integrity_check;"
   ```

5. **Port Conflicts**
   ```bash
   # Check if ports are in use
   netstat -tlnp | grep :8000
   netstat -tlnp | grep :5173
   ```

#### Log Analysis

```bash
# Check application logs
tail -f backend/logs/backend.log

# Filter for errors
grep -E "ERROR|CRITICAL" backend/logs/backend.log

# Monitor session activity
grep "session" backend/logs/backend.log | tail -10

# Monitor LangChain operations
grep "langchain" backend/logs/backend.log | tail -10

# Check memory strategy usage
grep "memory_strategy" backend/logs/backend.log

# Monitor token usage improvements
grep "token_usage" backend/logs/backend.log

# Check entity extraction activity
grep "entity_extraction" backend/logs/backend.log

# Monitor context optimization
grep "context_optimization" backend/logs/backend.log
```

### Performance Optimization

The application automatically optimizes performance through LangChain integration:

- **Intelligent Memory Management**: Smart memory strategies (buffer, summary, entity, hybrid)
- **Context Optimization**: Automatic summarization and relevance-based context selection
- **Entity Extraction**: Remembers important facts without storing full conversation history
- **Session Caching**: Active LangChain sessions cached for 1 hour
- **Database Indexing**: Optimized queries for session and message operations
- **Token Efficiency**: 60-80% reduction in API token usage through smart memory strategies
- **Fallback Mechanisms**: Graceful degradation when advanced features fail

#### LangChain Performance Tuning

1. **Memory Strategy Selection**:
   - `buffer`: Best for short conversations (< 20 messages)
   - `summary`: Optimal for long conversations with summarization
   - `entity`: Ideal for fact-heavy conversations
   - `hybrid`: Balanced approach (recommended for production)

2. **Token Management**:
   - Adjust `LANGCHAIN_MAX_TOKENS` based on model limits
   - Tune `LANGCHAIN_SUMMARIZATION_TRIGGER_RATIO` for summarization frequency
   - Configure `LANGCHAIN_MESSAGES_TO_KEEP_AFTER_SUMMARY` for context preservation

3. **Context Optimization**:
   - Set `LANGCHAIN_RELEVANCE_THRESHOLD` higher for more selective context
   - Enable `LANGCHAIN_ENABLE_SEMANTIC_SEARCH` for better context selection
   - Adjust `LANGCHAIN_MAX_BUFFER_SIZE` based on conversation patterns

### Backup and Recovery

#### Regular Backups

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp oracle_sessions.db "backups/oracle_sessions_${DATE}.db"
cp backend/.env "backups/config_${DATE}.env"
echo "Backup created: ${DATE}"
EOF

chmod +x backup.sh
```

#### Recovery

```bash
# Restore from backup
BACKUP_DATE="20250127_120000"  # Replace with actual backup date
cp "backups/oracle_sessions_${BACKUP_DATE}.db" oracle_sessions.db
cp "backups/config_${BACKUP_DATE}.env" backend/.env

# Restart application
pkill -f "uvicorn main:app"
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

## LangChain Deployment Considerations

### Feature Flag Rollout Strategy

Deploy LangChain integration gradually using feature flags:

1. **Initial Deployment** (0-10% users):
   ```ini
   LANGCHAIN_ENABLED=true
   ENABLE_LANGCHAIN=true
   # Feature flag: langchain_integration at 10%
   ```

2. **Memory Strategy Testing** (10-25% users):
   ```ini
   ENABLE_LANGCHAIN_MEMORY=true
   # Feature flag: langchain_memory_strategies enabled
   ```

3. **Context Optimization** (25-50% users):
   ```ini
   ENABLE_CONTEXT_OPTIMIZATION=true
   # Feature flag: context_optimization at 50%
   ```

4. **Full Rollout** (100% users):
   ```ini
   # All LangChain features enabled
   ENABLE_HYBRID_PERSISTENCE=true
   ```

### Monitoring LangChain Integration

Monitor LangChain performance and health:

```bash
# Check LangChain integration status
curl http://localhost:8000/api/v1/monitoring/langchain

# Monitor memory strategy performance
curl http://localhost:8000/api/v1/monitoring/memory-strategies

# Check token usage improvements
curl http://localhost:8000/api/v1/monitoring/token-usage

# Monitor entity extraction metrics
curl http://localhost:8000/api/v1/monitoring/entity-extraction
```

### Rollback Procedures

If LangChain integration issues occur:

1. **Immediate Rollback**:
   ```bash
   # Disable LangChain integration
   export LANGCHAIN_ENABLED=false
   export ENABLE_LANGCHAIN=false
   
   # Restart application
   pkill -f "uvicorn main:app"
   cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Partial Rollback**:
   ```bash
   # Disable specific features
   export ENABLE_LANGCHAIN_MEMORY=false
   export ENABLE_CONTEXT_OPTIMIZATION=false
   
   # Keep basic LangChain integration
   export LANGCHAIN_MEMORY_STRATEGY=buffer
   ```

3. **Configuration Rollback**:
   ```bash
   # Restore previous configuration
   cp backups/config_backup.env backend/.env
   
   # Restart with previous settings
   cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Security Considerations

1. **Environment Variables**: Keep `.env` files secure and never commit them
2. **API Keys**: Rotate Gemini API keys regularly
3. **Database**: Ensure proper file permissions on SQLite database
4. **Logs**: Monitor logs for security issues and rotate regularly
5. **LangChain Configuration**: Validate LangChain configuration parameters
6. **Memory Management**: Monitor memory usage for potential security issues

## Scaling Considerations

For higher loads, consider:

1. **Database**: Migrate from SQLite to PostgreSQL
2. **Caching**: Implement Redis for session caching
3. **Load Balancing**: Use nginx or similar for multiple instances
4. **Monitoring**: Implement proper monitoring and alerting

This simple deployment guide covers the essential steps for getting Oracle Chat AI running in both development and production environments.