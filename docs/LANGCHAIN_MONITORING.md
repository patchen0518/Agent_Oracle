# LangChain Integration Monitoring Guidelines

## Overview

This document provides comprehensive monitoring guidelines for Oracle Chat AI's LangChain integration, including key metrics, alerting strategies, performance benchmarks, and health monitoring procedures.

## Monitoring Architecture

### Monitoring Stack

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Application   │───▶│   Log Files     │───▶│   Monitoring    │
│   Metrics       │    │   & Structured  │    │   Dashboard     │
│                 │    │   Logging       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Health        │    │   Performance   │    │   Alerting      │
│   Endpoints     │    │   Metrics       │    │   System        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Components

1. **Application Metrics**: Built-in LangChain performance tracking
2. **Health Endpoints**: Real-time system health checks
3. **Structured Logging**: Detailed operation logging
4. **Performance Benchmarks**: Token usage and response time tracking
5. **Alerting System**: Proactive issue detection

## Key Metrics to Monitor

### 1. System Health Metrics

#### LangChain Integration Status
```bash
# Endpoint: GET /health
# Key fields: services.langchain, langchain_metrics

curl http://localhost:8000/health | jq '{
  langchain_status: .services.langchain,
  memory_strategy: .langchain_metrics.memory_strategy,
  active_sessions: .langchain_metrics.active_memory_sessions,
  token_reduction: .langchain_metrics.token_usage_reduction
}'
```

**Expected Values:**
- `langchain_status`: "enabled"
- `memory_strategy`: "hybrid" (or configured strategy)
- `active_sessions`: 0-50 (based on load)
- `token_reduction`: "60-80%"

#### Memory Strategy Health
```bash
# Monitor memory strategy distribution
grep "memory_strategy_used" backend/logs/backend.log | \
  awk '{print $NF}' | sort | uniq -c

# Expected distribution (for hybrid strategy):
# buffer: 30-40%
# summary: 20-30%
# entity: 15-25%
# hybrid: 20-30%
```

### 2. Performance Metrics

#### Token Usage Efficiency
```bash
# Monitor token usage improvements
grep "token_usage_reduction" backend/logs/backend.log | \
  tail -10 | awk '{print $NF}' | sed 's/%//' | \
  awk '{sum+=$1; count++} END {print "Average reduction: " sum/count "%"}'

# Target: 60-80% reduction
# Alert if: < 40% reduction
```

#### Response Time Performance
```bash
# Monitor LangChain response times
grep "langchain_response_time" backend/logs/backend.log | \
  tail -20 | awk '{print $NF}' | sed 's/ms//' | \
  awk '{sum+=$1; count++} END {print "Average response time: " sum/count "ms"}'

# Target: < 2000ms
# Alert if: > 5000ms
```

#### Memory Operation Performance
```bash
# Monitor memory operation times
grep "memory_operation_time" backend/logs/backend.log | \
  tail -10 | awk '{print $NF}' | sed 's/ms//' | \
  awk '{sum+=$1; count++} END {print "Average memory operation time: " sum/count "ms"}'

# Target: < 500ms
# Alert if: > 1000ms
```

### 3. Error Rate Metrics

#### LangChain Error Rates
```bash
# Calculate LangChain error rate
TOTAL_REQUESTS=$(grep -c "langchain_request" backend/logs/backend.log)
ERROR_REQUESTS=$(grep -c "langchain.*ERROR" backend/logs/backend.log)
ERROR_RATE=$(echo "scale=2; $ERROR_REQUESTS * 100 / $TOTAL_REQUESTS" | bc)
echo "LangChain error rate: $ERROR_RATE%"

# Target: < 1%
# Alert if: > 5%
```

#### Memory Strategy Failure Rate
```bash
# Monitor memory strategy failures
MEMORY_OPERATIONS=$(grep -c "memory_strategy_operation" backend/logs/backend.log)
MEMORY_FAILURES=$(grep -c "memory_strategy.*failed" backend/logs/backend.log)
FAILURE_RATE=$(echo "scale=2; $MEMORY_FAILURES * 100 / $MEMORY_OPERATIONS" | bc)
echo "Memory strategy failure rate: $FAILURE_RATE%"

# Target: < 2%
# Alert if: > 10%
```

