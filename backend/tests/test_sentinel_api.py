"""
AlertX Sentinel — Integration Tests for API Endpoints
Verifies authentication enforcement, briefing generation, export endpoints,
and acknowledgement integration.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.main import app, event_store
from backend.event_store import Event
from backend.auth import create_access_token


def test_api_sentinel():
    client = TestClient(app)

    # 1. Create a sample event in event_store
    ev = Event(
        incident_type="knife",
        severity="0.85",
        priority="HIGH",
        confidence=0.89,
        details="Subject observed with metallic blade",
        source="camera_sector_4",
        frame_index=120
    )
    event_store.add_event(ev)
    event_id = ev.id

    # 2. Test unauthenticated access (must return 401)
    res_unauth = client.get(f"/sentinel/briefing/{event_id}")
    assert res_unauth.status_code == 401, f"Expected 401, got {res_unauth.status_code}"
    print("[PASS] Unauthenticated access properly rejected with 401")

    # 3. Test authenticated access
    token = create_access_token({"sub": "admin_test"})
    headers = {"Authorization": f"Bearer {token}"}

    res_briefing = client.get(f"/sentinel/briefing/{event_id}", headers=headers)
    assert res_briefing.status_code == 200, f"Expected 200, got {res_briefing.status_code}"
    b_data = res_briefing.json()
    assert b_data["status"] == "success"
    briefing = b_data["briefing"]
    assert briefing["incident_id"] == event_id
    assert briefing["category"] == "knife"
    assert briefing["confidence"] == "89.0%"
    assert briefing["priority"] == "HIGH"
    assert len(briefing["known_facts"]) >= 4
    assert len(briefing["uncertainties"]) >= 3
    print("[PASS] Authenticated briefing retrieval succeeded")

    # 4. Test 404 for unknown incident
    res_404 = client.get("/sentinel/briefing/nonexistent-999", headers=headers)
    assert res_404.status_code == 404
    print("[PASS] 404 handled gracefully for missing incident")

    # 5. Test JSON export
    res_json = client.get(f"/sentinel/export/{event_id}?format=json", headers=headers)
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    assert f"sentinel-dossier-{event_id}.json" in res_json.headers["content-disposition"]
    print("[PASS] JSON report export succeeded")

    # 6. Test HTML export
    res_html = client.get(f"/sentinel/export/{event_id}?format=html", headers=headers)
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert f"sentinel-dossier-{event_id}.html" in res_html.headers["content-disposition"]
    assert "<!DOCTYPE html>" in res_html.text
    print("[PASS] HTML dossier export succeeded")

    # 7. Test Acknowledgement endpoint
    res_ack = client.post(f"/events/{event_id}/acknowledge", headers=headers)
    assert res_ack.status_code == 200
    assert res_ack.json()["status"] == "acknowledged"

    # Re-fetch briefing to confirm status is now ACKNOWLEDGED
    res_re = client.get(f"/sentinel/briefing/{event_id}", headers=headers)
    assert res_re.json()["briefing"]["status"] == "ACKNOWLEDGED"
    assert res_re.json()["briefing"]["acknowledged"] is True
    print("[PASS] Incident acknowledgement workflow succeeded")


if __name__ == "__main__":
    test_api_sentinel()
    print("\nALL SENTINEL API TESTS PASSED!")

