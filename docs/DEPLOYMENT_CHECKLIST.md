# Oracle Chat AI - Deployment Checklist and Validation Steps

## Overview

This comprehensive checklist ensures safe and successful deployment of Oracle Chat AI with persistent Gemini sessions. Follow each step in order and validate completion before proceeding.

## Pre-Deployment Checklist

### Environment Preparation

#### System Requirements Verification
- [ ] **Python 3.14+** installed and accessible
  ```bash
  python --version  # Should show 3.14+
  which uv  # Should return path to uv
  ```

- [ ] **Node.js 18+** and npm installed
  ```bash
  node --version  # Should show 18+
  npm --version   # Should show compatible version
  ```

- [ ] **SQLite 3.x** available
  ```bash
  sqlite3 --version  # Should show version info
  ```

- [ ] **Sufficient disk space** (minimum 2GB free)
  ```bash
  df -h .  # Check available space
  ```

- [ ] **Adequate memory** (minimum 4GB RAM recommended)
  ```bash
  free -h  # Check available memory
  ```

#### Dependencies and Tools
- [ ] **Git** configured and accessible
  ```bash
  git --version
  git config --get user.name
  git config --get user.email
  ```

- [ ] **System permissions** for service management
  ```bash
  sudo systemctl --version  # Verify systemd access
  ```

- [ ] **Network connectivity** to external services
  ```bash
  curl -I https://generativelanguage.googleapis.com/
  curl -I https://registry.npmjs.org/
  ```

### Configuration Validation

#### Environment Variables
- [ ] **Gemini API key** configured and valid
  ```bash
  # Check API key is set (don't echo the actual key)
  [ -n "$GEMINI_API_KEY" ] && echo "API key is set" || echo "API key missing"
  
  # Test API connectivity (basic test)
  curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | jq '.models[0].name' || echo "API test failed"
  ```

- [ ] **Required environment variables** present
  ```bash
  # Check required variables
  required_vars=("GEMINI_API_KEY" "GEMINI_MODEL" "DATABASE_URL")
  for var in "${required_vars[@]}"; do
    [ -n "${!var}" ] && echo "$var: ✓" || echo "$var: ✗ MISSING"
  done
  ```

- [ ] **Feature flag configuration** validated
  ```bash
  # Verify feature flags are properly set
  echo "USE_PERSISTENT_SESSIONS: $(grep USE_PERSISTENT_SESSIONS backend/.env | cut -d'=' -f2)"
  echo "GRADUAL_ROLLOUT_PERCENTAGE: $(grep GRADUAL_ROLLOUT_PERCENTAGE backend/.env | cut -d'=' -f2)"
  ```

#### Database Preparation
- [ ] **Database file** accessible and writable
  ```bash
  # Check database file
  if [ -f oracle_sessions.db ]; then
    echo "Database exists: ✓"
    sqlite3 oracle_sessions.db "PRAGMA integrity_check;" | head -1
  else
    echo "Database will be created on first run"
  fi
  ```

- [ ] **Database backup** created
  ```bash
  # Create pre-deployment backup
  if [ -f oracle_sessions.db ]; then
    BACKUP_NAME="oracle_sessions_pre_deployment_$(date +%Y%m%d_%H%M%S).db"
    cp oracle_sessions.db "backups/$BACKUP_NAME"
    echo "Backup created: $BACKUP_NAME"
  fi
  ```

### Code and Dependencies

#### Source Code Validation
- [ ] **Correct version/branch** checked out
  ```bash
  git branch --show-current
  git describe --tags --always
  git status --porcelain  # Should be clean
  ```

- [ ] **Backend dependencies** installed and up-to-date
  ```bash
  cd backend
  uv sync --check  # Verify dependencies are in sync
  uv run python -c "import google.genai; print('Gemini SDK imported successfully')"
  ```

- [ ] **Frontend dependencies** installed
  ```bash
  cd frontend
  npm ci  # Clean install
  npm audit --audit-level=high  # Check for security issues
  ```

#### Build Validation
- [ ] **Frontend build** successful
  ```bash
  cd frontend
  npm run build
  [ -d dist ] && echo "Frontend build: ✓" || echo "Frontend build: ✗ FAILED"
  ```

- [ ] **Backend imports** working
  ```bash
  cd backend
  uv run python -c "
  from main import app
  from services.gemini_client import GeminiClient
  from services.session_service import SessionService
  print('All imports successful')
  "
  ```