#### Fallback Usage Rate
```bash
# Monitor fallback mechanism usage
TOTAL_SESSIONS=$(grep -c "session_created" backend/logs/backend.log)
FALLBACK_SESSIONS=$(grep -c "fallback_to_direct_gemini" backend/logs/backend.log)
FALLBACK_RATE=$(echo "scale=2; $FALLBACK_SESSIONS * 100 / $TOTAL_SESSIONS" | bc)
echo "Fallback usage rate: $FALLBACK_RATE%"

# Target: < 5%
# Alert if: > 20%
```

### 4. Feature Usage Metrics

#### Entity Extraction Success Rate
```bash
# Monitor entity extraction performance
EXTRACTION_ATTEMPTS=$(grep -c "entity_extraction_attempt" backend/logs/backend.log)
EXTRACTION_SUCCESS=$(grep -c "entity_extraction_success" backend/logs/backend.log)
SUCCESS_RATE=$(echo "scale=2; $EXTRACTION_SUCCESS * 100 / $EXTRACTION_ATTEMPTS" | bc)
echo "Entity extraction success rate: $SUCCESS_RATE%"

# Target: > 80%
# Alert if: < 60%
```

#### Context Optimization Effectiveness
```bash
# Monitor context optimization impact
grep "context_optimization_result" backend/logs/backend.log | \
  tail -10 | awk '{print $NF}' | sed 's/%//' | \
  awk '{sum+=$1; count++} END {print "Average context reduction: " sum/count "%"}'

# Target: 30-50% context reduction
# Alert if: < 20% or > 70%
```

## Monitoring Dashboards

### 1. Executive Dashboard

**Key Metrics:**
- System uptime and availability
- Overall performance (response times)
- Cost savings (token usage reduction)
- User satisfaction metrics

```bash
# Generate executive summary
cat << 'EOF' > /tmp/executive_summary.sh
#!/bin/bash
echo "=== LangChain Integration Executive Summary ==="
echo "Date: $(date)"
echo ""

# System health
HEALTH=$(curl -s http://localhost:8000/health | jq -r '.status')
echo "System Status: $HEALTH"

# Token savings
TOKEN_REDUCTION=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.token_usage_reduction // "N/A"')
echo "Token Usage Reduction: $TOKEN_REDUCTION"

# Active sessions
ACTIVE_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.session_metrics.active_sessions // 0')
echo "Active Sessions: $ACTIVE_SESSIONS"

# Error rate (last 24 hours)
ERROR_COUNT=$(grep -c "ERROR" backend/logs/backend.log)
echo "Error Count (24h): $ERROR_COUNT"

echo ""
echo "=== End Summary ==="
EOF

chmod +x /tmp/executive_summary.sh
/tmp/executive_summary.sh
```

### 2. Technical Dashboard

**Key Metrics:**
- LangChain integration status
- Memory strategy performance
- Error rates and types
- Performance benchmarks

```bash
# Generate technical dashboard
cat << 'EOF' > /tmp/technical_dashboard.sh
#!/bin/bash
echo "=== LangChain Technical Dashboard ==="
echo "Date: $(date)"
echo ""

# LangChain status
LANGCHAIN_STATUS=$(curl -s http://localhost:8000/health | jq -r '.services.langchain // "unknown"')
echo "LangChain Status: $LANGCHAIN_STATUS"

# Memory strategy
MEMORY_STRATEGY=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.memory_strategy // "unknown"')
echo "Memory Strategy: $MEMORY_STRATEGY"

# Performance metrics
echo ""
echo "Performance Metrics:"
grep "langchain_response_time" backend/logs/backend.log | tail -5 | \
  awk '{print "  Response Time: " $NF}'

# Error analysis
echo ""
echo "Recent Errors:"
grep -E "langchain.*ERROR" backend/logs/backend.log | tail -3 | \
  awk '{print "  " $0}'

# Memory operations
echo ""
echo "Memory Operations:"
grep "memory_strategy_used" backend/logs/backend.log | tail -5 | \
  awk '{print "  Strategy Used: " $NF}'

echo ""
echo "=== End Dashboard ==="
EOF

chmod +x /tmp/technical_dashboard.sh
/tmp/technical_dashboard.sh
```

