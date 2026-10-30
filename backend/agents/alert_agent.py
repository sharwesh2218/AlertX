"""
AlertX — Alert Agent
Dispatches alerts to the event store and console.
Includes cooldown logic to prevent duplicate consecutive alerts.
"""

import time
import cv2
import logging
import smtplib
import ssl
from datetime import datetime
from email.header import Header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from agents.base_agent import BaseAgent
from backend.config import (
    ALERT_COOLDOWN,
    FRONTEND_URL,
    MAIL_SERVER,
    MAIL_PORT,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_RECIPIENT,
)
from backend.auth import make_dispatch_token
from backend.event_store import Event, EventStore
from utils.image_host import upload_frame
# Import for updating global context
import backend.main as main_module

logger = logging.getLogger("alertx.agent.alert")


def send_email(subject, message, image_data=None, recipient=None) -> bool:
    """
    Send an HTML alert email via SMTP (STARTTLS). `message` is the HTML body;
    `image_data` (JPEG bytes) is attached if provided.
    Never raises: returns True on success, False otherwise.
    """
    to_addr = recipient or MAIL_RECIPIENT
    if not (MAIL_USERNAME and MAIL_PASSWORD and to_addr):
        logger.warning("📧 Email alert skipped: MAIL_USERNAME / MAIL_PASSWORD / recipient not configured.")
        return False
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = MAIL_USERNAME
        msg["To"] = to_addr
        msg.attach(MIMEText(message, "html", "utf-8"))
        if image_data:
            img = MIMEImage(image_data, _subtype="jpeg")
            img.add_header("Content-Disposition", "attachment", filename="incident.jpg")
            msg.attach(img)

        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_USERNAME, [to_addr], msg.as_string())
        logger.info(f"📧 Email alert sent to {to_addr}")
        return True
    except Exception as e:
        logger.error(f"📧 Email alert failed: {e}")
        return False


