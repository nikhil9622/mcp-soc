# MCP SOC Operational Runbook

**Version:** 1.0  
**Last Updated:** 2026-03-22  
**Audience:** DevOps, SRE, Security Engineers

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Service Management](#service-management)
3. [Monitoring & Alerts](#monitoring--alerts)
4. [Common Issues](#common-issues)
5. [Incident Response](#incident-response)
6. [Maintenance Procedures](#maintenance-procedures)
7. [Performance Tuning](#performance-tuning)
8. [Troubleshooting](#troubleshooting)

---

## Quick Reference

### Service Status Commands

```bash
# Check all services
docker-compose ps

# Check logs
docker-compose logs -f --tail=100

# Check specific agent
docker-compose logs -f ingestion

# Check Redis health
docker-compose exec redis redis-cli ping

# Check MongoDB health
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

### Health Check Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Broker API | `GET /api/health` | `{"status": "healthy"}` |
| Redis | `redis-cli ping` | `PONG` |
| MongoDB | `mongosh --eval "db.adminCommand('ping')"` | `{ ok: 1 }` |

### Key Metrics Dashboard

Monitor these metrics in your observability platform:

| Metric | Threshold | Action |
|--------|-----------|--------|
| Event ingestion rate | < 100/sec | Normal |
| Detection latency | < 5 seconds | Normal |
| Alert delivery time | < 60 seconds | Normal |
| Redis memory usage | < 80% | Normal |
| MongoDB disk usage | < 80% | Normal |
| False positive rate | < 20% | Tune detection rules |

---

## Service Management

### Starting Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d ingestion

# Start with rebuild
docker-compose up -d --build

# Scale agents
docker-compose up -d --scale ingestion=3 --scale detection=2
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop specific service
docker-compose stop ingestion

# Stop and remove volumes (data loss!)
docker-compose down -v
```

### Restarting Services

```bash
# Restart all
docker-compose restart

# Restart specific agent
docker-compose restart detection

# Rolling restart (zero downtime)
docker-compose up -d --no-deps --build ingestion
```

---

## Monitoring & Alerts

### Application Logs

**Log Locations:**
```
Docker: docker-compose logs
Local: stdout/stderr
Production: /var/log/mcp-soc/
```

**Log Levels:**
- `DEBUG` - Detailed diagnostic info
- `INFO` - Normal operations
- `WARNING` - Unexpected but handled
- `ERROR` - Operation failed
- `CRITICAL` - System-level failure

**Example Log Queries:**

```bash
# Find errors in last hour
docker-compose logs --since 1h | grep ERROR

# Monitor detection agent
docker-compose logs -f detection | grep "Detection matched"

# Track specific tenant
docker-compose logs | grep "tenant_id=tenant_abc123"
```

### Redis Streams Monitoring

```bash
# Check stream length
redis-cli XLEN soc:events:tenant_abc123

# Check consumer group lag
redis-cli XPENDING soc:events:tenant_abc123 detection-group

# View stream info
redis-cli XINFO STREAM soc:events:tenant_abc123

# Monitor all streams
redis-cli --scan --pattern "soc:*"
```

### MongoDB Monitoring

```bash
# Check database stats
mongosh --eval "db.stats()"

# Check collection sizes
mongosh --eval "db.events.stats()"

# Active operations
mongosh --eval "db.currentOp()"

# Slow queries (>100ms)
mongosh --eval "db.system.profile.find({millis: {\$gt: 100}})"
```

### Performance Metrics

**Key Performance Indicators (KPIs):**

```python
# Example monitoring queries

# Event throughput
db.events.countDocuments({
    "timestamp": {"$gte": ISODate("2024-06-15T00:00:00Z")}
})

# Detection hit rate
total_detections = db.detections.countDocuments()
total_events = db.events.countDocuments()
hit_rate = (total_detections / total_events) * 100

# False positive rate
false_positives = db.alerts.countDocuments({"feedback": "fp"})
total_alerts = db.alerts.countDocuments({"feedback": {"$ne": null}})
fp_rate = (false_positives / total_alerts) * 100

# Average incident resolution time
db.incidents.aggregate([
    {"$match": {"status": "resolved"}},
    {"$project": {
        "resolution_time": {
            "$subtract": ["$resolved_at", "$created_at"]
        }
    }},
    {"$group": {
        "_id": null,
        "avg_time": {"$avg": "$resolution_time"}
    }}
])
```

---

## Common Issues

### Issue: Agents Not Processing Events

**Symptoms:**
- Redis streams filling up
- No detections being created
- Agents showing as running but idle

**Diagnosis:**
```bash
# Check consumer group
redis-cli XINFO GROUPS soc:events:tenant_abc123

# Check agent logs
docker-compose logs detection

# Check for exceptions
docker-compose logs detection | grep -i error
```

**Resolution:**
1. Restart the stuck agent: `docker-compose restart detection`
2. Check for pending messages: `redis-cli XPENDING soc:events:tenant_abc123 detection-group`
3. If deadlocked, create new consumer group:
   ```bash
   redis-cli XGROUP DESTROY soc:events:tenant_abc123 detection-group
   redis-cli XGROUP CREATE soc:events:tenant_abc123 detection-group $
   ```

---

### Issue: High False Positive Rate

**Symptoms:**
- >30% of alerts marked as false positives
- Alert fatigue from analysts
- Detection rules matching too broadly

**Diagnosis:**
```bash
# Check FP rate by rule
db.alerts.aggregate([
    {"$lookup": {
        "from": "detections",
        "localField": "incident_id",
        "foreignField": "incident_id",
        "as": "detections"
    }},
    {"$unwind": "$detections"},
    {"$group": {
        "_id": "$detections.rule_id",
        "total": {"$sum": 1},
        "fp": {"$sum": {"$cond": [{"$eq": ["$feedback", "fp"]}, 1, 0]}}
    }},
    {"$project": {
        "rule_id": "$_id",
        "fp_rate": {"$multiply": [{"$divide": ["$fp", "$total"]}, 100]}
    }},
    {"$sort": {"fp_rate": -1}}
])
```

**Resolution:**
1. Identify noisy rules (high FP rate)
2. Adjust rule thresholds in `detection_rules/*.yml`
3. Add exclusion conditions
4. Test with synthetic data: `pytest tests/test_detection_rules.py`
5. Deploy updated rules and monitor

---

### Issue: MongoDB Slow Queries

**Symptoms:**
- API responses > 1 second
- High CPU on MongoDB container
- Slow dashboard loads

**Diagnosis:**
```bash
# Enable profiling
mongosh --eval "db.setProfilingLevel(1, {slowms: 100})"

# Check slow queries
mongosh --eval "db.system.profile.find().sort({ts: -1}).limit(10)"

# Check missing indexes
mongosh --eval "db.events.explain().find({tenant_id: 'tenant_abc123'})"
```

**Resolution:**
1. Add missing indexes: See `db/init_db.py`
2. Optimize query patterns (always filter by `tenant_id`)
3. Add compound indexes for common queries
4. Consider sharding for large deployments

---

### Issue: Redis Out of Memory

**Symptoms:**
- Redis container restarting
- `OOM` errors in logs
- Streams not accepting new messages

**Diagnosis:**
```bash
# Check memory usage
redis-cli INFO memory

# Check stream sizes
redis-cli --scan --pattern "soc:*" | xargs -I{} redis-cli XLEN {}

# Check eviction policy
redis-cli CONFIG GET maxmemory-policy
```

**Resolution:**
1. Increase Redis memory limit in `docker-compose.yml`
2. Trim old stream entries:
   ```bash
   redis-cli XTRIM soc:events:tenant_abc123 MAXLEN ~ 10000
   ```
3. Set stream TTL in agent configuration
4. Archive old streams to S3
5. Scale horizontally with Redis Cluster

---

## Incident Response

### Severity Levels

| Level | Response Time | Example |
|-------|---------------|---------|
| **P0 - Critical** | < 15 min | Complete outage, data loss |
| **P1 - High** | < 1 hour | Single agent down, degraded performance |
| **P2 - Medium** | < 4 hours | Non-critical feature broken |
| **P3 - Low** | < 1 day | Minor bug, documentation issue |

### P0: Complete Outage

**Response Checklist:**

1. **Assess Impact**
   ```bash
   # Check all services
   docker-compose ps
   
   # Check health endpoint
   curl http://localhost:8000/api/health
   ```

2. **Identify Root Cause**
   ```bash
   # Check recent logs
   docker-compose logs --tail=500
   
   # Check resource usage
   docker stats
   ```

3. **Restore Service**
   - Try restart: `docker-compose restart`
   - Try rebuild: `docker-compose up -d --build`
   - Rollback to last known good: `git checkout <commit> && docker-compose up -d --build`

4. **Notify Stakeholders**
   - Update status page
   - Send incident notification
   - Post mortem within 48 hours

### P1: Agent Down

**Response Checklist:**

1. **Identify Failed Agent**
   ```bash
   docker-compose ps
   ```

2. **Check Logs**
   ```bash
   docker-compose logs --tail=200 <agent-name>
   ```

3. **Restart Agent**
   ```bash
   docker-compose restart <agent-name>
   ```

4. **Monitor Recovery**
   - Check stream processing resumes
   - Verify backlog clears
   - Monitor for recurring failures

---

## Maintenance Procedures

### Weekly Maintenance

**Every Monday, 2:00 AM UTC:**

1. **Backup Databases**
   ```bash
   # MongoDB backup
   mongodump --out=/backups/mongodb/$(date +%Y-%m-%d)
   
   # Redis backup
   redis-cli SAVE
   cp /var/lib/redis/dump.rdb /backups/redis/dump-$(date +%Y-%m-%d).rdb
   ```

2. **Trim Old Streams**
   ```bash
   # Keep last 7 days
   redis-cli --scan --pattern "soc:*" | while read stream; do
       redis-cli XTRIM $stream MAXLEN ~ 100000
   done
   ```

3. **Archive Old Events**
   ```python
   # Archive events older than 90 days to S3
   from datetime import datetime, timedelta
   cutoff = datetime.utcnow() - timedelta(days=90)
   
   old_events = db.events.find({"timestamp": {"$lt": cutoff}})
   # ... upload to S3 and delete from MongoDB
   ```

4. **Update Dependencies**
   ```bash
   pip list --outdated
   # Review and update requirements.txt
   ```

### Monthly Maintenance

**First Sunday of Month, 3:00 AM UTC:**

1. **Review Detection Rules**
   - Analyze false positive rates
   - Tune rule thresholds
   - Add new rules from threat intelligence

2. **Capacity Planning**
   - Review growth trends
   - Project resource needs
   - Plan scaling

3. **Security Audit**
   - Review API key usage
   - Check for unauthorized access
   - Update dependencies for CVEs

---

## Performance Tuning

### Agent Scaling

**When to Scale:**
- Redis stream lag > 1000 messages
- Event processing latency > 10 seconds
- CPU usage > 80% sustained

**How to Scale:**
```bash
# Scale up
docker-compose up -d --scale ingestion=3 --scale detection=2

# Scale down
docker-compose up -d --scale ingestion=1
```

### Database Optimization

**MongoDB Indexes:**
```javascript
// Essential indexes (already created in init_db.py)
db.events.createIndex({"tenant_id": 1, "timestamp": -1})
db.detections.createIndex({"tenant_id": 1, "detected_at": -1})
db.incidents.createIndex({"tenant_id": 1, "status": 1})

// Add custom indexes based on query patterns
db.events.createIndex({"tenant_id": 1, "user": 1, "timestamp": -1})
```

**Redis Configuration:**
```conf
# redis.conf optimizations
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""  # Disable RDB for performance (use AOF)
appendonly yes
appendfsync everysec
```

---

## Troubleshooting

### Debug Mode

Enable debug logging:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in .env file
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart
```

### Interactive Debugging

```bash
# Attach to running container
docker-compose exec detection /bin/bash

# Run Python REPL in container
docker-compose exec detection python

# Execute specific function
docker-compose exec detection python -c "from agents.detection import test_rule; test_rule()"
```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `ConnectionRefusedError: Redis` | Redis not running | `docker-compose up -d redis` |
| `ServerSelectionTimeoutError: MongoDB` | MongoDB not running | `docker-compose up -d mongodb` |
| `AuthenticationError: Anthropic` | Invalid API key | Check `ANTHROPIC_API_KEY` in `.env` |
| `ValidationError: Pydantic` | Invalid data schema | Check input data format |
| `StreamKeyError` | Tenant ID missing | Ensure `tenant_id` in all operations |

---

## Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| On-Call Engineer | +1-555-0100 | Primary |
| Security Lead | +1-555-0101 | P0/P1 |
| Platform Team | platform@example.com | Infrastructure issues |
| Vendor Support (Anthropic) | support@anthropic.com | Claude API issues |

---

## Appendix

### Useful Commands Cheat Sheet

```bash
# Logs
docker-compose logs -f --tail=100 [service]
docker-compose logs --since 1h | grep ERROR

# Restart
docker-compose restart [service]
docker-compose up -d --force-recreate [service]

# Database
redis-cli INFO
mongosh --eval "db.stats()"

# Performance
docker stats
docker-compose top

# Cleanup
docker-compose down -v  # Remove volumes
docker system prune -a  # Clean all Docker resources
```

---

**Document Owner:** DevOps Team  
**Review Cycle:** Monthly  
**Last Reviewed:** 2026-03-22