### 3. Operations Dashboard

**Key Metrics:**
- Resource utilization
- Session management
- Database performance
- System capacity

```bash
# Generate operations dashboard
cat << 'EOF' > /tmp/operations_dashboard.sh
#!/bin/bash
echo "=== LangChain Operations Dashboard ==="
echo "Date: $(date)"
echo ""

# Resource utilization
echo "Resource Utilization:"
ps aux | grep uvicorn | grep -v grep | awk '{print "  CPU: " $3 "%, Memory: " $4 "%"}'

# Session metrics
echo ""
echo "Session Metrics:"
TOTAL_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.session_metrics.total_sessions // 0')
ACTIVE_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.session_metrics.active_sessions // 0')
echo "  Total Sessions: $TOTAL_SESSIONS"
echo "  Active Sessions: $ACTIVE_SESSIONS"

# Database size
echo ""
echo "Database Metrics:"
DB_SIZE=$(ls -lh oracle_sessions.db | awk '{print $5}')
echo "  Database Size: $DB_SIZE"

# Log file sizes
echo ""
echo "Log File Sizes:"
ls -lh backend/logs/*.log | awk '{print "  " $9 ": " $5}'

echo ""
echo "=== End Dashboard ==="
EOF

chmod +x /tmp/operations_dashboard.sh
/tmp/operations_dashboard.sh
```

## Alerting Configuration

### 1. Critical Alerts (Immediate Response)

#### System Down Alert
```bash
# Monitor system availability
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HEALTH_STATUS" != "200" ]; then
    echo "CRITICAL: System is down (HTTP $HEALTH_STATUS)"
    # Trigger immediate alert
fi
```

#### LangChain Integration Failure
```bash
# Monitor LangChain integration status
LANGCHAIN_STATUS=$(curl -s http://localhost:8000/health | jq -r '.services.langchain')
if [ "$LANGCHAIN_STATUS" != "enabled" ]; then
    echo "CRITICAL: LangChain integration failed"
    # Trigger immediate alert
fi
```

#### High Error Rate Alert
```bash
# Monitor error rate (last 5 minutes)
ERROR_COUNT=$(grep "$(date '+%Y-%m-%d %H:%M')" backend/logs/backend.log | grep -c "ERROR")
if [ $ERROR_COUNT -gt 10 ]; then
    echo "CRITICAL: High error rate detected ($ERROR_COUNT errors in last 5 minutes)"
    # Trigger immediate alert
fi
```

### 2. Warning Alerts (Monitor Closely)

#### Performance Degradation
```bash
# Monitor response time degradation
AVG_RESPONSE_TIME=$(grep "langchain_response_time" backend/logs/backend.log | \
  tail -10 | awk '{print $NF}' | sed 's/ms//' | \
  awk '{sum+=$1; count++} END {print sum/count}')

if (( $(echo "$AVG_RESPONSE_TIME > 3000" | bc -l) )); then
    echo "WARNING: Performance degradation detected (avg response time: ${AVG_RESPONSE_TIME}ms)"
    # Trigger warning alert
fi
```

#### Memory Strategy Failures
```bash
# Monitor memory strategy failure rate
MEMORY_FAILURES=$(grep -c "memory_strategy.*failed" backend/logs/backend.log)
if [ $MEMORY_FAILURES -gt 5 ]; then
    echo "WARNING: Multiple memory strategy failures ($MEMORY_FAILURES)"
    # Trigger warning alert
fi
```

#### Token Usage Efficiency Drop
```bash
# Monitor token usage efficiency
TOKEN_REDUCTION=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.token_usage_reduction' | sed 's/%//')
if (( $(echo "$TOKEN_REDUCTION < 40" | bc -l) )); then
    echo "WARNING: Token usage efficiency below threshold (${TOKEN_REDUCTION}%)"
    # Trigger warning alert
fi
```

