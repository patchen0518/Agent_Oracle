# LangChain Integration Migration Guide

## Overview

This guide provides step-by-step instructions for migrating Oracle Chat AI from direct Gemini API integration to LangChain-enhanced conversation management. It includes pre-migration preparation, migration procedures, rollback plans, and monitoring guidelines.

## Migration Overview

### What's Changing

**From: Direct Gemini API Integration**
- Direct `google-genai` API calls
- Simple session caching
- Basic context management
- Manual conversation history handling

**To: LangChain-Enhanced Integration**
- `ChatGoogleGenerativeAI` through LangChain
- Intelligent memory strategies (buffer, summary, entity, hybrid)
- Automatic context optimization and summarization
- Entity extraction and fact retention
- Enhanced error handling and fallback mechanisms

### Benefits of Migration

1. **Improved Token Efficiency**: 60-80% reduction in API token usage
2. **Better Context Management**: Intelligent conversation summarization
3. **Enhanced Memory**: Entity extraction and fact retention
4. **Scalability**: Better handling of long conversations
5. **Flexibility**: Multiple memory strategies for different use cases

## Pre-Migration Checklist

### 1. Environment Preparation

```bash
# Backup current configuration
cp backend/.env backend/.env.backup.$(date +%Y%m%d_%H%M%S)

# Backup database
cp oracle_sessions.db oracle_sessions_backup_$(date +%Y%m%d_%H%M%S).db

# Verify LangChain dependencies
uv run python -c "import langchain; print(f'LangChain {langchain.__version__} available')"
uv run python -c "import langchain_google_genai; print('LangChain Google GenAI available')"
```

### 2. Configuration Validation

```bash
# Validate current configuration
uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv('backend/.env')
api_key = os.getenv('GEMINI_API_KEY')
if api_key:
    print('✓ GEMINI_API_KEY configured')
else:
    print('✗ GEMINI_API_KEY missing')
"

# Test current system
curl http://localhost:8000/health
```

### 3. Monitoring Setup

```bash
# Create monitoring directory
mkdir -p logs/migration

# Setup migration logging
export MIGRATION_LOG_FILE=logs/migration/migration_$(date +%Y%m%d_%H%M%S).log
```

## Migration Procedures

### Phase 1: Basic LangChain Integration (Low Risk)

#### Step 1: Enable LangChain with Minimal Configuration

```bash
# Add basic LangChain configuration to .env
cat >> backend/.env << 'EOF'

# LangChain Integration - Phase 1: Basic Integration
LANGCHAIN_ENABLED=true
LANGCHAIN_MEMORY_STRATEGY=buffer
LANGCHAIN_MAX_BUFFER_SIZE=10
LANGCHAIN_MAX_TOKENS=2000
LANGCHAIN_ENTITY_EXTRACTION_ENABLED=false
LANGCHAIN_ENABLE_SEMANTIC_SEARCH=false
LANGCHAIN_ENABLE_PERFORMANCE_MONITORING=true
LANGCHAIN_ENABLE_TOKEN_TRACKING=true
EOF
```

#### Step 2: Feature Flag Configuration

```bash
# Enable LangChain for 10% of sessions initially
export ENABLE_LANGCHAIN=true

# Update feature flags (if using feature flag system)
curl -X POST http://localhost:8000/api/v1/feature-flags/langchain_integration \
  -H "Content-Type: application/json" \
  -d '{"percentage": 10, "state": "percentage_rollout"}'
```

#### Step 3: Deploy and Monitor

```bash
# Restart application with LangChain integration
pkill -f "uvicorn main:app"
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 &

# Monitor startup
tail -f backend/logs/backend.log | grep -E "langchain|startup"

# Verify health
curl http://localhost:8000/health | jq '.services.langchain'
```

#### Step 4: Validation

```bash
# Test basic functionality
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"title": "LangChain Migration Test"}' | jq -r '.id')

# Send test message
curl -X POST http://localhost:8000/api/v1/sessions/$SESSION_ID/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test LangChain integration"}' | jq '.assistant_message.content'

# Monitor for errors
grep -E "ERROR|CRITICAL" backend/logs/backend.log | tail -5
```

