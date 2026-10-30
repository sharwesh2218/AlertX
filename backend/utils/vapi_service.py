import json
import logging
import os
import re
import threading
from typing import Any, Dict, Optional

import requests
from backend.config import (
    BASE_DIR,
    DISPATCH_PHONE_NUMBER,
    VAPI_API_KEY,
    VAPI_ASSISTANT_ID,
    VAPI_PHONE_NUMBER_ID,
)

logger = logging.getLogger("alertx.vapi")

_CONFIG_PATH = os.path.join(BASE_DIR, ".dispatch_config.json")
_CONFIG_LOCK = threading.Lock()
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")

_LAST_DISPATCH_TLS = threading.local()

SERVICE_LABELS = {
    "POLICE": "Police Emergency Response",
    "AMBULANCE": "Ambulance and Medical Emergency Response",
    "FIRE": "Fire and Rescue Department",
    "SECURITY": "Facility Security Response",
}


def normalize_phone_number(raw: Optional[str]) -> str:
    """
    Normalize a phone number into E.164 format (e.g. '+919876543210' or '+14155552671').
    Returns '' if empty; raises ValueError if non-empty and not valid E.164.
    """
    if raw is None:
        return ""
    cleaned = re.sub(r"[\s\-\(\)\.]", "", str(raw).strip())
    if not cleaned:
        return ""
    if not _E164_RE.match(cleaned):
        raise ValueError(
            "Phone number must include '+' and country code in E.164 format "
            "(for example +919876543210 or +14155552671)."
        )
    return cleaned


def mask_secret(secret: Optional[str]) -> str:
    """Return a masked preview of an API key without exposing the secret."""
    val = (secret or "").strip()
    if not val:
        return ""
    if len(val) <= 6:
        return "•" * len(val)
    return f"{'•' * 8}{val[-4:]}"


def _read_saved_config() -> Dict[str, str]:
    if not os.path.isfile(_CONFIG_PATH):
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if v is not None}
    except Exception as exc:
        logger.warning(f"Could not read dispatch config file: {exc}")
    return {}


def get_dispatch_config() -> Dict[str, str]:
    """
    Resolve active Vapi + Alert Phone Number settings.
    Runtime values saved via dashboard override .env defaults.
    """
    with _CONFIG_LOCK:
        saved = _read_saved_config()

    env_api_key = os.getenv("VAPI_API_KEY", VAPI_API_KEY) or ""
    env_assistant_id = os.getenv("VAPI_ASSISTANT_ID", VAPI_ASSISTANT_ID) or ""
    env_phone_id = os.getenv("VAPI_PHONE_NUMBER_ID", VAPI_PHONE_NUMBER_ID) or ""
    env_dest_phone = os.getenv("DISPATCH_PHONE_NUMBER", DISPATCH_PHONE_NUMBER) or ""

    return {
        "vapi_api_key": (saved.get("vapi_api_key") or env_api_key).strip(),
        "vapi_assistant_id": (saved.get("vapi_assistant_id") or env_assistant_id).strip(),
        "vapi_phone_number_id": (saved.get("vapi_phone_number_id") or env_phone_id).strip(),
        "dispatch_phone_number": (
            saved.get("dispatch_phone_number")
            if "dispatch_phone_number" in saved
            else env_dest_phone
        ).strip(),
    }


def get_public_dispatch_status() -> Dict[str, Any]:
    """Return sanitized dispatch configuration safe for authenticated frontend display."""
    cfg = get_dispatch_config()
    vapi_ready = bool(
        cfg["vapi_api_key"]
        and cfg["vapi_assistant_id"]
        and cfg["vapi_phone_number_id"]
    )
    return {
        "dispatch_phone_number": cfg["dispatch_phone_number"],
        "vapi_configured": vapi_ready,
        "vapi_api_key_set": bool(cfg["vapi_api_key"]),
        "vapi_api_key_masked": mask_secret(cfg["vapi_api_key"]),
        "vapi_assistant_id": cfg["vapi_assistant_id"],
        "vapi_phone_number_id": cfg["vapi_phone_number_id"],
    }