### 3. Info Alerts (Informational)

#### Feature Usage Changes
```bash
# Monitor feature usage patterns
CURRENT_STRATEGY=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.memory_strategy')
echo "INFO: Current memory strategy: $CURRENT_STRATEGY"
```

#### Capacity Planning
```bash
# Monitor capacity metrics
ACTIVE_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.session_metrics.active_sessions')
if [ $ACTIVE_SESSIONS -gt 40 ]; then
    echo "INFO: High session count ($ACTIVE_SESSIONS), consider capacity planning"
fi
```

## Performance Benchmarking

### 1. Baseline Metrics

Establish baseline metrics before LangChain integration:

```bash
# Pre-migration baseline
cat << 'EOF' > /tmp/baseline_metrics.sh
#!/bin/bash
echo "=== Pre-Migration Baseline Metrics ==="
echo "Date: $(date)"
echo ""

# Response time baseline
echo "Response Time Baseline:"
grep "response_time" backend/logs/backend.log | tail -100 | \
  awk '{print $NF}' | sed 's/ms//' | \
  awk '{sum+=$1; count++} END {print "  Average: " sum/count "ms"}'

# Token usage baseline
echo ""
echo "Token Usage Baseline:"
grep "tokens_used" backend/logs/backend.log | tail -100 | \
  awk '{print $NF}' | \
  awk '{sum+=$1; count++} END {print "  Average: " sum/count " tokens"}'

# Error rate baseline
echo ""
echo "Error Rate Baseline:"
TOTAL_REQUESTS=$(grep -c "request" backend/logs/backend.log)
ERROR_REQUESTS=$(grep -c "ERROR" backend/logs/backend.log)
ERROR_RATE=$(echo "scale=2; $ERROR_REQUESTS * 100 / $TOTAL_REQUESTS" | bc)
echo "  Error Rate: $ERROR_RATE%"

echo ""
echo "=== End Baseline ==="
EOF

chmod +x /tmp/baseline_metrics.sh
/tmp/baseline_metrics.sh
```

### 2. Performance Comparison

Compare performance before and after LangChain integration:

```bash
# Performance comparison script
cat << 'EOF' > /tmp/performance_comparison.sh
#!/bin/bash
echo "=== LangChain Performance Comparison ==="
echo "Date: $(date)"
echo ""

# Token usage comparison
echo "Token Usage Improvement:"
TOKEN_REDUCTION=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.token_usage_reduction')
echo "  Reduction: $TOKEN_REDUCTION"

# Response time comparison
echo ""
echo "Response Time Comparison:"
CURRENT_AVG=$(grep "langchain_response_time" backend/logs/backend.log | \
  tail -50 | awk '{print $NF}' | sed 's/ms//' | \
  awk '{sum+=$1; count++} END {print sum/count}')
echo "  Current Average: ${CURRENT_AVG}ms"

# Memory efficiency
echo ""
echo "Memory Efficiency:"
MEMORY_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.active_memory_sessions')
TOTAL_SESSIONS=$(curl -s http://localhost:8000/health | jq -r '.session_metrics.active_sessions')
MEMORY_EFFICIENCY=$(echo "scale=2; $MEMORY_SESSIONS * 100 / $TOTAL_SESSIONS" | bc)
echo "  Memory-managed sessions: ${MEMORY_EFFICIENCY}%"

echo ""
echo "=== End Comparison ==="
EOF

chmod +x /tmp/performance_comparison.sh
/tmp/performance_comparison.sh
```

## Health Check Procedures

### 1. Automated Health Checks