### Phase 2: Enhanced Memory Strategies (Medium Risk)

#### Step 1: Enable Advanced Memory Features

```bash
# Update configuration for enhanced memory
cat >> backend/.env << 'EOF'

# LangChain Integration - Phase 2: Enhanced Memory
LANGCHAIN_MEMORY_STRATEGY=hybrid
LANGCHAIN_MAX_BUFFER_SIZE=20
LANGCHAIN_MAX_TOKENS_BEFORE_SUMMARY=4000
LANGCHAIN_ENTITY_EXTRACTION_ENABLED=true
LANGCHAIN_ENABLE_SEMANTIC_SEARCH=true
EOF
```

#### Step 2: Gradual Rollout

```bash
# Increase feature flag percentage to 25%
curl -X POST http://localhost:8000/api/v1/feature-flags/langchain_memory_strategies \
  -H "Content-Type: application/json" \
  -d '{"percentage": 25, "state": "percentage_rollout"}'

# Enable memory strategies
export ENABLE_LANGCHAIN_MEMORY=true
```

#### Step 3: Monitor Memory Performance

```bash
# Monitor memory strategy usage
grep "memory_strategy" backend/logs/backend.log | tail -10

# Check entity extraction
grep "entity_extraction" backend/logs/backend.log | tail -5

# Monitor token usage improvements
grep "token_usage_reduction" backend/logs/backend.log | tail -5
```

### Phase 3: Context Optimization (Medium Risk)

#### Step 1: Enable Context Optimization

```bash
# Add context optimization configuration
cat >> backend/.env << 'EOF'

# LangChain Integration - Phase 3: Context Optimization
LANGCHAIN_MAX_TOKENS=4000
LANGCHAIN_MESSAGES_TO_KEEP_AFTER_SUMMARY=20
LANGCHAIN_RELEVANCE_THRESHOLD=0.7
LANGCHAIN_SUMMARIZATION_TRIGGER_RATIO=0.8
LANGCHAIN_SUMMARY_MODEL=gemini-2.5-flash
EOF
```

#### Step 2: Enable Context Optimization Feature

```bash
# Enable context optimization for 50% of sessions
curl -X POST http://localhost:8000/api/v1/feature-flags/context_optimization \
  -H "Content-Type: application/json" \
  -d '{"percentage": 50, "state": "percentage_rollout"}'

export ENABLE_CONTEXT_OPTIMIZATION=true
```

#### Step 3: Monitor Context Performance

```bash
# Monitor context optimization
grep "context_optimization" backend/logs/backend.log | tail -10

# Check summarization activity
grep "summarization" backend/logs/backend.log | tail -5
```

### Phase 4: Full Rollout (Higher Risk)

#### Step 1: Complete Configuration

```bash
# Add full LangChain configuration
cat >> backend/.env << 'EOF'

# LangChain Integration - Phase 4: Full Configuration
LANGCHAIN_TEMPERATURE=0.7
LANGCHAIN_MAX_OUTPUT_TOKENS=2048
LANGCHAIN_LOG_LEVEL=info
ENABLE_HYBRID_PERSISTENCE=true
EOF
```

#### Step 2: Full Feature Rollout

```bash
# Enable all features for 100% of users
curl -X POST http://localhost:8000/api/v1/feature-flags/langchain_integration \
  -H "Content-Type: application/json" \
  -d '{"percentage": 100, "state": "enabled"}'

curl -X POST http://localhost:8000/api/v1/feature-flags/langchain_memory_strategies \
  -H "Content-Type: application/json" \
  -d '{"percentage": 100, "state": "enabled"}'

curl -X POST http://localhost:8000/api/v1/feature-flags/context_optimization \
  -H "Content-Type: application/json" \
  -d '{"percentage": 100, "state": "enabled"}'
```

#### Step 3: Final Validation

```bash
# Comprehensive system test
./scripts/test_langchain_integration.sh

# Performance validation
./scripts/validate_token_usage.sh

# Monitor system health
curl http://localhost:8000/health | jq '.'
```

## Rollback Procedures

### Emergency Rollback (Immediate)

If critical issues occur, perform immediate rollback:

