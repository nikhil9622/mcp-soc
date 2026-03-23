"""Unit tests for ingestion agent normalization logic."""
import json
from datetime import datetime, timezone

import pytest

from agents.ingestion import (
    _normalize_cloudtrail,
    _normalize_syslog,
    _s3_key,
    _extract_user,
    _extract_ip,
    _extract_action,
)


def test_normalize_cloudtrail_basic():
    raw = {
        "userIdentity": {"type": "IAMUser", "userName": "alice", "arn": "arn:aws:iam::123:user/alice"},
        "eventTime": "2024-06-15T14:30:00Z",
        "eventName": "ConsoleLogin",
        "sourceIPAddress": "1.2.3.4",
        "awsRegion": "us-east-1",
        "eventSource": "signin.amazonaws.com",
    }
    event = _normalize_cloudtrail(raw, "tenant1")
    assert event.tenant_id == "tenant1"
    assert event.user == "alice"
    assert event.ip == "1.2.3.4"
    assert event.action == "ConsoleLogin"
    assert event.source == "cloudtrail"
    assert event.region == "us-east-1"


def test_normalize_cloudtrail_root():
    raw = {
        "userIdentity": {"type": "Root", "arn": "arn:aws:iam::123:root"},
        "eventTime": "2024-06-15T12:00:00Z",
        "eventName": "ConsoleLogin",
        "sourceIPAddress": "9.8.7.6",
        "awsRegion": "us-east-1",
    }
    event = _normalize_cloudtrail(raw, "tenant1")
    assert event.user_type == "Root"
    assert event.user == "root"


def test_normalize_syslog_ssh_failure():
    raw = {
        "message": "Failed password for alice from 10.0.0.1 port 22 ssh2",
        "timestamp": "2024-06-15T14:00:00Z",
        "host": "myserver",
        "file": "/var/log/auth.log",
    }
    event = _normalize_syslog(raw, "tenant1")
    assert event.user == "alice"
    assert event.ip == "10.0.0.1"
    assert event.action == "sshd"
    assert event.source == "syslog"
    assert event.metadata["host"] == "myserver"


def test_normalize_syslog_sudo():
    raw = {
        "message": "sudo: alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/bash",
        "timestamp": "2024-06-15T14:05:00Z",
        "host": "myserver",
    }
    event = _normalize_syslog(raw, "tenant1")
    assert event.action == "sudo"


def test_s3_key_format():
    key = _s3_key("tenant123", "cloudtrail", "evt-abc")
    parts = key.split("/")
    assert parts[0] == "tenant123"
    assert parts[1] == "cloudtrail"
    assert key.endswith("evt-abc.json")


def test_extract_user_for_user():
    assert _extract_user("Failed password for alice from 1.2.3.4 port 22") == "alice"


def test_extract_user_session_opened():
    assert _extract_user("pam_unix(sshd:session): session opened for user bob") == "bob"


def test_extract_ip():
    assert _extract_ip("Failed password for alice from 192.168.1.100 port 22") == "192.168.1.100"


def test_extract_ip_no_match():
    assert _extract_ip("some log with no ip") == "0.0.0.0"


def test_extract_action_sudo():
    assert _extract_action("sudo: alice : command=/bin/bash") == "sudo"


def test_extract_action_sshd():
    assert _extract_action("Failed password from sshd service") == "sshd"