def save_dispatch_config(updates: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """
    Validate and persist updates to Vapi credentials and/or alert destination phone number.
    """
    with _CONFIG_LOCK:
        saved = _read_saved_config()

        if "dispatch_phone_number" in updates and updates["dispatch_phone_number"] is not None:
            saved["dispatch_phone_number"] = normalize_phone_number(updates["dispatch_phone_number"])

        if "vapi_api_key" in updates and updates["vapi_api_key"] is not None:
            raw_key = updates["vapi_api_key"].strip()
            # Ignore masked placeholder if echoed back unchanged
            if raw_key and "•" not in raw_key:
                saved["vapi_api_key"] = raw_key
            elif raw_key == "":
                saved.pop("vapi_api_key", None)

        if "vapi_assistant_id" in updates and updates["vapi_assistant_id"] is not None:
            raw_ast = updates["vapi_assistant_id"].strip()
            if raw_ast:
                saved["vapi_assistant_id"] = raw_ast
            else:
                saved.pop("vapi_assistant_id", None)

        if "vapi_phone_number_id" in updates and updates["vapi_phone_number_id"] is not None:
            raw_ph = updates["vapi_phone_number_id"].strip()
            if raw_ph:
                saved["vapi_phone_number_id"] = raw_ph
            else:
                saved.pop("vapi_phone_number_id", None)

        with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(saved, fh, indent=2)

    return get_public_dispatch_status()


def _set_last_dispatch_info(ok: bool, call_id: str = "", error: str = "", destination: str = "") -> None:
    _LAST_DISPATCH_TLS.info = {
        "ok": ok,
        "call_id": call_id,
        "error": error,
        "destination": destination,
    }


def get_last_dispatch_info() -> Dict[str, Any]:
    return getattr(_LAST_DISPATCH_TLS, "info", {"ok": False, "call_id": "", "error": "", "destination": ""})


def _extract_vapi_error(status_code: int, body_text: str) -> str:
    msg = body_text.strip()
    try:
        parsed = json.loads(body_text)
        if isinstance(parsed, dict):
            raw_msg = parsed.get("message") or parsed.get("error") or msg
            if isinstance(raw_msg, list):
                msg = "; ".join(str(x) for x in raw_msg)
            else:
                msg = str(raw_msg)
    except Exception:
        pass

    if status_code == 401:
        return (
            "Vapi rejected the API key (401 Unauthorized). "
            "Make sure you pasted your Vapi PRIVATE API Key (not the Public Key)."
        )
    return f"Vapi API error ({status_code}): {msg}"


def trigger_ai_dispatch(service: str, incident_details: str, destination_number: str) -> bool:
    """
    Triggers an outbound Vapi Voice AI call to `destination_number`.
    Uses Vapi API v1 (`POST https://api.vapi.ai/call`) with dynamic assistant overrides.
    Returns True on HTTP 201 Created, False otherwise (details via `get_last_dispatch_info()`).
    """
    cfg = get_dispatch_config()
    api_key = cfg["vapi_api_key"]
    assistant_id = cfg["vapi_assistant_id"]
    phone_number_id = cfg["vapi_phone_number_id"]

    try:
        normalized_dest = normalize_phone_number(destination_number)
    except ValueError as ve:
        _set_last_dispatch_info(False, error=str(ve), destination=str(destination_number or ""))
        logger.warning(f"Vapi dispatch aborted — invalid destination number '{destination_number}': {ve}")
        return False

    if not normalized_dest:
        err = "No alert destination phone number configured."
        _set_last_dispatch_info(False, error=err)
        logger.warning(f"Vapi dispatch aborted — {err}")
        return False

    missing = []
    if not api_key:
        missing.append("VAPI_API_KEY (Private Key)")
    if not assistant_id:
        missing.append("VAPI_ASSISTANT_ID")
    if not phone_number_id:
        missing.append("VAPI_PHONE_NUMBER_ID")

    if missing:
        err = (
            f"Vapi Voice AI not fully configured — missing: {', '.join(missing)}. "
            "Open 'Connect / Change Vapi Voice AI Credentials' in the dashboard or add them to backend/.env."
        )
        _set_last_dispatch_info(False, error=err, destination=normalized_dest)
        logger.warning(f"[STUB] Vapi Dispatch skipped ({err}) -> {service} @ {normalized_dest}")
        return False

    svc_key = (service or "EMERGENCY").strip().upper()
    service_label = SERVICE_LABELS.get(svc_key, f"{svc_key.title()} Emergency Response")

    clean_incident = (incident_details or "").strip()
    if not clean_incident or clean_incident == "No recent incident recorded.":
        clean_incident = (
            f"Manual {service_label} alert triggered by the security operator "
            "from the AlertX command dashboard"
        )

    first_message = (
        f"Hello, this is AlertX AI Emergency Dispatch. "
        f"We are requesting immediate {service_label}. "
        f"Incident report: {clean_incident}. Please confirm receipt of this alert."
    )

    payload: Dict[str, Any] = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_number_id,
        "customer": {
            "number": normalized_dest,
        },
        "assistantOverrides": {
            "firstMessage": first_message,
            "variableValues": {
                "service": svc_key,
                "service_label": service_label,
                "incident_details": clean_incident,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info(f"Initiating Vapi AI Call Dispatch for {svc_key} to {normalized_dest}...")

    try:
        response = requests.post("https://api.vapi.ai/call", json=payload, headers=headers, timeout=15)
        if response.status_code in (200, 201):
            resp_data = response.json() if response.content else {}
            call_id = str(resp_data.get("id", ""))
            logger.info(f"AI Voice Dispatch triggered for {svc_key} -> {normalized_dest}. Call ID: {call_id}")
            _set_last_dispatch_info(True, call_id=call_id, destination=normalized_dest)
            return True

        err_msg = _extract_vapi_error(response.status_code, response.text)
        logger.error(err_msg)
        _set_last_dispatch_info(False, error=err_msg, destination=normalized_dest)
        return False
    except Exception as exc:
        err_msg = f"Vapi connection failed: {exc}"
        logger.error(err_msg)
        _set_last_dispatch_info(False, error=err_msg, destination=normalized_dest)
        return False
