# Oracle Chat AI - Monitoring and Observability Guide

## Overview

This guide provides comprehensive information on monitoring Oracle Chat AI's persistent session management system, interpreting metrics, setting up alerts, and maintaining optimal performance.

## Table of Contents

1. [Monitoring Architecture](#monitoring-architecture)
2. [Key Metrics and KPIs](#key-metrics-and-kpis)
3. [Health Check Endpoints](#health-check-endpoints)
4. [Performance Monitoring](#performance-monitoring)
5. [Session Management Monitoring](#session-management-monitoring)
6. [Alerting and Thresholds](#alerting-and-thresholds)
7. [Dashboard Setup](#dashboard-setup)
8. [Log Analysis](#log-analysis)

## Monitoring Architecture

Oracle Chat AI provides multiple layers of observability:

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                         │
├─────────────────────────────────────────────────────────────┤
│  Application Metrics                                        │
│  ├── Session Management (Cache, Recovery, Cleanup)         │
│  ├── Performance Metrics (Response Times, Token Usage)     │
│  ├── Database Operations (CRUD, Connection Health)         │
│  └── API Endpoints (Request/Response, Error Rates)         │
├─────────────────────────────────────────────────────────────┤
│  System Metrics                                            │
│  ├── Memory Usage (Application + System)                   │
│  ├── Disk Usage (Database, Logs)                          │
│  ├── CPU Usage (Processing Load)                          │
│  └── Network (API Calls, Connectivity)                    │
├─────────────────────────────────────────────────────────────┤
│  External Dependencies                                      │
│  ├── Gemini API (Availability, Rate Limits, Errors)       │
│  ├── Database (SQLite Health, Performance)                │
│  └── File System (Log Writing, Database Access)           │
└─────────────────────────────────────────────────────────────┘
```

## Key Metrics and KPIs

### Session Management KPIs

#### Cache Performance
- **Cache Hit Ratio:** `cache_hits / (cache_hits + cache_misses)`
  - **Target:** > 70%
  - **Warning:** < 50%
  - **Critical:** < 30%

- **Active Sessions:** Current sessions in memory
  - **Target:** Stable based on usage patterns
  - **Warning:** > 80% of `MAX_PERSISTENT_SESSIONS`
  - **Critical:** > 95% of `MAX_PERSISTENT_SESSIONS`

- **Session Recovery Rate:** `sessions_recovered / total_sessions_created`
  - **Target:** < 5%
  - **Warning:** 5-10%
  - **Critical:** > 10%

#### Performance KPIs
- **Response Time Improvement:** Compared to stateless mode
  - **Target:** 30-50% improvement
  - **Warning:** < 20% improvement
  - **Critical:** No improvement or degradation

- **Token Usage Reduction:** Compared to stateless mode
  - **Target:** 60-80% reduction
  - **Warning:** < 40% reduction
  - **Critical:** < 20% reduction

- **Session Creation Time:** Average time to create new session
  - **Target:** < 500ms
  - **Warning:** 500ms - 1000ms
  - **Critical:** > 1000ms

### System KPIs

#### Resource Utilization
- **Memory Usage:** System memory utilization
  - **Target:** < 70%
  - **Warning:** 70-85%
  - **Critical:** > 85%

- **Disk Usage:** Available disk space
  - **Target:** < 80%
  - **Warning:** 80-90%
  - **Critical:** > 90%

#### Database Performance
- **Query Response Time:** Average database query time
  - **Target:** < 50ms
  - **Warning:** 50-100ms
  - **Critical:** > 100ms

- **Connection Health:** Database connectivity status
  - **Target:** Always healthy
  - **Critical:** Any connection failures

## Health Check Endpoints

### Basic Health Check

**Endpoint:** `GET /health`

**Purpose:** Quick system status overview

**Key Fields:**
```json
{
  "status": "healthy|degraded|unhealthy",
  "services": {
    "gemini_api": "configured|missing",
    "database": "connected|disconnected",
    "persistent_sessions": "enabled|disabled"
  },
  "session_metrics": {
    "total_sessions": 25,
    "active_sessions": 8,
    "persistent_sessions_active": 5
  }
}
```

**Monitoring Usage:**
```bash
# Simple health check
curl -s http://localhost:8000/health | jq '.status'

# Check if persistent sessions are working
curl -s http://localhost:8000/health | jq '.services.persistent_sessions'
```

### Detailed Health Check

**Endpoint:** `GET /api/v1/monitoring/health/detailed`

**Purpose:** Comprehensive system diagnostics

**Key Sections:**
- **System Resources:** Memory, disk, CPU usage
- **Database Status:** Connection health, query performance
- **Environment Config:** Feature flags, API keys, settings
- **Error Statistics:** Error rates, recent errors, error types

**Critical Metrics to Monitor:**
```bash
# Memory usage
curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq '.system.memory_usage_percent'

# Database health
curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq '.database.status'

# Error rate
curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq '.errors.error_rate_per_hour'
```

### Session Health Check

**Endpoint:** `GET /api/v1/monitoring/health/sessions`

**Purpose:** Detailed session management health

**Key Metrics:**
```json
{
  "session_management": {
    "cache_performance": {
      "cache_hit_ratio": 0.847,
      "status": "healthy|fair|poor"
    },
    "memory_usage": {
      "current_usage_mb": 12.5,
      "usage_percentage": 1.0,
      "status": "healthy|moderate|high"
    },
    "cleanup_operations": {
      "last_cleanup": "2025-01-27T11:55:00Z",
      "status": "healthy|delayed|overdue"
    }
  }
}
```

**Monitoring Commands:**
```bash
# Cache performance
curl -s http://localhost:8000/api/v1/monitoring/health/sessions | jq '.session_management.cache_performance'

# Memory usage
curl -s http://localhost:8000/api/v1/monitoring/health/sessions | jq '.session_management.memory_usage'

# Cleanup status
curl -s http://localhost:8000/api/v1/monitoring/health/sessions | jq '.session_management.cleanup_operations'
```

## Performance Monitoring

### Session Performance Metrics

**Endpoint:** `GET /api/v1/monitoring/health/sessions/performance`

**Key Performance Indicators:**

#### Session Creation Performance
```json
{
  "session_creation": {
    "total_operations": 127,
    "avg_creation_time_ms": 245.5,
    "min_creation_time_ms": 120,
    "max_creation_time_ms": 890
  }
}
```

**Monitoring:**
```bash
# Average session creation time
curl -s http://localhost:8000/api/v1/monitoring/health/sessions/performance | jq '.performance_summary.session_creation.avg_creation_time_ms'

# Performance indicators
curl -s http://localhost:8000/api/v1/monitoring/health/sessions/performance | jq '.performance_indicators'
```

#### Session Recovery Performance
```json
{
  "session_recovery": {
    "total_operations": 8,
    "avg_recovery_time_ms": 1250.0,
    "min_recovery_time_ms": 800,
    "max_recovery_time_ms": 2100
  }
}
```

#### Token Usage Optimization
```json
{
  "estimated_improvements": {
    "token_usage_reduction_percent": 70,
    "response_time_improvement_percent": 35
  }
}
```

### Cleanup Performance Monitoring

**Endpoint:** `GET /api/v1/monitoring/health/sessions/cleanup`

**Key Metrics:**
```json
{
  "cleanup_operations": {
    "total_operations": 45,
    "avg_cleanup_time_ms": 125.5,
    "total_sessions_cleaned": 234,
    "total_memory_freed_mb": 23.4
  },
  "memory_management": {
    "capacity_percentage": 15.2,
    "oldest_session_age_hours": 0.75
  }
}
```

**Monitoring Commands:**
```bash
# Cleanup efficiency
curl -s http://localhost:8000/api/v1/monitoring/health/sessions/cleanup | jq '.cleanup_effectiveness'

# Memory capacity
curl -s http://localhost:8000/api/v1/monitoring/health/sessions/cleanup | jq '.memory_management.capacity_percentage'
```

## Session Management Monitoring

### Session Analytics

**Endpoint:** `GET /api/v1/monitoring/sessions/analytics`

**Comprehensive Session Metrics:**
```json
{
  "session_metrics": {
    "total_sessions": 25,
    "total_messages": 247,
    "recent_sessions_24h": 5,
    "recent_messages_24h": 42,
    "average_messages_per_session": 9.88,
    "cache_hit_ratio": 0.847
  },
  "operation_performance": {
    "send_message": {
      "count": 247,
      "avg_duration_ms": 850.5
    },
    "create_session": {
      "count": 25,
      "avg_duration_ms": 245.5
    }
  }
}
```

### Usage Patterns

**Endpoint:** `GET /api/v1/monitoring/sessions/usage?days=7`

**Usage Analysis:**
```json
{
  "session_creation_patterns": {
    "2025-01-27": 5,
    "2025-01-26": 3,
    "2025-01-25": 8
  },
  "message_activity_patterns": {
    "2025-01-27": 42,
    "2025-01-26": 28,
    "2025-01-25": 67
  },
  "activity_summary": {
    "average_sessions_per_day": 5.3,
    "average_messages_per_day": 45.7
  }
}
```

**Monitoring Commands:**
```bash
# Daily usage patterns
curl -s "http://localhost:8000/api/v1/monitoring/sessions/usage?days=7" | jq '.activity_summary'

# Session creation trends
curl -s "http://localhost:8000/api/v1/monitoring/sessions/usage?days=7" | jq '.session_creation_patterns'
```

## Alerting and Thresholds

### Critical Alerts

#### Session Management Alerts
```bash
# Cache hit ratio too low
CACHE_HIT_RATIO=$(curl -s http://localhost:8000/api/v1/monitoring/health/sessions | jq -r '.session_management.cache_performance.cache_hit_ratio')
if (( $(echo "$CACHE_HIT_RATIO < 0.3" | bc -l) )); then
  echo "CRITICAL: Cache hit ratio is $CACHE_HIT_RATIO (< 30%)"
fi

# Memory usage too high
MEMORY_USAGE=$(curl -s http://localhost:8000/api/v1/monitoring/health/sessions | jq -r '.session_management.memory_usage.usage_percentage')
if (( $(echo "$MEMORY_USAGE > 90" | bc -l) )); then
  echo "CRITICAL: Session memory usage is $MEMORY_USAGE% (> 90%)"
fi

# Cleanup overdue
CLEANUP_STATUS=$(curl -s http://localhost:8000/api/v1/monitoring/health/sessions/cleanup | jq -r '.health_indicators.cleanup_frequency')
if [ "$CLEANUP_STATUS" = "overdue" ]; then
  echo "CRITICAL: Session cleanup is overdue"
fi
```

#### System Resource Alerts
```bash
# System memory usage
SYS_MEMORY=$(curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq -r '.system.memory_usage_percent')
if (( $(echo "$SYS_MEMORY > 85" | bc -l) )); then
  echo "CRITICAL: System memory usage is $SYS_MEMORY% (> 85%)"
fi

# Database health
DB_STATUS=$(curl -s http://localhost:8000/api/v1/monitoring/health/detailed | jq -r '.database.status')
if [ "$DB_STATUS" != "healthy" ]; then
  echo "CRITICAL: Database status is $DB_STATUS"
fi
```

### Warning Alerts

#### Performance Degradation
```bash
# Response time degradation
AVG_RESPONSE_TIME=$(curl -s http://localhost:8000/api/v1/monitoring/sessions/analytics | jq -r '.operation_performance.send_message.avg_duration_ms')
if (( $(echo "$AVG_RESPONSE_TIME > 2000" | bc -l) )); then
  echo "WARNING: Average response time is ${AVG_RESPONSE_TIME}ms (> 2000ms)"
fi

# High recovery rate
RECOVERY_RATE=$(curl -s http://localhost:8000/api/v1/monitoring/health/sessions/recovery | jq -r '.recovery_statistics.recovery_rate')
if (( $(echo "$RECOVERY_RATE > 0.05" | bc -l) )); then
  echo "WARNING: Session recovery rate is $RECOVERY_RATE (> 5%)"
fi
```

### Monitoring Script Example

```bash
#!/bin/bash
# oracle_monitoring.sh - Comprehensive monitoring script

BASE_URL="http://localhost:8000"
ALERT_EMAIL="admin@company.com"

# Function to send alert
send_alert() {
  local severity=$1
  local message=$2
  echo "[$severity] $(date): $message"
  # Add email/Slack notification here
}

# Check overall health
HEALTH_STATUS=$(curl -s $BASE_URL/health | jq -r '.status')
if [ "$HEALTH_STATUS" != "healthy" ]; then
  send_alert "CRITICAL" "System health status: $HEALTH_STATUS"
fi

# Check session performance
CACHE_HIT_RATIO=$(curl -s $BASE_URL/api/v1/monitoring/health/sessions | jq -r '.session_management.cache_performance.cache_hit_ratio')
if (( $(echo "$CACHE_HIT_RATIO < 0.5" | bc -l) )); then
  send_alert "WARNING" "Cache hit ratio low: $CACHE_HIT_RATIO"
fi

# Check memory usage
MEMORY_USAGE=$(curl -s $BASE_URL/api/v1/monitoring/health/detailed | jq -r '.system.memory_usage_percent')
if (( $(echo "$MEMORY_USAGE > 80" | bc -l) )); then
  send_alert "WARNING" "High memory usage: $MEMORY_USAGE%"
fi

# Check error rate
ERROR_RATE=$(curl -s $BASE_URL/api/v1/monitoring/health/detailed | jq -r '.errors.error_rate_per_hour')
if (( $(echo "$ERROR_RATE > 5" | bc -l) )); then
  send_alert "WARNING" "High error rate: $ERROR_RATE errors/hour"
fi

echo "Monitoring check completed at $(date)"
```

## Dashboard Setup

### Grafana Dashboard Configuration

#### Session Management Panel
```json
{
  "title": "Session Management",
  "targets": [
    {
      "expr": "oracle_active_sessions",
      "legendFormat": "Active Sessions"
    },
    {
      "expr": "oracle_cache_hit_ratio",
      "legendFormat": "Cache Hit Ratio"
    },
    {
      "expr": "oracle_session_recovery_rate",
      "legendFormat": "Recovery Rate"
    }
  ]
}
```

#### Performance Panel
```json
{
  "title": "Performance Metrics",
  "targets": [
    {
      "expr": "oracle_avg_response_time_ms",
      "legendFormat": "Avg Response Time (ms)"
    },
    {
      "expr": "oracle_token_usage_reduction_percent",
      "legendFormat": "Token Usage Reduction (%)"
    },
    {
      "expr": "oracle_session_creation_time_ms",
      "legendFormat": "Session Creation Time (ms)"
    }
  ]
}
```

### Custom Metrics Collection

#### Prometheus Metrics Export
```python
# Example metrics exporter for Prometheus
from prometheus_client import Gauge, Counter, Histogram

# Session metrics
active_sessions_gauge = Gauge('oracle_active_sessions', 'Number of active sessions')
cache_hit_ratio_gauge = Gauge('oracle_cache_hit_ratio', 'Session cache hit ratio')
session_recovery_counter = Counter('oracle_session_recoveries_total', 'Total session recoveries')

# Performance metrics
response_time_histogram = Histogram('oracle_response_time_seconds', 'Response time distribution')
token_usage_reduction_gauge = Gauge('oracle_token_usage_reduction_percent', 'Token usage reduction percentage')

# Update metrics from health endpoints
def update_metrics():
    health_data = requests.get('http://localhost:8000/api/v1/monitoring/health/sessions').json()
    
    active_sessions_gauge.set(health_data['session_management']['active_sessions'])
    cache_hit_ratio_gauge.set(health_data['session_management']['cache_performance']['cache_hit_ratio'])
    
    performance_data = requests.get('http://localhost:8000/api/v1/monitoring/health/sessions/performance').json()
    token_usage_reduction_gauge.set(performance_data['estimated_improvements']['token_usage_reduction_percent'])
```

## Log Analysis

### Structured Log Analysis

#### Session Lifecycle Events
```bash
# Session creation events
grep "session_created" backend/logs/backend.log | jq -r '.timestamp + " " + .session_id + " " + .cache_size'

# Session expiration events
grep "session_expired" backend/logs/backend.log | jq -r '.timestamp + " " + .session_id + " " + .age_hours'

# Session recovery events
grep "session_recovered" backend/logs/backend.log | jq -r '.timestamp + " " + .session_id + " " + .recovery_time_ms'
```

#### Performance Analysis
```bash
# Slow response analysis
grep "slow_response" backend/logs/backend.log | jq -r '.timestamp + " " + .session_id + " " + .response_time_ms'

# Cache miss analysis
grep "cache_miss" backend/logs/backend.log | jq -r '.timestamp + " " + .session_id + " " + .reason'

# Cleanup operations
grep "session_cleanup" backend/logs/backend.log | jq -r '.timestamp + " " + .sessions_removed + " " + .memory_freed_mb'
```

#### Error Pattern Analysis
```bash
# Gemini API errors
grep "gemini_api_error" backend/logs/backend.log | jq -r '.timestamp + " " + .error_type + " " + .session_id'

# Database errors
grep "database_error" backend/logs/backend.log | jq -r '.timestamp + " " + .operation + " " + .error_message'

# Session management errors
grep "session_management_error" backend/logs/backend.log | jq -r '.timestamp + " " + .operation + " " + .session_id'
```

### Log Aggregation Queries

#### ELK Stack Queries
```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"logger": "gemini_client"}},
        {"range": {"timestamp": {"gte": "now-1h"}}}
      ]
    }
  },
  "aggs": {
    "session_operations": {
      "terms": {"field": "operation.keyword"}
    },
    "avg_response_time": {
      "avg": {"field": "response_time_ms"}
    }
  }
}
```

#### Splunk Queries
```splunk
# Session performance over time
index=oracle source="backend.log" logger="session_chat_service" 
| timechart avg(response_time_ms) by operation

# Cache hit ratio trend
index=oracle source="backend.log" logger="gemini_client" operation="get_or_create_session"
| eval cache_result=if(cache_hit="true", "hit", "miss")
| timechart count by cache_result

# Error rate analysis
index=oracle source="backend.log" level="ERROR"
| timechart count by error_type
```

## Best Practices

### Monitoring Frequency

- **Health Checks:** Every 30 seconds
- **Performance Metrics:** Every 1 minute
- **Usage Analytics:** Every 5 minutes
- **Detailed Diagnostics:** Every 15 minutes

### Retention Policies

- **Real-time Metrics:** 24 hours
- **Hourly Aggregates:** 30 days
- **Daily Summaries:** 1 year
- **Raw Logs:** 7 days (configurable)

### Alert Escalation

1. **Level 1 (Info):** Log to monitoring system
2. **Level 2 (Warning):** Send notification to team
3. **Level 3 (Critical):** Page on-call engineer
4. **Level 4 (Emergency):** Escalate to management

### Performance Baselines

Establish baselines for key metrics:

```bash
# Collect baseline metrics
curl -s http://localhost:8000/api/v1/monitoring/health/sessions/performance > baseline_performance.json
curl -s http://localhost:8000/api/v1/monitoring/sessions/analytics > baseline_analytics.json

# Compare current vs baseline
python scripts/compare_performance.py baseline_performance.json current_performance.json
```

This monitoring guide provides comprehensive coverage of Oracle Chat AI's observability features, enabling effective monitoring, alerting, and performance optimization of the persistent session management system.