### Testing and Quality Assurance

#### Test Suite Execution
- [ ] **Backend tests** passing
  ```bash
  cd backend
  uv run pytest --tb=short -v
  echo "Backend test exit code: $?"
  ```

- [ ] **Frontend tests** passing
  ```bash
  cd frontend
  npm test -- --run
  echo "Frontend test exit code: $?"
  ```

- [ ] **Integration tests** successful
  ```bash
  cd backend
  uv run pytest backend/tests/test_system_integration.py -v
  ```

#### Security Validation
- [ ] **No secrets** in code or logs
  ```bash
  # Check for potential secrets in code
  grep -r "api_key\|password\|secret" --exclude-dir=.git --exclude="*.md" . | grep -v "GEMINI_API_KEY" || echo "No secrets found in code"
  ```

- [ ] **Environment file** properly secured
  ```bash
  ls -la backend/.env  # Should not be world-readable
  [ $(stat -c %a backend/.env) -le 600 ] && echo "Environment file permissions: ✓" || echo "Environment file permissions: ✗ TOO PERMISSIVE"
  ```

### Backup and Recovery Preparation

#### Backup Creation
- [ ] **Complete system backup** created
  ```bash
  BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
  
  # Database backup
  [ -f oracle_sessions.db ] && cp oracle_sessions.db "backups/oracle_sessions_${BACKUP_DATE}.db"
  
  # Configuration backup
  mkdir -p "backups/config_${BACKUP_DATE}"
  cp backend/.env "backups/config_${BACKUP_DATE}/"
  cp -r backend/config/ "backups/config_${BACKUP_DATE}/" 2>/dev/null || true
  
  # Application state backup
  tar -czf "backups/app_state_${BACKUP_DATE}.tar.gz" backend/logs/ oracle_sessions.db backend/.env 2>/dev/null || true
  
  echo "Backup created with timestamp: $BACKUP_DATE"
  ```

- [ ] **Backup integrity** verified
  ```bash
  # Verify database backup
  LATEST_DB_BACKUP=$(ls -t backups/oracle_sessions_*.db | head -1)
  if [ -f "$LATEST_DB_BACKUP" ]; then
    sqlite3 "$LATEST_DB_BACKUP" "PRAGMA integrity_check;" | head -1
  fi
  ```

#### Recovery Plan Validation
- [ ] **Rollback procedures** tested (in staging)
- [ ] **Recovery scripts** executable and accessible
  ```bash
  # Check rollback scripts exist and are executable
  scripts=("rollback_features.sh" "rollback_version.sh" "emergency_response.sh")
  for script in "${scripts[@]}"; do
    if [ -x "scripts/$script" ]; then
      echo "$script: ✓"
    else
      echo "$script: ✗ MISSING OR NOT EXECUTABLE"
    fi
  done
  ```

## Deployment Execution Checklist

### Phase 1: Infrastructure Deployment

#### Service Preparation
- [ ] **Current service** stopped gracefully
  ```bash
  sudo systemctl stop oracle-chat || echo "Service not running"
  sleep 5
  pgrep -f "uvicorn main:app" || echo "Application stopped"
  ```

- [ ] **Port availability** confirmed
  ```bash
  # Check if port 8000 is free
  netstat -tlnp | grep :8000 || echo "Port 8000 is available"
  ```

#### Code Deployment
- [ ] **New code** deployed
  ```bash
  git pull origin main
  git checkout v1.2.0  # Or specific deployment tag
  echo "Deployed version: $(git describe --tags --always)"
  ```

- [ ] **Dependencies** updated
  ```bash
  cd backend && uv sync
  cd ../frontend && npm ci && npm run build
  ```

#### Configuration Application
- [ ] **Feature flags** set for safe deployment
  ```bash
  # Ensure features start disabled
  grep "USE_PERSISTENT_SESSIONS=false" backend/.env || echo "WARNING: Persistent sessions not disabled"
  grep "GRADUAL_ROLLOUT_PERCENTAGE=0" backend/.env || echo "WARNING: Rollout not set to 0%"
  ```

- [ ] **Configuration** validated
  ```bash
  ./scripts/validate_config.sh
  ```

#### Service Startup
- [ ] **Application** started successfully
  ```bash
  sudo systemctl start oracle-chat
  sleep 10
  systemctl is-active oracle-chat
  ```

- [ ] **Process** running correctly
  ```bash
  pgrep -f "uvicorn main:app" && echo "Application process running"
  ```

