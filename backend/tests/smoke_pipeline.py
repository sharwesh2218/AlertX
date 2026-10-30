"""
AlertX smoke test: runs the agent chain in backend/main.py order with a fake
FrameResult. No network (email / voice dispatch / image hosting are mocked).

Run:  python tests/smoke_pipeline.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SECRET_KEY", "smoke-test-secret")
os.environ.pop("ALLOW_PUBLIC_IMAGE_HOST", None)  # make sure nothing uploads

from unittest import mock

import numpy as np

# Block the paid voice call before backend.main imports it
import utils.vapi_service as vapi
vapi.trigger_ai_dispatch = mock.Mock(return_value=True)

import backend.main as m  # noqa: E402  (imports the agents)
import agents.alert_agent as alert_mod  # noqa: E402
from agents.alert_agent import AlertAgent  # noqa: E402
from agents.decision_agent import DecisionAgent  # noqa: E402
from agents.detection_agent import DetectionAgent  # noqa: E402
from agents.learning_agent import LearningAgent  # noqa: E402
from agents.threat_agent import ThreatAnalysisAgent  # noqa: E402
from agents.violence_agent import ViolenceAgent  # noqa: E402
from backend.event_store import EventStore  # noqa: E402
from pipeline.detector import FrameResult  # noqa: E402


def make_frame_result():
    return FrameResult(
        detections=[],
        incidents=[{"type": "fight", "confidence": 0.9, "details": "x", "priority": "CRITICAL"}],
        raw_frame=None,
        annotated_frame=np.zeros((480, 640, 3), dtype=np.uint8),
        person_count=3,
    )


def test_full_chain():
    store = EventStore()
    store.clear()
    store._stats.update({"total_events": 0, "by_type": {}})

    send_email = mock.Mock(return_value=True)
    with mock.patch.object(alert_mod, "send_email", send_email), \
         mock.patch.object(m, "trigger_ai_dispatch", vapi.trigger_ai_dispatch):

        detection, threat, decision = DetectionAgent(), ThreatAnalysisAgent(), DecisionAgent()
        violence, alert, learning = ViolenceAgent(), AlertAgent(), LearningAgent()

        data = {
            "frame_result": make_frame_result(),
            "source": "smoke-test",
            "frame_index": 0,
            "recipient_override": "ops@example.com",
        }
        # Same order as backend/main.py::_bg_agent_task
        data = detection.process(data)
        data = threat.process(data)
        data = violence.process(data)   # no-op / no new incident for this frame
        data = decision.process(data)
        data = alert.process(data)
        data = learning.process(data)

    inc = data["incidents"][0]
    for key in ("priority", "severity_label", "summary"):
        assert key in inc, f"incident missing '{key}': {inc}"
    assert isinstance(data["alerts_dispatched"], list), "alerts_dispatched must be a list"

    events = store.get_events(limit=50)
    assert len(events) == 1, f"expected exactly ONE event in EventStore, got {len(events)}: {events}"
    assert events[0]["priority"] == inc["priority"]

    # Email path was exercised, with the recipient override and an image attached
    assert send_email.called, "send_email should be called for a HIGH/CRITICAL incident"
    kwargs = send_email.call_args.kwargs
    assert kwargs["recipient"] == "ops@example.com"
    assert kwargs["image_data"], "annotated frame should be attached"
    assert "/dispatch/police?t=" in kwargs["message"], "email must carry signed dispatch links"
    vapi.trigger_ai_dispatch.assert_not_called()
    print("PASS test_full_chain  ->", inc["priority"], "|", inc["summary"])


def test_clip_incidents_reach_downstream():
    """CLIP incidents must be written to data['incidents'] with all fields later agents need."""
    import torch

    agent = ViolenceAgent()
    if not alert_mod_clip_available():
        print("SKIP test_clip_incidents_reach_downstream (CLIP not installed)")
        return
    # Stub the model so no weights are downloaded: strongly favour 'car accident' (index 1)
    agent._loaded = True
    agent.preprocess = lambda img: torch.zeros(3, 224, 224)
    logits = torch.full((1, len(agent.labels)), -20.0)
    logits[0, 1] = 20.0
    agent.model = lambda img, txt: (logits, None)

    data = {
        "frame_result": make_frame_result(),
        "incidents": [],
        "person_count": 3,
    }
    data["frame_result"].raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    data = agent.process(data)
    clip_inc = [i for i in data["incidents"] if i["type"] == "accident"]
    assert clip_inc, f"CLIP incident missing from data['incidents']: {data['incidents']}"
    for key in ("type", "confidence", "class_name", "count", "person_count",
                "inference_ms", "timestamp", "severity_score"):
        assert key in clip_inc[0], f"CLIP incident missing '{key}'"

    # Threat agent must not overwrite the CLIP severity
    before = clip_inc[0]["severity_score"]
    data = ThreatAnalysisAgent().process(data)
    assert [i for i in data["incidents"] if i["type"] == "accident"][0]["severity_score"] == before
    print("PASS test_clip_incidents_reach_downstream")


def alert_mod_clip_available():
    import agents.violence_agent as v
    return v.CLIP_AVAILABLE


def test_bg_agent_task():
    """Verify backend.main._bg_agent_task itself writes ONE event and runs learning_agent."""
    from backend.models import DBStore

    store = EventStore()
    store.clear()
    store._stats.update({"total_events": 0, "by_type": {}})
    m.alert_agent._last_alert_time.clear()
    m.alert_agent._alerted_files.clear()
    before_learning = m.learning_agent.stats["processed"]
    before_alert = m.alert_agent.stats["processed"]

    send_email = mock.Mock(return_value=True)
    with mock.patch.object(alert_mod, "send_email", send_email), \
         mock.patch.object(m, "trigger_ai_dispatch", vapi.trigger_ai_dispatch), \
         mock.patch.object(DBStore, "save_event", return_value=True):
        m._bg_agent_task(make_frame_result(), "smoke-bg", 1, "ops@example.com")

    events = store.get_events(limit=50)
    assert len(events) == 1, f"_bg_agent_task must write ONE event, got {len(events)}: {events}"
    assert m.alert_agent.stats["processed"] == before_alert + 1, "alert_agent must run once"
    assert m.learning_agent.stats["processed"] == before_learning + 1, "learning_agent must run"
    print("PASS test_bg_agent_task -> 1 event, priority =", events[0]["priority"])


if __name__ == "__main__":
    test_full_chain()
    test_bg_agent_task()
    test_clip_incidents_reach_downstream()
    print("ALL SMOKE TESTS PASSED")