```bash
# 1. Disable LangChain integration immediately
export LANGCHAIN_ENABLED=false
export ENABLE_LANGCHAIN=false

# 2. Restart application
pkill -f "uvicorn main:app"
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 &

# 3. Verify rollback
curl http://localhost:8000/health | jq '.services'

# 4. Monitor for stability
tail -f backend/logs/backend.log | grep -v langchain
```

### Partial Rollback (Selective)

Roll back specific features while maintaining basic LangChain integration:

```bash
# Disable advanced memory strategies
export LANGCHAIN_MEMORY_STRATEGY=buffer
export LANGCHAIN_ENTITY_EXTRACTION_ENABLED=false
export ENABLE_LANGCHAIN_MEMORY=false

# Disable context optimization
export LANGCHAIN_ENABLE_SEMANTIC_SEARCH=false
export ENABLE_CONTEXT_OPTIMIZATION=false

# Restart with reduced features
pkill -f "uvicorn main:app"
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 &
```

### Configuration Rollback

Restore previous configuration:

```bash
# 1. Restore backup configuration
BACKUP_FILE=$(ls -t backend/.env.backup.* | head -1)
cp "$BACKUP_FILE" backend/.env

# 2. Restore backup database (if needed)
BACKUP_DB=$(ls -t oracle_sessions_backup_*.db | head -1)
cp "$BACKUP_DB" oracle_sessions.db

# 3. Restart application
pkill -f "uvicorn main:app"
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 &

# 4. Verify rollback
curl http://localhost:8000/health
```

### Feature Flag Rollback

Use feature flags for controlled rollback:

```bash
# Disable LangChain integration via feature flags
curl -X POST http://localhost:8000/api/v1/feature-flags/langchain_integration \
  -H "Content-Type: application/json" \
  -d '{"state": "disabled"}'

# Disable memory strategies
curl -X POST http://localhost:8000/api/v1/feature-flags/langchain_memory_strategies \
  -H "Content-Type: application/json" \
  -d '{"state": "disabled"}'

# Disable context optimization
curl -X POST http://localhost:8000/api/v1/feature-flags/context_optimization \
  -H "Content-Type: application/json" \
  -d '{"state": "disabled"}'
```

## Monitoring Guidelines

### Key Metrics to Monitor

#### 1. System Health Metrics

```bash
# Overall system health
curl http://localhost:8000/health | jq '.status'

# LangChain integration status
curl http://localhost:8000/health | jq '.services.langchain'

# Error rates
grep -c "ERROR" backend/logs/backend.log
```

#### 2. Performance Metrics

```bash
# Response time monitoring
grep "response_time" backend/logs/backend.log | tail -10

# Token usage improvements
grep "token_usage_reduction" backend/logs/backend.log | tail -5

# Memory strategy performance
grep "memory_strategy_performance" backend/logs/backend.log | tail -5
```

#### 3. LangChain-Specific Metrics

```bash
# Memory strategy usage
grep "memory_strategy" backend/logs/backend.log | \
  awk '{print $NF}' | sort | uniq -c

# Entity extraction success rate
grep "entity_extraction" backend/logs/backend.log | \
  grep -c "success"

# Context optimization effectiveness
grep "context_optimization" backend/logs/backend.log | tail -5
```

### Monitoring Alerts

Set up alerts for critical metrics:

#### 1. Error Rate Alerts

```bash
# Monitor LangChain error rate
ERROR_COUNT=$(grep -c "LANGCHAIN.*ERROR" backend/logs/backend.log)
if [ $ERROR_COUNT -gt 10 ]; then
    echo "ALERT: High LangChain error rate: $ERROR_COUNT errors"
fi
```

#### 2. Performance Degradation Alerts

```bash
# Monitor response time degradation
SLOW_RESPONSES=$(grep "response_time.*[5-9][0-9][0-9][0-9]" backend/logs/backend.log | wc -l)
if [ $SLOW_RESPONSES -gt 5 ]; then
    echo "ALERT: Performance degradation detected"
fi
```

#### 3. Memory Strategy Failure Alerts

```bash
# Monitor memory strategy failures
MEMORY_FAILURES=$(grep -c "memory_strategy.*failed" backend/logs/backend.log)
if [ $MEMORY_FAILURES -gt 3 ]; then
    echo "ALERT: Memory strategy failures detected"
fi
```