### Phase 2: Basic Validation

#### Health Checks
- [ ] **Basic health** endpoint responding
  ```bash
  curl -f http://localhost:8000/health
  echo "Health check exit code: $?"
  ```

- [ ] **Detailed health** check passing
  ```bash
  HEALTH_STATUS=$(curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq -r '.status')
  echo "Detailed health status: $HEALTH_STATUS"
  [ "$HEALTH_STATUS" = "healthy" ] && echo "✓" || echo "✗ UNHEALTHY"
  ```

#### Database Connectivity
- [ ] **Database** accessible and healthy
  ```bash
  DB_STATUS=$(curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq -r '.database.status')
  echo "Database status: $DB_STATUS"
  [ "$DB_STATUS" = "healthy" ] && echo "✓" || echo "✗ UNHEALTHY"
  ```

#### API Functionality
- [ ] **Session creation** working
  ```bash
  SESSION_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/sessions/ \
    -H "Content-Type: application/json" \
    -d '{"title": "Deployment Test Session"}')
  
  SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.id')
  echo "Test session created with ID: $SESSION_ID"
  [ "$SESSION_ID" != "null" ] && [ "$SESSION_ID" != "" ] && echo "✓" || echo "✗ FAILED"
  ```

- [ ] **Chat functionality** working
  ```bash
  if [ "$SESSION_ID" != "null" ] && [ "$SESSION_ID" != "" ]; then
    CHAT_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/sessions/$SESSION_ID/chat" \
      -H "Content-Type: application/json" \
      -d '{"message": "Hello, this is a deployment test"}')
    
    AI_RESPONSE=$(echo "$CHAT_RESPONSE" | jq -r '.assistant_message.content')
    echo "AI response received: ${AI_RESPONSE:0:50}..."
    [ "$AI_RESPONSE" != "null" ] && [ "$AI_RESPONSE" != "" ] && echo "✓" || echo "✗ FAILED"
  fi
  ```

### Phase 3: Feature Enablement (If Applicable)

#### Feature Flag Updates
- [ ] **Persistent sessions** enabled (if planned)
  ```bash
  # Only if enabling persistent sessions in this deployment
  if [ "$ENABLE_PERSISTENT_SESSIONS" = "true" ]; then
    sed -i 's/USE_PERSISTENT_SESSIONS=false/USE_PERSISTENT_SESSIONS=true/' backend/.env
    sed -i 's/GRADUAL_ROLLOUT_PERCENTAGE=0/GRADUAL_ROLLOUT_PERCENTAGE=1/' backend/.env
    sudo systemctl restart oracle-chat
    sleep 15
  fi
  ```

- [ ] **Feature status** verified
  ```bash
  PERSISTENT_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.services.persistent_sessions')
  echo "Persistent sessions status: $PERSISTENT_SESSIONS"
  ```

#### Feature Validation
- [ ] **Session management** working with new features
  ```bash
  if [ "$PERSISTENT_SESSIONS" = "enabled" ]; then
    # Test session reuse
    CHAT_RESPONSE2=$(curl -s -X POST "http://localhost:8000/api/v1/sessions/$SESSION_ID/chat" \
      -H "Content-Type: application/json" \
      -d '{"message": "Second message to test session persistence"}')
    
    USED_PERSISTENT=$(echo "$CHAT_RESPONSE2" | jq -r '.performance_info.used_persistent_session')
    echo "Used persistent session: $USED_PERSISTENT"
    [ "$USED_PERSISTENT" = "true" ] && echo "✓" || echo "✗ NOT USING PERSISTENT SESSIONS"
  fi
  ```

### Phase 4: Performance and Monitoring Validation

#### Performance Metrics
- [ ] **Response times** within acceptable range
  ```bash
  # Test response time
  START_TIME=$(date +%s%N)
  curl -s -X POST "http://localhost:8000/api/v1/sessions/$SESSION_ID/chat" \
    -H "Content-Type: application/json" \
    -d '{"message": "Performance test message"}' > /dev/null
  END_TIME=$(date +%s%N)
  
  RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))  # Convert to milliseconds
  echo "Response time: ${RESPONSE_TIME}ms"
  [ $RESPONSE_TIME -lt 5000 ] && echo "✓" || echo "✗ SLOW RESPONSE"
  ```