class AlertAgent(BaseAgent):
    """
    AlertAgent — Dispatches notifications to Email.
    Includes smart de-duplication for uploaded files.
    """

    def __init__(self):
        super().__init__("alert")
        self._store = EventStore()
        self._last_alert_time: Dict[str, float] = {}  # incident_type → timestamp
        self._alerted_files = set() # Track already alerted files

    def _should_alert(self, incident_type: str) -> bool:
        now = time.time()
        last = self._last_alert_time.get(incident_type, 0)
        if now - last >= ALERT_COOLDOWN:
            self._last_alert_time[incident_type] = now
            return True
        return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        incidents = data.get("incidents", [])
        source = data.get("source", "live")
        frame_index = data.get("frame_index", 0)
        alerts_dispatched = []

        # ── Grouping ──────────────────────────────────
        # Only process the highest confidence incident of each type per frame
        unique_incidents = {}
        for inc in incidents:
            itype = inc["type"]
            if itype not in unique_incidents or inc["confidence"] > unique_incidents[itype]["confidence"]:
                unique_incidents[itype] = inc

        for itype, inc in unique_incidents.items():
            if not self._should_alert(itype):
                continue

            event = Event(
                incident_type=itype,
                severity=inc.get("severity_label", "LOW"),
                priority=inc.get("priority", "LOW"),
                confidence=inc["confidence"],
                details=inc.get("summary", ""),
                source=source,
                frame_index=frame_index,
            )
            self._store.add_event(event)
            event_dict = event.to_dict()
            alerts_dispatched.append(event_dict)

            # Console alert with fallback for missing priority
            prio = inc.get("priority", "LOW")
            icon = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "🔔", "LOW": "ℹ️"}.get(prio, "📋")
            msg = f"{icon} [{prio}] {inc.get('summary', 'Unknown Event')}"
            self.logger.warning(msg)

            if prio in ["HIGH", "CRITICAL"]:
                # Get the evidence frame
                evidence_frame = None
                media_url = None
                frame_result = data.get("frame_result")
                
                if frame_result and frame_result.annotated_frame is not None:
                    evidence_frame = frame_result.annotated_frame
                    # Still upload a link as a secondary fallback
                    media_url = upload_frame(evidence_frame)
                
                # ── DISPATCH ────────────────────────────
                # Deduplication Logic
                # ── ALIGNMENT & DEDUPLICATION ────────────────
                source_name = data.get("source", "live")
                incident_type = itype.upper()
                priority = prio.upper()
                
                can_alert = False
                if source_name == "live":
                    elapsed = time.time() - self._last_alert_time.get(incident_type, 0)
                    if elapsed >= ALERT_COOLDOWN:
                        can_alert = True
                    else:
                        logger.info(f"⏳ Cooldown: {incident_type} alert squelched ({int(ALERT_COOLDOWN - elapsed)}s left)")
                else:
                    if source_name not in self._alerted_files:
                        can_alert = True
                    else:
                        logger.info(f"⏭️ Deduplication: File '{source_name}' already notified.")

                if not can_alert:
                    continue

                # ── PREPARE MEDIA ──────────────────────────
                image_bytes = None
                if frame_result is not None and frame_result.annotated_frame is not None:
                    try:
                        _, buffer = cv2.imencode('.jpg', frame_result.annotated_frame)
                        image_bytes = buffer.tobytes()
                    except Exception as ie:
                        logger.error(f"Image Encoding Error: {ie}")

                # ── DISPATCH ──────────────────────────────
                summary = data.get("high_priority_summary") or inc.get("summary", "No details")
                # Update global context for Voice AI
                main_module._last_high_priority_event = summary

                # Signed, expiring links for the emailed dispatch buttons
                tok_police = make_dispatch_token("police")
                tok_security = make_dispatch_token("security")
                tok_ambulance = make_dispatch_token("ambulance")
                
                alert_msg = f"""
                <html>
                    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; padding: 20px;">
                        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                            <div style="background-color: #ef4444; color: white; padding: 15px; text-align: center;">
                                <h2 style="margin: 0;">🚨 ALERTX SECURITY WARNING</h2>
                            </div>
                            <div style="padding: 20px; color: #1f2937;">
                                <h3 style="margin-top: 0;">Incident: {incident_type}</h3>
                                <p style="margin: 5px 0;"><strong>Priority:</strong> <span style="color: #ef4444; font-weight: bold;">{priority}</span></p>
                                <p style="margin: 5px 0;"><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                                <p style="margin: 5px 0;"><strong>Source:</strong> {source_name}</p>
                                
                                <div style="background-color: #fef2f2; padding: 15px; border-left: 4px solid #ef4444; margin: 20px 0; border-radius: 0 4px 4px 0;">
                                    <strong>AI Analysis:</strong> {summary}
                                </div>
                                
                                <div style="margin-top: 30px;">
                                    <h4 style="margin-bottom: 15px; text-align: center; color: #4b5563;">⚡ Voice Agent Dispatch</h4>
                                    <div style="text-align: center;">
                                        <a href="{main_module.PUBLIC_URL}/dispatch/police?t={tok_police}" style="display: inline-block; padding: 12px 15px; margin: 5px; background-color: #ef4444; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; width: 140px;">Call Police</a>
                                        <a href="{main_module.PUBLIC_URL}/dispatch/security?t={tok_security}" style="display: inline-block; padding: 12px 15px; margin: 5px; background-color: #f59e0b; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; width: 140px;">Call Security</a>
                                        <a href="{main_module.PUBLIC_URL}/dispatch/ambulance?t={tok_ambulance}" style="display: inline-block; padding: 12px 15px; margin: 5px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; width: 140px;">Call Ambulance</a>
                                    </div>
                                </div>
                                
                                <p style="margin-top: 30px; text-align: center; font-size: 13px; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 15px;">
                                    View live camera stream at <br>
                                    <a href="{FRONTEND_URL}" style="color: #3b82f6;">{FRONTEND_URL}</a>
                                </p>
                            </div>
                        </div>
                    </body>
                </html>
                """

                logger.info(f"📧 Sending Email Alert for {incident_type}...")
                success = send_email(
                    subject=f"🚨 {priority} ALERT: {incident_type}",
                    message=alert_msg,
                    image_data=image_bytes,
                    recipient=data.get("recipient_override")
                )

                if success:
                    event_dict["email_sent"] = True
                    if event_dict not in alerts_dispatched:
                        alerts_dispatched.append(event_dict)
                    if source_name == "live":
                        self._last_alert_time[incident_type] = time.time()
                    else:
                        self._alerted_files.add(source_name)

        data["alerts_dispatched"] = alerts_dispatched
        self._processed_count += 1
        return data
