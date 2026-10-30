"""
AlertX Sentinel — Unit & Regression Tests
Validates briefing generation, category recommendations, uncertainty analysis,
sanitized exports, and pipeline safety.
"""

import json
import sys
import os

# Ensure backend root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.sentinel_agent import SentinelAgent


def test_sentinel_initialization():
    agent = SentinelAgent()
    assert agent.name == "sentinel"
    assert agent.stats["processed"] == 0
    print("[PASS] test_sentinel_initialization")


def test_generate_briefing_full_data():
    agent = SentinelAgent()
    event = {
        "id": "ev-1029",
        "incident_type": "knife",
        "timestamp": "2026-10-30T14:00:00Z",
        "source": "camera_north_01",
        "confidence": 0.88,
        "priority": "HIGH",
        "details": "Knife detected in zone 1",
        "frame_index": 42,
        "acknowledged": True,
        "media_path": "/media/knife_frame.jpg"
    }
    briefing = agent.generate_briefing(event)
    assert briefing["incident_id"] == "ev-1029"
    assert briefing["category"] == "knife"
    assert briefing["priority"] == "HIGH"
    assert briefing["status"] == "ACKNOWLEDGED"
    assert briefing["acknowledged"] is True
    assert briefing["confidence"] == "88.0%"
    assert briefing["evidence"]["has_media"] is True
    assert briefing["evidence"]["media_reference"] == "/media/knife_frame.jpg"
    assert len(briefing["known_facts"]) >= 5
    assert len(briefing["uncertainties"]) >= 3
    assert len(briefing["recommended_response"]) >= 2
    assert len(briefing["checklist"]) >= 5
    print("[PASS] test_generate_briefing_full_data")


def test_generate_briefing_empty_and_missing_data():
    agent = SentinelAgent()
    briefing = agent.generate_briefing({})
    assert briefing["incident_id"] == "UNASSIGNED"
    assert briefing["category"] == "Unknown Event"
    assert briefing["status"] == "PENDING_REVIEW"
    assert briefing["confidence"] == "Confidence Unspecified"
    assert briefing["priority"] == "UNSPECIFIED"
    assert briefing["evidence"]["has_media"] is False
    assert len(briefing["uncertainties"]) >= 3
    print("[PASS] test_generate_briefing_empty_and_missing_data")


def test_generate_briefing_categories():
    agent = SentinelAgent()
    # Weapons
    w_briefing = agent.generate_briefing({"incident_type": "pistol", "confidence": 0.95})
    assert any("weapon" in s["action"].lower() or "lockdown" in s["action"].lower() for s in w_briefing["recommended_response"])

    # Violence / Fight
    f_briefing = agent.generate_briefing({"incident_type": "fight", "confidence": 0.75})
    assert any("patrol" in s["action"].lower() or "first-aid" in s["action"].lower() or "video" in s["action"].lower() for s in f_briefing["recommended_response"])

    # Fire
    fire_briefing = agent.generate_briefing({"incident_type": "fire", "confidence": 0.82})
    assert any("smoke" in s["action"].lower() or "alarm" in s["action"].lower() for s in fire_briefing["recommended_response"])

    # Medical / Fall
    med_briefing = agent.generate_briefing({"incident_type": "fall", "confidence": 0.65})
    assert any("first-aid" in s["action"].lower() or "distress" in s["action"].lower() for s in med_briefing["recommended_response"])

    print("[PASS] test_generate_briefing_categories")


def test_export_sanitization():
    agent = SentinelAgent()
    event = {
        "id": "ev-secret-check",
        "incident_type": "suspicious",
        "token": "SECRET_JWT_TOKEN",
        "password": "SUPER_SECRET_PASSWORD",
        "credentials": {"key": "secret"}
    }
    # JSON export
    raw_json = agent.export_report_json(event)
    data = json.loads(raw_json)
    assert data["incident_summary"]["id"] == "ev-secret-check"
    assert "token" not in raw_json
    assert "SECRET_JWT_TOKEN" not in raw_json
    assert "SUPER_SECRET_PASSWORD" not in raw_json

    # HTML export
    raw_html = agent.export_report_html(event)
    assert "<!DOCTYPE html>" in raw_html
    assert "ev-secret-check" in raw_html
    assert "SECRET_JWT_TOKEN" not in raw_html
    assert "SUPER_SECRET_PASSWORD" not in raw_html
    print("[PASS] test_export_sanitization")


def test_pipeline_process_safety():
    agent = SentinelAgent()
    # Normal pipeline data
    data = {
        "incidents": [
            {"type": "knife", "confidence": 0.85, "priority": "HIGH"},
            {"type": "anomaly", "confidence": 0.50, "priority": "LOW"}
        ]
    }
    enriched = agent.process(data)
    assert "sentinel_briefing" in enriched["incidents"][0]
    assert enriched["incidents"][0]["sentinel_briefing"]["category"] == "knife"
    assert "sentinel_briefing" in enriched["incidents"][1]
    assert agent.stats["processed"] == 1

    # Malformed data (should never raise)
    bad_data = {"incidents": "not-a-list"}
    agent.process(bad_data)
    assert agent.stats["processed"] == 2
    print("[PASS] test_pipeline_process_safety")


if __name__ == "__main__":
    test_sentinel_initialization()
    test_generate_briefing_full_data()
    test_generate_briefing_empty_and_missing_data()
    test_generate_briefing_categories()
    test_export_sanitization()
    test_pipeline_process_safety()
    print("\nALL SENTINEL TESTS PASSED!")

