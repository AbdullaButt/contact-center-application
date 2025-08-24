from __future__ import annotations
import os, uuid, logging
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# --- Env / Config -----------------------------------------------------------
load_dotenv(Path(__file__).with_name(".env"), override=True)
TELNYX_API_KEY = (os.getenv("TELNYX_API_KEY") or "").strip()
if not TELNYX_API_KEY or not TELNYX_API_KEY.startswith("KEY"):
    raise RuntimeError("Set TELNYX_API_KEY=KEY... in .env")

API_BASE = "https://api.telnyx.com/v2"
HTTP_TIMEOUT = 8

def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {TELNYX_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# --- App / Logging -----------------------------------------------------------
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ivr")

# --- Departments (1/2/3) ----------------------------------------------------
DEPARTMENT_URIS: Dict[str, str] = {
    "sales":   "sip:xxxxxxxxxxxxxxxxxxx",
    "support": "sip:xxxxxxxxxxxxxxxxxxx",
    "porting": "sip:xxxxxxxxxxxxxxxxxxx",
}
DIGIT_TO_DEPARTMENT: Dict[str, str] = {"1": "sales", "2": "support", "3": "porting"}

# Track to avoid duplicate/late commands
ROUTED_CALLS: set[str] = set()
ENDED_CALLS: set[str] = set()

# --- Telnyx Call Control helpers -------------------------------------------
def _post(url: str, body: Dict[str, Any]) -> Optional[requests.Response]:
    try:
        return requests.post(url, json=body, headers=_headers(), timeout=HTTP_TIMEOUT)
    except Exception as e:
        log.error("POST %s failed: %s", url, e)
        return None

def answer_call(ccid: str) -> bool:
    r = _post(f"{API_BASE}/calls/{ccid}/actions/answer", {"command_id": str(uuid.uuid4())})
    ok = bool(r and r.status_code == 200)
    if not ok:
        log.error("answer failed: %s %s", getattr(r, "status_code", None), getattr(r, "text", ""))
    return ok

def transfer_call(ccid: str, sip_uri: str) -> bool:
    body = {"to": sip_uri, "command_id": str(uuid.uuid4())}
    r = _post(f"{API_BASE}/calls/{ccid}/actions/transfer", body)
    ok = bool(r and r.status_code == 200)
    if not ok:
        log.error("transfer failed: %s %s", getattr(r, "status_code", None), getattr(r, "text", ""))
    return ok

def start_menu(ccid: str) -> None:
    """DTMF menu only."""
    body = {
        "payload": (
            "Welcome to Telnyx Contact Center. "
            "For Sales, press 1. For Support, press 2. For Porting, press 3."
        ),
        "invalid_payload": "Sorry, try again. 1 for Sales, 2 for Support, 3 for Porting.",
        "payload_type": "text",
        "service_level": "premium",
        "voice": "Telnyx.KokoroTTS.af",
        "minimum_digits": 1,
        "maximum_digits": 1,
        "valid_digits": "123",
        "timeout_millis": 8000,
        "command_id": str(uuid.uuid4()),
    }
    r = _post(f"{API_BASE}/calls/{ccid}/actions/gather_using_speak", body)
    if not (r and r.status_code == 200):
        log.error("start_menu failed: %s %s", getattr(r, "status_code", None), getattr(r, "text", ""))

def _extract_digits(event_payload: Dict[str, Any]) -> str:
    d = event_payload.get("digit") or event_payload.get("digits")
    if d:
        return str(d).strip()
    res = event_payload.get("result") or event_payload.get("dtmf") or {}
    if isinstance(res, dict):
        return str(res.get("digits") or res.get("digit") or "").strip()
    return ""

# --- Webhook ----------------------------------------------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    data = payload.get("data", {})
    etype = data.get("event_type")
    ev = data.get("payload", {})

    try:
        if etype == "call.initiated":
            ccid = ev.get("call_control_id")
            if not ccid:
                return jsonify({"status": "missing_call_control_id"}), 200
            if not answer_call(ccid):
                return jsonify({"status": "answer_failed"}), 200
            start_menu(ccid)
            return jsonify({"status": "answered_and_menu_started"}), 200

        elif etype == "call.gather.ended":
            ccid = ev.get("call_control_id")
            if not ccid or ccid in ROUTED_CALLS or ccid in ENDED_CALLS:
                return jsonify({"status": "gather_ignored"}), 200
            digit = _extract_digits(ev)
            dept = DIGIT_TO_DEPARTMENT.get(digit or "")
            if dept:
                if transfer_call(ccid, DEPARTMENT_URIS[dept]):
                    ROUTED_CALLS.add(ccid)
            else:
                start_menu(ccid)  # replay
            return jsonify({"status": "gather_processed", "digit": digit}), 200

        elif etype == "call.hangup":
            ccid = ev.get("call_control_id")
            if ccid:
                ENDED_CALLS.add(ccid)
            return jsonify({"status": "received"}), 200

        return jsonify({"status": "received", "event": etype}), 200

    except Exception as e:
        logging.exception("webhook error: %s", e)
        return jsonify({"status": "error"}), 200

# --- Run --------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    log.info("Starting on :%s (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
