"""
AWS CloudTrail Attack Simulator
Sends realistic CloudTrail events to MCP SOC at mcpsoc.dev
All events land in belidenikhilchandan@gmail.com's tenant.
"""

import requests
import time
import random
from datetime import datetime, timezone, timedelta

API_URL = "http://178.128.100.145:8000"
API_KEY = "soc_O5Yo1RbWckPnH2ffrG7OtAf5nMZbbrK9xSaqNd60uFU"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

ATTACKER_IPS = ["185.220.101.47", "194.165.16.11", "45.141.84.120", "91.108.4.200"]
INTERNAL_IPS = ["10.0.1.45", "10.0.2.88", "172.31.12.5"]

def now_iso(offset_minutes=0):
    t = datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

def post(records: list[dict], label: str):
    r = requests.post(f"{API_URL}/ingest/cloudtrail", headers=HEADERS, json={"records": records})
    print(f"  [{r.status_code}] {label} — {len(records)} events")

def sep(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)


# ─── 1. BRUTE FORCE CONSOLE LOGIN (T1110) ────────────────
sep("1. Brute Force Console Login (T1110)")
records = []
for i in range(8):
    records.append({
        "eventTime": now_iso(-i),
        "eventName": "ConsoleLogin",
        "eventSource": "signin.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[0],
        "userIdentity": {"type": "IAMUser", "userName": "admin"},
        "responseElements": {"ConsoleLogin": "Failure"},
        "requestParameters": None,
    })
post(records, "ConsoleLogin Failures x8")
time.sleep(3)


# ─── 2. ROOT ACCOUNT USAGE (T1078.003) ───────────────────
sep("2. Root Account Usage (T1078.003)")
records = [
    {
        "eventTime": now_iso(),
        "eventName": "GetCallerIdentity",
        "eventSource": "sts.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[1],
        "userIdentity": {"type": "Root", "userName": "root", "arn": "arn:aws:iam::123456789012:root"},
        "responseElements": None,
        "requestParameters": None,
    },
    {
        "eventTime": now_iso(-1),
        "eventName": "CreateAccessKey",
        "eventSource": "iam.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[1],
        "userIdentity": {"type": "Root", "userName": "root", "arn": "arn:aws:iam::123456789012:root"},
        "responseElements": {"accessKey": {"accessKeyId": "AKIAIOSFODNN7EXAMPLE"}},
        "requestParameters": {"userName": "root"},
    },
]
post(records, "Root account active")
time.sleep(3)


# ─── 3. PRIVILEGE ESCALATION (T1078.004) ─────────────────
sep("3. Privilege Escalation via IAM (T1078.004)")
records = [
    {
        "eventTime": now_iso(),
        "eventName": "AttachUserPolicy",
        "eventSource": "iam.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": INTERNAL_IPS[0],
        "userIdentity": {"type": "IAMUser", "userName": "dev-nikhil"},
        "responseElements": None,
        "requestParameters": {
            "userName": "dev-nikhil",
            "policyArn": "arn:aws:iam::aws:policy/AdministratorAccess",
        },
    },
    {
        "eventTime": now_iso(-2),
        "eventName": "AddUserToGroup",
        "eventSource": "iam.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": INTERNAL_IPS[0],
        "userIdentity": {"type": "IAMUser", "userName": "dev-nikhil"},
        "responseElements": None,
        "requestParameters": {"groupName": "Administrators", "userName": "dev-nikhil"},
    },
    {
        "eventTime": now_iso(-3),
        "eventName": "PutUserPolicy",
        "eventSource": "iam.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": INTERNAL_IPS[0],
        "userIdentity": {"type": "IAMUser", "userName": "dev-nikhil"},
        "responseElements": None,
        "requestParameters": {
            "userName": "dev-nikhil",
            "policyName": "FullAccess",
            "policyDocument": '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}',
        },
    },
]
post(records, "IAM privilege escalation")
time.sleep(3)


