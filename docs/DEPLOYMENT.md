# Oracle Chat AI - Simple Deployment Guide

## Overview

This guide provides straightforward deployment instructions for Oracle Chat AI.

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

# Optional (with defaults)
GEMINI_MODEL=gemini-2.5-flash
SYSTEM_INSTRUCTION_TYPE=default
LOG_LEVEL=info
ENVIRONMENT=production
DATABASE_URL=sqlite:///./oracle_sessions.db
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

# Expected response
{
  "status": "healthy",
  "services": {
    "gemini_api": "configured",
    "database": "connected",
    "logging": "active"
  },
  "session_metrics": {
    "total_sessions": 5,
    "active_sessions": 2,
    "total_messages": 47
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

2. **Database Issues**
   ```bash
   # Check database file
   ls -la oracle_sessions.db
   
   # Test database integrity
   sqlite3 oracle_sessions.db "PRAGMA integrity_check;"
   ```

3. **Port Conflicts**
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
```

### Performance Optimization

The application automatically optimizes performance through:

- **Session Caching**: Active Gemini sessions cached for 1 hour
- **Context Management**: Recent message context (last 10 messages) for efficiency
- **Database Indexing**: Optimized queries for session and message operations
- **Token Efficiency**: 60-80% reduction in API token usage

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

## Security Considerations

1. **Environment Variables**: Keep `.env` files secure and never commit them
2. **API Keys**: Rotate Gemini API keys regularly
3. **Database**: Ensure proper file permissions on SQLite database
4. **Logs**: Monitor logs for security issues and rotate regularly

## Scaling Considerations

For higher loads, consider:

1. **Database**: Migrate from SQLite to PostgreSQL
2. **Caching**: Implement Redis for session caching
3. **Load Balancing**: Use nginx or similar for multiple instances
4. **Monitoring**: Implement proper monitoring and alerting

This simple deployment guide covers the essential steps for getting Oracle Chat AI running in both development and production environments.