### Monitoring Dashboard

Create monitoring dashboard with key metrics:

1. **System Health**: Overall system status and LangChain integration status
2. **Performance**: Response times, token usage, memory efficiency
3. **Error Rates**: LangChain-specific errors and fallback usage
4. **Feature Usage**: Memory strategy distribution, optimization effectiveness
5. **User Impact**: Session success rates, conversation quality metrics

## Post-Migration Validation

### 1. Functional Validation

```bash
# Test all memory strategies
for strategy in buffer summary entity hybrid; do
    echo "Testing memory strategy: $strategy"
    # Create test session with specific strategy
    # Send multiple messages to test memory behavior
    # Validate responses and context handling
done
```

### 2. Performance Validation

```bash
# Compare token usage before and after migration
./scripts/compare_token_usage.sh

# Validate response time improvements
./scripts/benchmark_response_times.sh

# Test long conversation handling
./scripts/test_long_conversations.sh
```

### 3. Integration Validation

```bash
# Test all API endpoints with LangChain integration
./scripts/test_api_endpoints.sh

# Validate database integration
./scripts/test_database_integration.sh

# Test error handling and fallback mechanisms
./scripts/test_error_scenarios.sh
```

## Migration Timeline

### Recommended Timeline

**Week 1: Preparation**
- Environment setup and dependency installation
- Configuration preparation and validation
- Monitoring setup and baseline establishment

**Week 2: Phase 1 Deployment**
- Basic LangChain integration (10% rollout)
- Monitor for 3-5 days
- Validate functionality and performance

**Week 3: Phase 2 Deployment**
- Enhanced memory strategies (25% rollout)
- Monitor memory strategy performance
- Validate entity extraction and context handling

**Week 4: Phase 3 Deployment**
- Context optimization (50% rollout)
- Monitor summarization and optimization
- Validate token usage improvements

**Week 5: Full Rollout**
- Complete feature rollout (100%)
- Final validation and performance testing
- Documentation and training completion

### Risk Mitigation

1. **Gradual Rollout**: Use feature flags for controlled deployment
2. **Monitoring**: Comprehensive monitoring at each phase
3. **Rollback Plans**: Immediate rollback procedures ready
4. **Testing**: Extensive testing at each phase
5. **Communication**: Clear communication plan for stakeholders

## Success Criteria

### Technical Success Criteria

1. **Functionality**: All existing functionality preserved
2. **Performance**: 60-80% token usage reduction achieved
3. **Reliability**: Error rates remain below baseline
4. **Scalability**: Improved handling of long conversations
5. **Monitoring**: Comprehensive monitoring in place

### Business Success Criteria

1. **User Experience**: No degradation in user experience
2. **Cost Reduction**: Significant reduction in API costs
3. **Feature Enhancement**: New memory capabilities available
4. **Maintainability**: Improved code maintainability and extensibility
5. **Documentation**: Complete documentation and procedures

## Troubleshooting

For migration-specific issues, refer to:

1. **[LangChain Troubleshooting Guide](LANGCHAIN_TROUBLESHOOTING.md)**: Comprehensive troubleshooting
2. **[API Documentation](API_DOCUMENTATION.md)**: Updated API documentation
3. **[Deployment Guide](DEPLOYMENT.md)**: Deployment procedures and monitoring

## Support and Escalation

### Migration Support Contacts

1. **Technical Issues**: Development team
2. **Performance Issues**: DevOps team
3. **Business Impact**: Product team
4. **Emergency Rollback**: On-call engineer

### Escalation Procedures

1. **Level 1**: Monitor alerts and automated responses
2. **Level 2**: Manual intervention and partial rollback
3. **Level 3**: Complete rollback and incident response
4. **Level 4**: Emergency procedures and stakeholder notification

## Conclusion

This migration guide provides a comprehensive approach to migrating Oracle Chat AI to LangChain integration. Follow the phased approach, monitor carefully at each step, and be prepared to rollback if issues occur. The migration will significantly improve the system's conversation management capabilities while maintaining reliability and performance.