# ─── 4. IAM BACKDOOR — CREATE USER + KEY (T1136) ─────────
sep("4. IAM Backdoor Account (T1136)")
records = [
    {
        "eventTime": now_iso(),
        "eventName": "CreateUser",
        "eventSource": "iam.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[2],
        "userIdentity": {"type": "IAMUser", "userName": "dev-nikhil"},
        "responseElements": {"user": {"userName": "svc-backup-automation", "userId": "AIDACKCEVSQ6C2EXAMPLE"}},
        "requestParameters": {"userName": "svc-backup-automation"},
    },
    {
        "eventTime": now_iso(-1),
        "eventName": "CreateAccessKey",
        "eventSource": "iam.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[2],
        "userIdentity": {"type": "IAMUser", "userName": "dev-nikhil"},
        "responseElements": {"accessKey": {"accessKeyId": "AKIAI44QH8DHBEXAMPLE", "status": "Active"}},
        "requestParameters": {"userName": "svc-backup-automation"},
    },
]
post(records, "Backdoor IAM user created")
time.sleep(3)


# ─── 5. CLOUDTRAIL DISABLED — LOG TAMPERING (T1070) ──────
sep("5. CloudTrail Disabled / Log Tampering (T1070)")
records = [
    {
        "eventTime": now_iso(),
        "eventName": "StopLogging",
        "eventSource": "cloudtrail.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[3],
        "userIdentity": {"type": "IAMUser", "userName": "svc-backup-automation"},
        "responseElements": None,
        "requestParameters": {"name": "arn:aws:cloudtrail:us-east-1:123456789012:trail/main-trail"},
    },
    {
        "eventTime": now_iso(-1),
        "eventName": "DeleteTrail",
        "eventSource": "cloudtrail.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[3],
        "userIdentity": {"type": "IAMUser", "userName": "svc-backup-automation"},
        "responseElements": None,
        "requestParameters": {"name": "arn:aws:cloudtrail:us-east-1:123456789012:trail/main-trail"},
    },
]
post(records, "CloudTrail logging disabled")
time.sleep(3)


# ─── 6. S3 DATA EXFILTRATION (T1530) ─────────────────────
sep("6. S3 Data Exfiltration (T1530)")
records = []
for i in range(15):
    records.append({
        "eventTime": now_iso(-i),
        "eventName": "GetObject",
        "eventSource": "s3.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[0],
        "userIdentity": {"type": "IAMUser", "userName": "svc-backup-automation"},
        "responseElements": None,
        "requestParameters": {
            "bucketName": "company-confidential-hr",
            "key": f"employees/records_{i:04d}.csv",
        },
    })
post(records, "Mass S3 GetObject from sensitive bucket")
time.sleep(3)


# ─── 7. EC2 CRYPTO MINING — LARGE INSTANCE (T1496) ──────
sep("7. EC2 Crypto Mining — RunInstances (T1496)")
records = [
    {
        "eventTime": now_iso(),
        "eventName": "RunInstances",
        "eventSource": "ec2.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": ATTACKER_IPS[1],
        "userIdentity": {"type": "IAMUser", "userName": "svc-backup-automation"},
        "responseElements": {
            "instancesSet": {"items": [{"instanceId": "i-0abcd1234efgh5678", "instanceType": "p3.16xlarge"}]}
        },
        "requestParameters": {
            "instanceType": "p3.16xlarge",
            "imageId": "ami-0abcdef1234567890",
            "minCount": 5,
            "maxCount": 5,
        },
    }
]
post(records, "GPU instance launch (crypto mining)")
time.sleep(3)


# ─── 8. SECURITY GROUP OPENED TO WORLD (T1562) ───────────
sep("8. Security Group — SSH Opened to 0.0.0.0/0 (T1562)")
records = [
    {
        "eventTime": now_iso(),
        "eventName": "AuthorizeSecurityGroupIngress",
        "eventSource": "ec2.amazonaws.com",
        "awsRegion": "us-east-1",
        "sourceIPAddress": INTERNAL_IPS[1],
        "userIdentity": {"type": "IAMUser", "userName": "dev-nikhil"},
        "responseElements": {"return": "true"},
        "requestParameters": {
            "groupId": "sg-0123456789abcdef0",
            "ipPermissions": {
                "items": [{"ipProtocol": "tcp", "fromPort": 22, "toPort": 22,
                            "ipRanges": {"items": [{"cidrIp": "0.0.0.0/0"}]}}]
            },
        },
    }
]
post(records, "SSH opened to world")
time.sleep(3)


print("\n" + "="*55)
print("  ALL SCENARIOS SENT")
print("  Check mcpsoc.dev → Dashboard / Alerts / Incidents")
print("="*55 + "\n")