```bash
# Comprehensive health check script
cat << 'EOF' > /tmp/langchain_health_check.sh
#!/bin/bash
echo "=== LangChain Health Check ==="
echo "Date: $(date)"
echo ""

# Basic connectivity
echo "1. Basic Connectivity:"
HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HEALTH_CODE" = "200" ]; then
    echo "  ✓ Health endpoint accessible"
else
    echo "  ✗ Health endpoint failed (HTTP $HEALTH_CODE)"
    exit 1
fi

# LangChain integration status
echo ""
echo "2. LangChain Integration:"
LANGCHAIN_STATUS=$(curl -s http://localhost:8000/health | jq -r '.services.langchain')
if [ "$LANGCHAIN_STATUS" = "enabled" ]; then
    echo "  ✓ LangChain integration active"
else
    echo "  ✗ LangChain integration inactive ($LANGCHAIN_STATUS)"
fi

# Memory strategy status
echo ""
echo "3. Memory Strategy:"
MEMORY_STRATEGY=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.memory_strategy')
echo "  Current strategy: $MEMORY_STRATEGY"

# Recent errors
echo ""
echo "4. Recent Errors:"
ERROR_COUNT=$(grep "$(date '+%Y-%m-%d')" backend/logs/backend.log | grep -c "ERROR")
if [ $ERROR_COUNT -eq 0 ]; then
    echo "  ✓ No errors today"
else
    echo "  ⚠ $ERROR_COUNT errors today"
fi

# Performance check
echo ""
echo "5. Performance Check:"
TOKEN_REDUCTION=$(curl -s http://localhost:8000/health | jq -r '.langchain_metrics.token_usage_reduction')
echo "  Token usage reduction: $TOKEN_REDUCTION"

echo ""
echo "=== Health Check Complete ==="
EOF

chmod +x /tmp/langchain_health_check.sh
/tmp/langchain_health_check.sh
```

### 2. Manual Health Verification

```bash
# Manual verification steps
echo "Manual LangChain Health Verification:"
echo ""

# 1. Test session creation
echo "1. Testing session creation..."
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Health Check Session"}' | jq -r '.id')

if [ "$SESSION_ID" != "null" ] && [ -n "$SESSION_ID" ]; then
    echo "  ✓ Session created successfully (ID: $SESSION_ID)"
else
    echo "  ✗ Session creation failed"
fi

# 2. Test message sending
echo ""
echo "2. Testing message sending..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/sessions/$SESSION_ID/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, this is a health check"}')

ASSISTANT_MESSAGE=$(echo "$RESPONSE" | jq -r '.assistant_message.content')
if [ "$ASSISTANT_MESSAGE" != "null" ] && [ -n "$ASSISTANT_MESSAGE" ]; then
    echo "  ✓ Message processed successfully"
else
    echo "  ✗ Message processing failed"
fi

# 3. Test session cleanup
echo ""
echo "3. Testing session cleanup..."
DELETE_RESPONSE=$(curl -s -X DELETE http://localhost:8000/api/v1/sessions/$SESSION_ID)
DELETE_STATUS=$(echo "$DELETE_RESPONSE" | jq -r '.message')
if [[ "$DELETE_STATUS" == *"deleted"* ]]; then
    echo "  ✓ Session deleted successfully"
else
    echo "  ✗ Session deletion failed"
fi

echo ""
echo "Manual verification complete."
```

## Troubleshooting Integration

For detailed troubleshooting procedures, refer to:

1. **[LangChain Troubleshooting Guide](LANGCHAIN_TROUBLESHOOTING.md)**: Comprehensive issue resolution
2. **[Migration Guide](LANGCHAIN_MIGRATION_GUIDE.md)**: Migration-specific monitoring
3. **[API Documentation](API_DOCUMENTATION.md)**: API endpoint monitoring

## Monitoring Best Practices

### 1. Proactive Monitoring

- Set up automated health checks every 5 minutes
- Monitor key metrics continuously
- Use predictive alerting for capacity planning
- Implement trend analysis for performance optimization

### 2. Reactive Monitoring

- Establish clear escalation procedures
- Maintain runbooks for common issues
- Implement automated rollback triggers
- Document all incidents and resolutions

### 3. Continuous Improvement

- Regular review of monitoring effectiveness
- Update alerting thresholds based on historical data
- Optimize monitoring overhead
- Enhance monitoring coverage based on new features

## Conclusion

Effective monitoring of LangChain integration is crucial for maintaining system reliability and performance. Use this guide to establish comprehensive monitoring, set up appropriate alerts, and maintain system health. Regular review and optimization of monitoring procedures will ensure continued success of the LangChain integration.