- [ ] **Memory usage** within normal range
  ```bash
  MEMORY_USAGE=$(curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq -r '.system.memory_usage_percent')
  echo "Memory usage: ${MEMORY_USAGE}%"
  [ $(echo "$MEMORY_USAGE < 80" | bc -l) -eq 1 ] && echo "✓" || echo "✗ HIGH MEMORY USAGE"
  ```

#### Monitoring Setup
- [ ] **Monitoring endpoints** accessible
  ```bash
  endpoints=(
    "/health"
    "/api/v1/monitoring/health/detailed"
    "/api/v1/monitoring/health/sessions"
    "/api/v1/monitoring/sessions/analytics"
  )
  
  for endpoint in "${endpoints[@]}"; do
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000$endpoint")
    echo "$endpoint: $STATUS_CODE"
    [ "$STATUS_CODE" = "200" ] && echo "✓" || echo "✗ FAILED"
  done
  ```

- [ ] **Logging** functioning correctly
  ```bash
  # Check if logs are being written
  if [ -f backend/logs/backend.log ]; then
    RECENT_LOGS=$(tail -10 backend/logs/backend.log | wc -l)
    echo "Recent log entries: $RECENT_LOGS"
    [ $RECENT_LOGS -gt 0 ] && echo "✓" || echo "✗ NO RECENT LOGS"
  else
    echo "✗ LOG FILE NOT FOUND"
  fi
  ```

## Post-Deployment Validation

### Functional Testing

#### End-to-End User Flow
- [ ] **Complete user workflow** tested
  ```bash
  # Create session
  SESSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/sessions/ \
    -H "Content-Type: application/json" \
    -d '{"title": "E2E Test Session"}' | jq -r '.id')
  
  # Send multiple messages
  for i in {1..3}; do
    curl -s -X POST "http://localhost:8000/api/v1/sessions/$SESSION_ID/chat" \
      -H "Content-Type: application/json" \
      -d "{\"message\": \"Test message $i\"}" > /dev/null
    echo "Message $i sent"
  done
  
  # Retrieve message history
  MESSAGE_COUNT=$(curl -s "http://localhost:8000/api/v1/sessions/$SESSION_ID/messages" | jq -r '.total')
  echo "Total messages in session: $MESSAGE_COUNT"
  [ $MESSAGE_COUNT -ge 6 ] && echo "✓" || echo "✗ INCORRECT MESSAGE COUNT"  # 3 user + 3 assistant
  ```

- [ ] **Session management** operations working
  ```bash
  # List sessions
  SESSION_COUNT=$(curl -s http://localhost:8000/api/v1/sessions/ | jq -r '.total')
  echo "Total sessions: $SESSION_COUNT"
  
  # Get session details
  SESSION_TITLE=$(curl -s "http://localhost:8000/api/v1/sessions/$SESSION_ID" | jq -r '.title')
  echo "Session title: $SESSION_TITLE"
  [ "$SESSION_TITLE" = "E2E Test Session" ] && echo "✓" || echo "✗ INCORRECT SESSION TITLE"
  ```

#### Error Handling
- [ ] **Error responses** properly formatted
  ```bash
  # Test invalid session ID
  ERROR_RESPONSE=$(curl -s "http://localhost:8000/api/v1/sessions/99999")
  ERROR_DETAIL=$(echo "$ERROR_RESPONSE" | jq -r '.detail')
  echo "Error response: $ERROR_DETAIL"
  [ "$ERROR_DETAIL" != "null" ] && echo "✓" || echo "✗ NO ERROR DETAIL"
  ```

### Performance Validation

#### Load Testing
- [ ] **Concurrent requests** handled properly
  ```bash
  # Simple concurrent test
  echo "Testing concurrent requests..."
  for i in {1..5}; do
    (curl -s -X POST "http://localhost:8000/api/v1/sessions/$SESSION_ID/chat" \
      -H "Content-Type: application/json" \
      -d "{\"message\": \"Concurrent test $i\"}" > /dev/null) &
  done
  wait
  echo "Concurrent test completed"
  ```

- [ ] **System stability** under load
  ```bash
  # Check system health after load test
  sleep 5
  HEALTH_AFTER_LOAD=$(curl -s http://localhost:8000/health | jq -r '.status')
  echo "Health after load test: $HEALTH_AFTER_LOAD"
  [ "$HEALTH_AFTER_LOAD" = "healthy" ] && echo "✓" || echo "✗ UNHEALTHY AFTER LOAD"
  ```

### Security Validation

