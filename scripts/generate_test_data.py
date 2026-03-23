"""
Generate simulated test data for MCP SOC
This creates realistic security events, detections, incidents, and alerts
for testing the frontend without needing real AWS CloudTrail data.
"""

import asyncio
from datetime import datetime, timedelta
import random
from motor.motor_asyncio import AsyncIOMotorClient
from shared.config import settings

# Sample data templates
USERS = ["alice", "bob", "charlie", "admin", "developer", "analyst", "manager"]
IPS = ["203.0.113.1", "192.0.2.50", "198.51.100.1", "10.0.0.5", "172.16.0.10"]
ACTIONS = [
    "ConsoleLogin",
    "AssumeRole",
    "PutUserPolicy",
    "CreateAccessKey",
    "DeleteBucket",
    "DescribeInstances",
]

RULE_NAMES = [
    "brute_force_login",
    "privilege_escalation",
    "unusual_access_hours",
    "new_geo_login",
    "root_account_usage",
]

SEVERITIES = ["critical", "high", "medium", "low"]
STATUSES = ["open", "investigating", "resolved", "false_positive"]

INCIDENT_SUMMARIES = [
    {
        "summary": "Brute force attack detected from suspicious IP",
        "what_happened": "5 failed login attempts within 3 minutes from 203.0.113.1",
        "why_suspicious": "Exceeds threshold for T1110 credential access technique",
        "impact": "Admin account at risk of compromise",
        "recommended_action": "Force password reset and enable MFA",
    },
    {
        "summary": "Privilege escalation attempt detected",
        "what_happened": "Non-admin user attempted PutUserPolicy with admin role",
        "why_suspicious": "Unauthorized privilege elevation attempt (T1078)",
        "impact": "Potential unauthorized access to sensitive resources",
        "recommended_action": "Review IAM policies and investigate user activity",
    },
    {
        "summary": "Unusual access hours detected",
        "what_happened": "Login activity outside normal business hours (2:00 AM)",
        "why_suspicious": "Access outside typical 9-17 working hours",
        "impact": "Low - may be legitimate remote work",
        "recommended_action": "Confirm with user if activity was legitimate",
    },
    {
        "summary": "Login from new geographic location",
        "what_happened": "User logged in from Singapore (first time)",
        "why_suspicious": "User typically logs in from US East Coast only",
        "impact": "Possible account compromise or credential theft",
        "recommended_action": "Contact user to verify login and reset credentials",
    },
    {
        "summary": "Root account usage detected",
        "what_happened": "AWS root account used for routine operations",
        "why_suspicious": "Root account should only be used for account management",
        "impact": "High - root access bypasses all IAM controls",
        "recommended_action": "Use IAM users instead; investigate root usage justification",
    },
]


async def generate_events(db, count=50):
    """Generate normalized security events."""
    print(f"Generating {count} security events...")
    events = []
    now = datetime.utcnow()
    
    for i in range(count):
        event_time = now - timedelta(hours=random.randint(1, 72))
        events.append({
            "tenant_id": "demo_tenant",
            "event_id": f"evt_{i:04d}",
            "timestamp": event_time,
            "source": "cloudtrail",
            "user": random.choice(USERS),
            "ip": random.choice(IPS),
            "action": random.choice(ACTIONS),
            "metadata": {
                "event_name": random.choice(ACTIONS),
                "user_agent": "aws-cli/2.13.0",
                "region": random.choice(["us-east-1", "us-west-2", "eu-west-1"]),
            },
            "raw_log_s3_key": f"s3://demo-bucket/logs/event_{i}.json",
        })
    
    await db.events.insert_many(events)
    print(f"✅ Created {len(events)} events")
    return events


async def generate_detections(db, count=30):
    """Generate security detections."""
    print(f"Generating {count} detections...")
    detections = []
    now = datetime.utcnow()
    
    for i in range(count):
        detected_at = now - timedelta(hours=random.randint(1, 48))
        severity = random.choice(SEVERITIES)
        rule = random.choice(RULE_NAMES)
        
        detections.append({
            "tenant_id": "demo_tenant",
            "detection_id": f"det_{i:04d}",
            "event_id": f"evt_{random.randint(0, 49):04d}",
            "rule_name": rule,
            "rule_id": f"sigma_{rule}",
            "severity": severity,
            "detected_at": detected_at,
            "mitre_technique_id": random.choice(["T1110", "T1078", "T1098", "T1136"]),
            "mitre_tactic": random.choice(["credential_access", "privilege_escalation", "persistence"]),
            "score": random.randint(50, 100),
            "metadata": {
                "matched_fields": ["user", "action", "timestamp"],
                "threshold_exceeded": True,
            },
        })
    
    await db.detections.insert_many(detections)
    print(f"✅ Created {len(detections)} detections")
    return detections


