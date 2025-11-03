# Oracle Chat AI - Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting information for Oracle Chat AI, with special focus on persistent Gemini session management, performance issues, and common deployment problems.

## Table of Contents

1. [Session Management Issues](#session-management-issues)
2. [Performance Problems](#performance-problems)
3. [Database Issues](#database-issues)
4. [API and Connectivity Issues](#api-and-connectivity-issues)
5. [Monitoring and Diagnostics](#monitoring-and-diagnostics)
6. [Configuration Problems](#configuration-problems)
7. [Emergency Procedures](#emergency-procedures)

## Session Management Issues

### Persistent Sessions Not Working

**Symptoms:**
- Sessions are not being cached
- No performance improvements observed
- `used_persistent_session: false` in API responses

**Diagnosis:**
1. Check feature flag configuration:
   ```bash
   # Verify environment variables
   echo $USE_PERSISTENT_SESSIONS
   echo $GRADUAL_ROLLOUT_PERCENTAGE
   ```

2. Check session health endpoint:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/sessions
   ```

**Solutions:**
1. **Enable persistent sessions:**
   ```ini
   # In .env file
   USE_PERSISTENT_SESSIONS=true
   GRADUAL_ROLLOUT_PERCENTAGE=100
   ```

2. **Restart the application:**
   ```bash
   # Kill existing process and restart
   pkill -f "uvicorn main:app"
   cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Check logs for errors:**
   ```bash
   tail -f backend/logs/backend.log | grep -i "session"
   ```

### High Session Recovery Rate

**Symptoms:**
- Frequent session recovery operations
- `sessions_recovered` count increasing rapidly
- Performance degradation

**Diagnosis:**
1. Check session recovery health:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/sessions/recovery
   ```

2. Monitor session statistics:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/sessions/analytics
   ```

**Solutions:**
1. **Increase session timeout:**
   ```ini
   # Extend session lifetime (default: 3600 seconds)
   PERSISTENT_SESSION_TIMEOUT=7200
   ```

2. **Increase maximum sessions:**
   ```ini
   # Allow more sessions in memory
   MAX_PERSISTENT_SESSIONS=1000
   ```

3. **Check for memory pressure:**
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed
   ```

### Session Cleanup Issues

**Symptoms:**
- Memory usage continuously increasing
- `cleanup_frequency: overdue` in health checks
- Application becoming unresponsive

**Diagnosis:**
1. Check cleanup health:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/sessions/cleanup
   ```

2. Monitor memory usage:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed | jq '.system.memory_usage_percent'
   ```

**Solutions:**
1. **Reduce cleanup interval:**
   ```ini
   # More frequent cleanup (default: 300 seconds)
   CLEANUP_INTERVAL=120
   ```

2. **Manual cleanup trigger:**
   ```bash
   # Force cleanup via API (if implemented)
   curl -X POST http://localhost:8000/api/v1/sessions/cleanup
   ```

3. **Restart application if critical:**
   ```bash
   # Emergency restart
   sudo systemctl restart oracle-chat
   ```

### Session Cache Misses

**Symptoms:**
- Low cache hit ratio (< 50%)
- Poor performance despite persistent sessions enabled
- High `cache_misses` count

**Diagnosis:**
1. Check cache performance:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/sessions/performance
   ```

2. Analyze session patterns:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/sessions/usage?days=1
   ```

**Solutions:**
1. **Increase session timeout:**
   ```ini
   PERSISTENT_SESSION_TIMEOUT=7200  # 2 hours
   ```

2. **Optimize session usage patterns:**
   - Encourage users to continue conversations in same session
   - Avoid creating new sessions for related conversations

3. **Monitor session lifecycle:**
   ```bash
   tail -f backend/logs/backend.log | grep -E "(session_created|session_expired)"
   ```

## Performance Problems

### Slow Response Times

**Symptoms:**
- Response times > 2 seconds consistently
- `response_time_ms` high in API responses
- User complaints about slow AI responses

**Diagnosis:**
1. Check performance metrics:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/sessions/performance
   ```

2. Monitor system resources:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed
   ```

**Solutions:**
1. **Verify persistent sessions are working:**
   ```bash
   # Should show cache_hit: true for existing sessions
   curl -X POST http://localhost:8000/api/v1/sessions/1/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "test"}'
   ```

2. **Check Gemini API model configuration:**
   ```ini
   # Use faster model
   GEMINI_MODEL=gemini-2.5-flash-lite
   ```

3. **Optimize database queries:**
   ```bash
   # Check database performance
   sqlite3 oracle_sessions.db ".schema"
   sqlite3 oracle_sessions.db "EXPLAIN QUERY PLAN SELECT * FROM sessions LIMIT 10;"
   ```

### High Token Usage

**Symptoms:**
- API costs higher than expected
- `token_usage_optimized: false` in responses
- No significant token reduction observed

**Diagnosis:**
1. Check token optimization status:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/sessions/performance | jq '.estimated_improvements.token_usage_reduction_percent'
   ```

2. Verify session reuse:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/sessions/analytics | jq '.session_metrics.cache_hit_ratio'
   ```

**Solutions:**
1. **Ensure persistent sessions are enabled:**
   ```ini
   USE_PERSISTENT_SESSIONS=true
   ```

2. **Check session timeout configuration:**
   ```ini
   # Longer sessions = more reuse = better token optimization
   PERSISTENT_SESSION_TIMEOUT=7200
   ```

3. **Monitor session usage patterns:**
   ```bash
   curl http://localhost:8000/api/v1/monitoring/sessions/usage?days=7
   ```

### Memory Usage Issues

**Symptoms:**
- High memory usage (> 90%)
- Application crashes or becomes unresponsive
- `memory_status: critical` in health checks

**Diagnosis:**
1. Check system memory:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed | jq '.system'
   ```

2. Check session memory usage:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/sessions | jq '.session_management.memory_usage'
   ```

**Solutions:**
1. **Reduce maximum sessions:**
   ```ini
   MAX_PERSISTENT_SESSIONS=250  # Reduce from default 500
   ```

2. **Decrease session timeout:**
   ```ini
   PERSISTENT_SESSION_TIMEOUT=1800  # 30 minutes instead of 1 hour
   ```

3. **Increase cleanup frequency:**
   ```ini
   CLEANUP_INTERVAL=120  # 2 minutes instead of 5
   ```

## Database Issues

### Database Connection Failures

**Symptoms:**
- `database: unhealthy` in health checks
- SQLite errors in logs
- API endpoints returning 503 errors

**Diagnosis:**
1. Check database status:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed | jq '.database'
   ```

2. Test database file:
   ```bash
   ls -la oracle_sessions.db
   sqlite3 oracle_sessions.db ".tables"
   ```

**Solutions:**
1. **Check database file permissions:**
   ```bash
   chmod 664 oracle_sessions.db
   chown $USER:$USER oracle_sessions.db
   ```

2. **Recreate database if corrupted:**
   ```bash
   # Backup existing database
   cp oracle_sessions.db oracle_sessions.db.backup
   
   # Initialize new database
   uv run python backend/scripts/manage_db.py init
   ```

3. **Check disk space:**
   ```bash
   df -h .
   ```

### Session Data Corruption

**Symptoms:**
- Sessions exist in database but not accessible
- Inconsistent message counts
- Foreign key constraint errors

**Diagnosis:**
1. Check database integrity:
   ```bash
   sqlite3 oracle_sessions.db "PRAGMA integrity_check;"
   ```

2. Verify session relationships:
   ```bash
   sqlite3 oracle_sessions.db "SELECT s.id, s.message_count, COUNT(m.id) as actual_count FROM sessions s LEFT JOIN messages m ON s.id = m.session_id GROUP BY s.id HAVING s.message_count != actual_count;"
   ```

**Solutions:**
1. **Repair message counts:**
   ```bash
   uv run python backend/scripts/manage_db.py repair
   ```

2. **Clean orphaned records:**
   ```bash
   sqlite3 oracle_sessions.db "DELETE FROM messages WHERE session_id NOT IN (SELECT id FROM sessions);"
   ```

3. **Full database reset (last resort):**
   ```bash
   uv run python backend/scripts/manage_db.py reset
   ```

## API and Connectivity Issues

### Gemini API Errors

**Symptoms:**
- `GEMINI_API_ERROR` in API responses
- Authentication failures
- Rate limiting errors

**Diagnosis:**
1. Check API key configuration:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed | jq '.environment.gemini_api_key'
   ```

2. Test API connectivity:
   ```bash
   # Check logs for Gemini API errors
   tail -f backend/logs/backend.log | grep -i "gemini"
   ```

**Solutions:**
1. **Verify API key:**
   ```ini
   # Ensure valid API key in .env
   GEMINI_API_KEY=your_valid_api_key_here
   ```

2. **Check API quotas:**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Verify API key is active and has quota

3. **Handle rate limiting:**
   ```ini
   # Use different model if rate limited
   GEMINI_MODEL=gemini-2.5-flash-lite
   ```

### Network Connectivity Issues

**Symptoms:**
- Timeouts when calling Gemini API
- Intermittent connection failures
- DNS resolution errors

**Diagnosis:**
1. Test external connectivity:
   ```bash
   curl -I https://generativelanguage.googleapis.com/
   ```

2. Check DNS resolution:
   ```bash
   nslookup generativelanguage.googleapis.com
   ```

**Solutions:**
1. **Configure proxy if needed:**
   ```ini
   # Add proxy configuration
   HTTP_PROXY=http://proxy.company.com:8080
   HTTPS_PROXY=http://proxy.company.com:8080
   ```

2. **Adjust timeout settings:**
   ```ini
   # Increase timeout for slow networks
   GEMINI_API_TIMEOUT=30
   ```

## Monitoring and Diagnostics

### Health Check Failures

**Symptoms:**
- Health endpoints returning 503 errors
- Monitoring dashboards showing service down
- Inconsistent health status

**Diagnosis:**
1. Check all health endpoints:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/v1/monitoring/health/detailed
   curl http://localhost:8000/api/v1/monitoring/health/sessions
   ```

2. Check application logs:
   ```bash
   tail -f backend/logs/backend.log | grep -E "(ERROR|CRITICAL)"
   ```

**Solutions:**
1. **Restart monitoring services:**
   ```bash
   # Restart application
   sudo systemctl restart oracle-chat
   ```

2. **Reset monitoring statistics:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/monitoring/errors/reset
   curl -X POST http://localhost:8000/api/v1/monitoring/sessions/analytics/reset
   ```

### Log Analysis

**Common log patterns to monitor:**

1. **Session lifecycle events:**
   ```bash
   grep "session_created\|session_expired\|session_recovered" backend/logs/backend.log
   ```

2. **Performance issues:**
   ```bash
   grep "slow_response\|timeout\|performance_warning" backend/logs/backend.log
   ```

3. **Error patterns:**
   ```bash
   grep -E "ERROR|CRITICAL|EXCEPTION" backend/logs/backend.log | tail -20
   ```

## Configuration Problems

### Environment Variable Issues

**Symptoms:**
- Default values being used instead of configured values
- Feature flags not working
- Inconsistent behavior across environments

**Diagnosis:**
1. Check environment loading:
   ```bash
   # Verify .env file exists and is readable
   ls -la backend/.env
   cat backend/.env | grep -v "^#" | grep -v "^$"
   ```

2. Test configuration loading:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed | jq '.environment'
   ```

**Solutions:**
1. **Verify .env file format:**
   ```ini
   # Correct format (no spaces around =)
   USE_PERSISTENT_SESSIONS=true
   PERSISTENT_SESSION_TIMEOUT=3600
   
   # Incorrect format
   USE_PERSISTENT_SESSIONS = true  # Wrong: spaces around =
   ```

2. **Check file permissions:**
   ```bash
   chmod 644 backend/.env
   ```

3. **Restart application after changes:**
   ```bash
   # Environment changes require restart
   pkill -f "uvicorn main:app"
   cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Model Configuration Issues

**Symptoms:**
- Using wrong AI model
- Model not found errors
- Unexpected AI behavior

**Diagnosis:**
1. Check current model:
   ```bash
   curl http://localhost:8000/api/v1/monitoring/health/detailed | jq '.environment'
   ```

2. Test model availability:
   ```bash
   # Check logs for model initialization
   grep "model" backend/logs/backend.log | tail -5
   ```

**Solutions:**
1. **Use supported model:**
   ```ini
   # Supported models
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_MODEL=gemini-2.5-flash-lite
   GEMINI_MODEL=gemini-2.5-pro
   ```

2. **Verify API key has access to model:**
   - Check Google AI Studio for model availability
   - Some models may require special access

## Emergency Procedures

### Service Degradation Response

**When persistent sessions are causing issues:**

1. **Immediate fallback to stateless mode:**
   ```ini
   # Disable persistent sessions immediately
   USE_PERSISTENT_SESSIONS=false
   ```

2. **Restart application:**
   ```bash
   sudo systemctl restart oracle-chat
   ```

3. **Monitor recovery:**
   ```bash
   curl http://localhost:8000/health
   ```

### Memory Crisis Response

**When memory usage is critical (> 95%):**

1. **Emergency session cleanup:**
   ```bash
   # Force cleanup if endpoint exists
   curl -X POST http://localhost:8000/api/v1/sessions/cleanup/emergency
   ```

2. **Reduce session limits:**
   ```ini
   MAX_PERSISTENT_SESSIONS=50  # Drastically reduce
   PERSISTENT_SESSION_TIMEOUT=300  # 5 minutes
   ```

3. **Restart if necessary:**
   ```bash
   sudo systemctl restart oracle-chat
   ```

### Database Recovery

**When database is corrupted or inaccessible:**

1. **Backup current state:**
   ```bash
   cp oracle_sessions.db oracle_sessions.db.emergency_backup
   cp backend/logs/backend.log backend/logs/backend.log.emergency_backup
   ```

2. **Attempt repair:**
   ```bash
   sqlite3 oracle_sessions.db "PRAGMA integrity_check;"
   sqlite3 oracle_sessions.db "VACUUM;"
   ```

3. **Full reset if repair fails:**
   ```bash
   uv run python backend/scripts/manage_db.py reset
   ```

### Rollback Procedures

**When new deployment causes issues:**

1. **Disable new features:**
   ```ini
   USE_PERSISTENT_SESSIONS=false
   GRADUAL_ROLLOUT_PERCENTAGE=0
   ```

2. **Revert to previous version:**
   ```bash
   git checkout previous-stable-tag
   sudo systemctl restart oracle-chat
   ```

3. **Monitor stability:**
   ```bash
   watch -n 5 'curl -s http://localhost:8000/health | jq .status'
   ```

## Getting Help

### Log Collection for Support

When reporting issues, collect these logs:

```bash
# System information
curl http://localhost:8000/api/v1/monitoring/diagnostics > diagnostics.json

# Recent application logs
tail -1000 backend/logs/backend.log > recent_logs.txt

# Health status
curl http://localhost:8000/api/v1/monitoring/health/detailed > health_status.json

# Session statistics
curl http://localhost:8000/api/v1/monitoring/sessions/analytics > session_analytics.json
```

### Performance Baseline Collection

For performance issues:

```bash
# Performance metrics
curl http://localhost:8000/api/v1/monitoring/health/sessions/performance > performance_metrics.json

# Usage patterns
curl http://localhost:8000/api/v1/monitoring/sessions/usage?days=7 > usage_patterns.json

# System resources
curl http://localhost:8000/api/v1/monitoring/health/detailed | jq '.system' > system_resources.json
```

### Contact Information

- **GitHub Issues:** [Project Repository Issues](https://github.com/your-org/oracle-chat/issues)
- **Documentation:** [API Documentation](./API_DOCUMENTATION.md)
- **Deployment Guide:** [Deployment Guide](./DEPLOYMENT_GUIDE.md)