#### Configuration Security
- [ ] **No sensitive data** exposed in responses
  ```bash
  # Check health endpoint doesn't expose secrets
  HEALTH_RESPONSE=$(curl -s http://localhost:8000/api/v1/monitoring/health/detailed)
  if echo "$HEALTH_RESPONSE" | grep -i "api_key\|password\|secret" > /dev/null; then
    echo "✗ SENSITIVE DATA EXPOSED"
  else
    echo "✓ No sensitive data in health response"
  fi
  ```

- [ ] **File permissions** properly set
  ```bash
  # Check critical file permissions
  files=("backend/.env" "oracle_sessions.db")
  for file in "${files[@]}"; do
    if [ -f "$file" ]; then
      PERMS=$(stat -c %a "$file")
      echo "$file permissions: $PERMS"
      [ $PERMS -le 644 ] && echo "✓" || echo "✗ PERMISSIONS TOO PERMISSIVE"
    fi
  done
  ```

## Rollback Validation

### Rollback Readiness
- [ ] **Rollback scripts** tested and ready
  ```bash
  # Verify rollback scripts exist and are executable
  rollback_scripts=("scripts/rollback_features.sh" "scripts/rollback_version.sh")
  for script in "${rollback_scripts[@]}"; do
    if [ -x "$script" ]; then
      echo "$script: ✓ Ready"
    else
      echo "$script: ✗ NOT READY"
    fi
  done
  ```

- [ ] **Backup integrity** confirmed
  ```bash
  # Verify latest backup is intact
  LATEST_BACKUP=$(ls -t backups/oracle_sessions_*.db | head -1)
  if [ -f "$LATEST_BACKUP" ]; then
    sqlite3 "$LATEST_BACKUP" "PRAGMA integrity_check;" | head -1
    echo "Latest backup: $LATEST_BACKUP ✓"
  else
    echo "✗ NO BACKUP AVAILABLE"
  fi
  ```

### Rollback Testing (Optional - Staging Only)
- [ ] **Feature rollback** tested
  ```bash
  # Only run in staging environment
  if [ "$ENVIRONMENT" = "staging" ]; then
    echo "Testing feature rollback in staging..."
    ./scripts/rollback_features.sh
    sleep 10
    
    # Verify rollback worked
    PERSISTENT_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.services.persistent_sessions')
    [ "$PERSISTENT_SESSIONS" = "disabled" ] && echo "✓ Feature rollback works" || echo "✗ Feature rollback failed"
    
    # Re-enable for continued testing
    sed -i 's/USE_PERSISTENT_SESSIONS=false/USE_PERSISTENT_SESSIONS=true/' backend/.env
    sudo systemctl restart oracle-chat
  fi
  ```

## Final Deployment Sign-off

### Deployment Completion Checklist
- [ ] All pre-deployment checks passed
- [ ] Infrastructure deployment successful
- [ ] Basic validation completed
- [ ] Feature enablement (if applicable) successful
- [ ] Performance validation passed
- [ ] Security validation passed
- [ ] Monitoring and alerting configured
- [ ] Rollback procedures verified
- [ ] Documentation updated
- [ ] Team notified of successful deployment

### Sign-off Approvals
- [ ] **Technical Lead** approval: _________________ Date: _________
- [ ] **Operations** approval: _________________ Date: _________
- [ ] **Product Owner** approval: _________________ Date: _________

### Deployment Summary
```bash
#!/bin/bash
# Generate deployment summary
echo "=== DEPLOYMENT SUMMARY ==="
echo "Date: $(date)"
echo "Version: $(git describe --tags --always)"
echo "Environment: ${ENVIRONMENT:-production}"
echo "Deployed by: $(whoami)"
echo ""
echo "System Status:"
echo "  Health: $(curl -s http://localhost:8000/health | jq -r '.status')"
echo "  Version: $(curl -s http://localhost:8000/health | jq -r '.version')"
echo "  Persistent Sessions: $(curl -s http://localhost:8000/health | jq -r '.services.persistent_sessions')"
echo ""
echo "Performance Metrics:"
echo "  Memory Usage: $(curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq -r '.system.memory_usage_percent')%"
echo "  Active Sessions: $(curl -s http://localhost:8000/api/v1/monitoring/health/sessions | jq -r '.session_management.active_sessions')"
echo ""
echo "Deployment completed successfully!"
```

This comprehensive checklist ensures thorough validation at every stage of the deployment process, minimizing risks and ensuring successful deployment of Oracle Chat AI with persistent Gemini sessions.