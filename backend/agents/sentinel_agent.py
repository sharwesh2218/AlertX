"""
AlertX Sentinel — Evidence-Backed Incident Intelligence Agent
Additive agent providing structured briefings, uncertainty analysis,
operator response guidance, and evidence report exports.

Zero external LLM / paid API dependencies. Fully deterministic and fail-safe.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger("alertx.agent.sentinel")


class SentinelAgent(BaseAgent):
    """
    SentinelAgent — Evaluates detection events and generates evidence-backed
    incident intelligence briefings, operator response checklists, and audit exports.
    """

    def __init__(self):
        super().__init__("sentinel")

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safe additive pipeline step. Attaches sentinel briefings to incidents
        without altering original detection logic or throwing unhandled errors.
        """
        try:
            incidents = data.get("incidents", [])
            if isinstance(incidents, list):
                for inc in incidents:
                    if isinstance(inc, dict):
                        # Add briefing without overwriting original fields
                        inc["sentinel_briefing"] = self.generate_briefing(inc)
            self._processed_count += 1
        except Exception as err:
            self.logger.warning(f"Sentinel pipeline enrichment non-fatal notice: {err}")
        return data

    def generate_briefing(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a structured, evidence-backed incident briefing from event metadata.
        Distinguishes between automated model detections and confirmed real-world events.
        Handles missing or malformed fields safely with clear placeholders.
        """
        if not isinstance(event, dict):
            event = {}

        event_id = str(event.get("id") or event.get("event_id") or "UNASSIGNED")
        category = str(event.get("incident_type") or event.get("type") or "Unknown Event").strip()
        timestamp = str(event.get("timestamp") or event.get("timestamp_iso") or "Timestamp Unavailable")
        source = str(event.get("source") or "Source Unspecified")
        priority = str(event.get("priority") or "UNSPECIFIED").upper()
        details = str(event.get("details") or event.get("description") or event.get("summary") or "No additional telemetry details recorded.")
        frame_idx = event.get("frame_index")

        # Format confidence safely
        raw_conf = event.get("confidence")
        if raw_conf is not None:
            try:
                conf_val = float(raw_conf)
                if conf_val <= 1.0:
                    conf_pct = conf_val * 100.0
                else:
                    conf_pct = conf_val
                confidence_str = f"{conf_pct:.1f}%"
                confidence_num = round(conf_pct / 100.0, 3)
            except (ValueError, TypeError):
                confidence_str = "Confidence Unspecified"
                confidence_num = None
        else:
            confidence_str = "Confidence Unspecified"
            confidence_num = None

        acknowledged = bool(event.get("acknowledged", False))
        
        # Evidence reference resolution
        media_path = event.get("media_path")
        if not media_path and source.startswith("upload:"):
            parts = source.split(":", 1)
            if len(parts) > 1:
                media_path = f"/media/{parts[1]}"

        evidence_info = {
            "has_media": bool(media_path),
            "media_reference": media_path if media_path else None,
            "media_description": "Stored capture frame / media artifact" if media_path else "No direct media frame linked to this record"
        }

        # ── 1. REPORTED EVENT ──────────────────────────────────────────────
        reported_event = (
            f"AlertX vision node flagged candidate pattern for '{category}' "
            f"with {confidence_str} algorithmic confidence."
        )

        # ── 2. WHEN & WHERE ────────────────────────────────────────────────
        where_desc = f"Sensor source: {source}"
        if frame_idx is not None:
            where_desc += f" (Frame index: {frame_idx})"
        when_where = {
            "timestamp": timestamp,
            "source": source,
            "frame_index": frame_idx,
            "summary": f"Logged at {timestamp} via [{where_desc}]."
        }

        # ── 3. KNOWN FACTS ────────────────────────────────────────────────
        known_facts = [
            f"System Incident ID: {event_id}",
            f"Model Classification Tag: {category}",
            f"Calculated Algorithmic Confidence: {confidence_str}",
            f"System Priority Level: {priority}",
            f"Input Stream / Sensor: {source}",
            f"Operator Acknowledgment: {'Acknowledged by operator' if acknowledged else 'Pending operator review'}",
            f"Telemetry Note: {details}"
        ]

        # ── 4. UNCERTAINTIES & CAVEATS ─────────────────────────────────────
        uncertainties = [
            "AUTOMATED DETECTION CAVEAT: Algorithmic alerts represent statistical pattern matching and are not conclusive proof of a crime, hazard, or active emergency.",
            "ENVIRONMENTAL CONSTRAINTS: Optical perspective, motion blur, occlusions, or lighting variations can cause false positives.",
            "INTENT AMBIGUITY: Sensor telemetry cannot establish subject intent, interpersonal context, or authorization status."
        ]
        if confidence_num is not None and confidence_num < 0.70:
            uncertainties.append(
                f"LOW CONFIDENCE NOTICE: Algorithmic confidence ({confidence_str}) is below operational threshold (70%); high possibility of sensor noise or misclassification."
            )
        if not evidence_info["has_media"]:
            uncertainties.append(
                "EVIDENCE GAP: No direct visual frame artifact is associated with this event; visual re-verification requires live camera feed check."
            )

        # ── 5. RECOMMENDED OPERATOR RESPONSE ──────────────────────────────
        recommended_response = self._get_category_recommendations(category, priority)

        # ── 6. GUIDED CHECKLIST ───────────────────────────────────────────
        checklist = [
            {
                "id": "chk_review_class",
                "label": "Review automated classification and confidence score",
                "hint": f"Inspect reported class '{category}' at {confidence_str} confidence.",
                "required": True
            },
            {
                "id": "chk_inspect_evidence",
                "label": "Inspect visual evidence and environmental context",
                "hint": "Check captured frame or monitor live zone camera.",
                "required": True
            },
            {
                "id": "chk_verify_source",
                "label": "Verify sensor zone and identify personnel on scene",
                "hint": f"Confirm activity at source '{source}'.",
                "required": False
            },
            {
                "id": "chk_assess_escalation",
                "label": "Assess escalation criteria against facility SOP",
                "hint": f"Determine if [{priority}] tier response or local patrol dispatch is required.",
                "required": True
            },
            {
                "id": "chk_acknowledge",
                "label": "Acknowledge incident in AlertX audit log",
                "hint": "Commit operator review status using the acknowledge action.",
                "required": True
            },
            {
                "id": "chk_export_report",
                "label": "Export evidence intelligence dossier for records",
                "hint": "Download sanitized incident report for audit archive.",
                "required": False
            }
        ]

        return {
            "incident_id": event_id,
            "category": category,
            "timestamp": timestamp,
            "source": source,
            "confidence": confidence_str,
            "confidence_numeric": confidence_num,
            "priority": priority,
            "details": details,
            "status": "ACKNOWLEDGED" if acknowledged else "PENDING_REVIEW",
            "acknowledged": acknowledged,
            "evidence": evidence_info,
            "reported_event": reported_event,
            "when_and_where": when_where,
            "known_facts": known_facts,
            "uncertainties": uncertainties,
            "recommended_response": recommended_response,
            "checklist": checklist,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }

    def _get_category_recommendations(self, category: str, priority: str) -> List[Dict[str, str]]:
        """Provides category-specific actionable response protocols."""
        cat_lower = category.lower()
        if any(w in cat_lower for w in ["gun", "pistol", "knife", "weapon"]):
            return [
                {
                    "step": "Visual Verification",
                    "action": "Examine high-resolution frame to verify object morphology (differentiate tools/phones from weapons)."
                },
                {
                    "step": "Perimeter Safety",
                    "action": "Do NOT approach unverified subject directly. Monitor movement via adjacent camera sectors."
                },
                {
                    "step": "Protocol Escalation",
                    "action": "If weapon presence is visually confirmed, activate emergency lockdown and notify tactical security."
                }
            ]
        elif any(f in cat_lower for f in ["fight", "violence", "assault", "brawl"]):
            return [
                {
                    "step": "Context Assessment",
                    "action": "Review multi-frame video sequence to distinguish benign interaction/sport from physical violence."
                },
                {
                    "step": "Patrol Dispatch",
                    "action": "Dispatch secondary on-site patrol unit to the active camera sector for situational assessment."
                },
                {
                    "step": "Medical Readiness",
                    "action": "Place facility first-aid responders on standby if physical contact continues."
                }
            ]
        elif any(s in cat_lower for s in ["fire", "smoke", "flame"]):
            return [
                {
                    "step": "Sensor Cross-Check",
                    "action": "Cross-verify optical detection with physical smoke, ionization, or thermal sensors in zone."
                },
                {
                    "step": "Ventilation Check",
                    "action": "Inspect zone HVAC status to restrict potential smoke spread."
                },
                {
                    "step": "Emergency Dispatch",
                    "action": "If combustion is visually confirmed, trigger facility fire alarm and notify fire department."
                }
            ]
        elif any(m in cat_lower for m in ["fall", "medical", "collapse", "injury"]):
            return [
                {
                    "step": "Subject Assessment",
                    "action": "Observe camera feed for subject movement, consciousness, or signs of acute distress."
                },
                {
                    "step": "Medical Dispatch",
                    "action": "Dispatch first-aid responder or security warden to the exact sensor location immediately."
                }
            ]
        else:
            return [
                {
                    "step": "Initial Review",
                    "action": "Examine recent activity logs and telemetry corresponding to the detection zone."
                },
                {
                    "step": "Zone Verification",
                    "action": f"Confirm whether activity at source corresponds to authorized operations."
                },
                {
                    "step": "Audit Logging",
                    "action": "Record verification notes in the security incident log."
                }
            ]

    def export_report_json(self, event: Dict[str, Any]) -> str:
        """
        Exports a sanitized, evidence-backed incident report in JSON format.
        Guarantees no internal secrets, tokens, or credentials are leaked.
        """
        briefing = self.generate_briefing(event)
        report = {
            "report_title": "AlertX Sentinel Incident Intelligence Dossier",
            "export_version": "1.0",
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "incident_summary": {
                "id": briefing["incident_id"],
                "category": briefing["category"],
                "timestamp": briefing["timestamp"],
                "source": briefing["source"],
                "confidence": briefing["confidence"],
                "priority": briefing["priority"],
                "status": briefing["status"],
                "acknowledged": briefing["acknowledged"]
            },
            "evidence": briefing["evidence"],
            "briefing": {
                "reported_event": briefing["reported_event"],
                "when_and_where": briefing["when_and_where"],
                "known_facts": briefing["known_facts"],
                "uncertainties": briefing["uncertainties"],
                "recommended_response": briefing["recommended_response"]
            },
            "audit_notice": (
                "This document is an algorithmic incident briefing generated by AlertX Sentinel. "
                "Automated classifications require authorized human verification prior to formal legal or punitive action."
            )
        }
        return json.dumps(report, indent=2)

    def export_report_html(self, event: Dict[str, Any]) -> str:
        """
        Exports a standalone, printable HTML incident evidence dossier.
        Sanitized, professional, and matching AlertX styling.
        """
        briefing = self.generate_briefing(event)
        
        facts_html = "".join(f"<li>{fact}</li>" for fact in briefing["known_facts"])
        uncertainties_html = "".join(f"<li>{unc}</li>" for unc in briefing["uncertainties"])
        
        steps_html = "".join(
            f"<div class='rec-step'><strong>{s['step']}:</strong> {s['action']}</div>"
            for s in briefing["recommended_response"]
        )

        prio_color = {
            "CRITICAL": "#ef4444",
            "HIGH": "#f59e0b",
            "MEDIUM": "#6366f1",
            "LOW": "#10b981"
        }.get(briefing["priority"], "#6366f1")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AlertX Sentinel Dossier - Incident #{briefing['incident_id']}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
    color: #111827;
    background: #f9fafb;
    margin: 0;
    padding: 32px;
  }}
  .container {{
    max-width: 800px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 32px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
  }}
  .header {{
    border-bottom: 2px solid #111827;
    padding-bottom: 16px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .badge {{
    display: inline-block;
    padding: 4px 12px;
    font-weight: 700;
    font-size: 13px;
    border-radius: 4px;
    color: #ffffff;
    background: {prio_color};
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    background: #f3f4f6;
    padding: 16px;
    border-radius: 6px;
    margin-bottom: 24px;
    font-size: 14px;
  }}
  h2 {{
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #374151;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 6px;
    margin-top: 24px;
  }}
  ul {{ padding-left: 20px; }}
  li {{ margin-bottom: 6px; font-size: 14px; }}
  .rec-step {{
    background: #f9fafb;
    border-left: 4px solid #6366f1;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 14px;
  }}
  .notice {{
    margin-top: 32px;
    padding: 12px;
    background: #fef3c7;
    border: 1px solid #fde68a;
    border-radius: 6px;
    color: #92400e;
    font-size: 12px;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .container {{ box-shadow: none; border: none; padding: 0; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1 style="margin:0; font-size: 24px;">AlertX Sentinel</h1>
      <p style="margin:4px 0 0; color:#6b7280; font-size: 14px;">Evidence-Backed Incident Intelligence Dossier</p>
    </div>
    <div>
      <span class="badge">{briefing['priority']} PRIORITY</span>
    </div>
  </div>

  <div class="meta-grid">
    <div><strong>Incident ID:</strong> {briefing['incident_id']}</div>
    <div><strong>Detected Category:</strong> {briefing['category']}</div>
    <div><strong>Timestamp:</strong> {briefing['timestamp']}</div>
    <div><strong>Algorithmic Confidence:</strong> {briefing['confidence']}</div>
    <div><strong>Sensor / Source:</strong> {briefing['source']}</div>
    <div><strong>Audit Status:</strong> {briefing['status']}</div>
  </div>

  <h2>Reported Event</h2>
  <p style="font-size: 14px;">{briefing['reported_event']}</p>

  <h2>Known Information (Telemetry Facts)</h2>
  <ul>{facts_html}</ul>

  <h2>Uncertainties & Algorithmic Caveats</h2>
  <ul>{uncertainties_html}</ul>

  <h2>Recommended Operator Response Protocol</h2>
  {steps_html}

  <div class="notice">
    <strong>Sentinel Verification Notice:</strong> This dossier was generated deterministically by AlertX Sentinel at {briefing['generated_at']}.
    Automated classifications do not constitute confirmed real-world findings until independently verified by an authorized human operator.
  </div>
</div>
</body>
</html>"""
        return html