async def generate_incidents(db, count=15):
    """Generate security incidents."""
    print(f"Generating {count} incidents...")
    incidents = []
    now = datetime.utcnow()
    
    for i in range(count):
        created_at = now - timedelta(hours=random.randint(1, 36))
        updated_at = created_at + timedelta(hours=random.randint(1, 12))
        severity = random.choice(SEVERITIES)
        status = random.choice(STATUSES)
        summary_data = random.choice(INCIDENT_SUMMARIES)
        
        # Generate detection IDs for this incident
        detection_count = random.randint(1, 5)
        detection_ids = [f"det_{random.randint(0, 29):04d}" for _ in range(detection_count)]
        
        incidents.append({
            "tenant_id": "demo_tenant",
            "incident_id": f"inc_{i:04d}",
            "detection_ids": detection_ids,
            "severity": severity,
            "status": status,
            "created_at": created_at,
            "updated_at": updated_at,
            "entities": {
                "users": [random.choice(USERS) for _ in range(random.randint(1, 3))],
                "ips": [random.choice(IPS) for _ in range(random.randint(1, 2))],
                "hosts": [f"host-{random.randint(1,5)}" for _ in range(random.randint(0, 2))],
            },
            "summary": summary_data,
            "risk_score": random.randint(40, 95),
            "detection_count": detection_count,
        })
    
    await db.incidents.insert_many(incidents)
    print(f"✅ Created {len(incidents)} incidents")
    return incidents


async def generate_alerts(db, incidents):
    """Generate alerts from incidents."""
    print(f"Generating alerts for {len(incidents)} incidents...")
    alerts = []
    
    for i, incident in enumerate(incidents):
        alert = {
            "tenant_id": "demo_tenant",
            "alert_id": f"alt_{i:04d}",
            "incident_id": incident["incident_id"],
            "severity": incident["severity"],
            "title": incident["summary"]["summary"],
            "description": incident["summary"]["what_happened"],
            "sent_at": incident["created_at"],
            "channel": "email",
            "recipient": "security-team@example.com",
            "status": "sent",
            "affected_entity": incident["entities"]["users"][0] if incident["entities"]["users"] else "unknown",
            "source_ip": incident["entities"]["ips"][0] if incident["entities"]["ips"] else "unknown",
        }
        
        # Add feedback for some alerts
        if random.random() > 0.5:
            alert["feedback"] = random.choice(["tp", "fp"])
            alert["feedback_at"] = incident["updated_at"]
            if alert["feedback"] == "fp":
                alert["feedback_note"] = "Confirmed with user - legitimate activity"
            else:
                alert["feedback_note"] = "Security incident confirmed - action taken"
            alert["analyst"] = random.choice(["analyst@example.com", "admin@example.com"])
        
        alerts.append(alert)
    
    await db.alerts.insert_many(alerts)
    print(f"✅ Created {len(alerts)} alerts")
    return alerts


async def main():
    """Generate all test data."""
    print("=" * 60)
    print("MCP SOC - Test Data Generator")
    print("=" * 60)
    print()
    
    # Connect to MongoDB
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB]
    
    # Clear existing test data
    print("\nClearing existing demo data...")
    await db.events.delete_many({"tenant_id": "demo_tenant"})
    await db.detections.delete_many({"tenant_id": "demo_tenant"})
    await db.incidents.delete_many({"tenant_id": "demo_tenant"})
    await db.alerts.delete_many({"tenant_id": "demo_tenant"})
    print("✅ Cleared old data")
    
    print("\n" + "=" * 60)
    print("Generating new test data...")
    print("=" * 60)
    print()
    
    # Generate data
    events = await generate_events(db, count=50)
    detections = await generate_detections(db, count=30)
    incidents = await generate_incidents(db, count=15)
    alerts = await generate_alerts(db, incidents)
    
    # Create indexes
    print("\nCreating database indexes...")
    await db.events.create_index([("tenant_id", 1), ("timestamp", -1)])
    await db.detections.create_index([("tenant_id", 1), ("detected_at", -1)])
    await db.incidents.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.alerts.create_index([("tenant_id", 1), ("sent_at", -1)])
    print("✅ Indexes created")
    
    print("\n" + "=" * 60)
    print("✅ Test Data Generation Complete!")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  • Events:     {len(events)}")
    print(f"  • Detections: {len(detections)}")
    print(f"  • Incidents:  {len(incidents)}")
    print(f"  • Alerts:     {len(alerts)}")
    print()
    print("Tenant ID: demo_tenant")
    print()
    print("You can now:")
    print("  1. Start the frontend: cd frontend && npm run dev")
    print("  2. Visit: http://localhost:3000")
    print("  3. Use tenant_id='demo_tenant' to view this data")
    print()
    
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
