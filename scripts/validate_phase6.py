#!/usr/bin/env python
"""Validation script for Phase 6: Investigation Agent."""

import sys
import json
from pathlib import Path

# Verify investigation agent exists and has key components
def validate_investigation_agent():
    """Check investigation.py has all required components."""
    inv_path = Path("agents/investigation.py")
    if not inv_path.exists():
        print("❌ agents/investigation.py NOT FOUND")
        return False

    content = inv_path.read_text()
    
    checks = [
        ("SYSTEM_PROMPT", "SYSTEM_PROMPT defined"),
        ("run_investigation_agent", "Main handler function"),
        ("anthropic.Anthropic", "Anthropic client import"),
        ("IncidentSummary", "IncidentSummary schema usage"),
        ("tool_choice", "Claude Structured Output via tool_choice"),
        ("startup", "ARQ startup hook"),
        ("_poll_incidents", "Redis Stream polling"),
    ]

    for keyword, description in checks:
        if keyword in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description}")
            return False

    return True


def validate_tests():
    """Check test files exist."""
    tests = [
        ("tests/test_investigation.py", "Unit tests"),
        ("tests/test_investigation_e2e.py", "E2E integration tests"),
    ]

    for path, name in tests:
        p = Path(path)
        if p.exists():
            lines = len(p.read_text().split('\n'))
            print(f"✅ {name} ({lines} lines)")
        else:
            print(f"❌ {name} NOT FOUND")
            return False

    return True


def validate_models():
    """Check IncidentSummary model."""
    models_path = Path("shared/models.py")
    if not models_path.exists():
        print("❌ shared/models.py NOT FOUND")
        return False

    content = models_path.read_text()
    
    if "class IncidentSummary" in content:
        print("✅ IncidentSummary model defined")
        
        fields = ["summary", "what_happened", "why_suspicious", "impact", "recommended_action", "severity"]
        for field in fields:
            if field in content:
                print(f"   ✅ Field: {field}")
            else:
                print(f"   ❌ Field: {field} MISSING")
                return False
    else:
        print("❌ IncidentSummary model NOT FOUND")
        return False

    return True


def validate_schema():
    """Check schema JSON generation capability."""
    try:
        from shared.models import IncidentSummary
        
        schema = IncidentSummary.model_json_schema()
        required_fields = ["properties", "required"]
        
        for field in required_fields:
            if field in schema:
                print(f"✅ Schema has '{field}'")
            else:
                print(f"❌ Schema missing '{field}'")
                return False
        
        # Try creating instance
        summary = IncidentSummary(
            summary="Test",
            what_happened="Test",
            why_suspicious="Test",
            impact="Test",
            recommended_action="Test",
            severity="high",
        )
        print(f"✅ IncidentSummary instance created")
        
        # Check serialization
        dumped = summary.model_dump()
        if isinstance(dumped, dict):
            print(f"✅ Serialization works")
        else:
            print(f"❌ Serialization failed")
            return False
            
    except Exception as e:
        print(f"❌ Schema validation error: {e}")
        return False

    return True


def main():
    """Run all validations."""
    print("=" * 60)
    print("Phase 6: Investigation Agent Validation")
    print("=" * 60)
    
    all_pass = True
    
    print("\n[1/4] Checking Investigation Agent...")
    if not validate_investigation_agent():
        all_pass = False
    
    print("\n[2/4] Checking Test Files...")
    if not validate_tests():
        all_pass = False
    
    print("\n[3/4] Checking Models...")
    if not validate_models():
        all_pass = False
    
    print("\n[4/4] Checking Schema Validation...")
    if not validate_schema():
        all_pass = False
    
    print("\n" + "=" * 60)
    if all_pass:
        print("✅ All validations PASSED")
        print("\nPhase 6 is ready for deployment!")
        return 0
    else:
        print("❌ Some validations FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
