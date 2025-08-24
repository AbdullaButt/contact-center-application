# Telnyx Contact Center IVR (DTMF)

Minimal Flask app using **Telnyx Call Control** to:
- answer parked inbound calls,
- play a **DTMF** menu,
- route **1/2/3** to **Sales / Support / Porting** via **SIP**.

> This repo ships with a `app.py` and high‑level diagrams.

---

## Features
- ✅ Inbound **answer** via `/v2/calls/{call_control_id}/actions/answer`
- ✅ **DTMF IVR** via `gather_using_speak` (1 digit, `valid_digits="123"`)
- ✅ **Transfer** to SIP via `/actions/transfer`
- ✅ Idempotent **command_id** on every action
- ✅ Webhooks always return **HTTP 200** (prevents retries)

---

## Prerequisites
- Python **3.10+**
- A Telnyx **API v2 key** (starts with `KEY`)
- A Telnyx **Call Control App** pointing to your webhook
- SIP users (agents) registered on `sip.telnyx.com`

---

## Quickstart
```bash
# 1) Create and activate a virtualenv
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install deps
pip install -r requirements.txt

# 3) Configure environment
cp .env.example .env
# Edit .env and set: TELNYX_API_KEY=KEYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 4) Run
python app.py
# or choose a port: PORT=5000 python app.py

# 5) Expose locally (ngrok)
ngrok http 5000
# Set your Telnyx Call Control webhook URL to:
#   https://<your-subdomain>.ngrok-free.app/webhook
```

> If you run on a different port (e.g., `PORT=3000`), tunnel the same port: `ngrok http 3000`.

---

## Environment
Create a `.env` from the example:

```env
TELNYX_API_KEY=KEYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PORT=5000
FLASK_DEBUG=false
```

---

## How it works
1. **`call.initiated`** → app **answers** the parked call.
2. App starts **DTMF gather** (`gather_using_speak`) for a single digit (1/2/3).
3. **`call.gather.ended`** → app reads `digits` and **transfers** to the mapped SIP.
4. Telnyx **bridges** Caller ↔ Agent (RTP), then **`call.hangup`** is acknowledged.

### Routing map
Edit these in `app.py`:
```python
DEPARTMENT_URIS = {
    "sales":   "sip:userabdullah12879@sip.telnyx.com",
    "support": "sip:userabdullah68947@sip.telnyx.com",
    "porting": "sip:abdulla429@sip.telnyx.com",
}
DIGIT_TO_DEPARTMENT = {"1": "sales", "2": "support", "3": "porting"}
```

---

## Webhooks handled
- `call.initiated` → answer + start IVR
- `call.gather.ended` → read digit + transfer
- `call.hangup` → mark ended

> This app returns **200 OK** to all webhooks, logging any internal errors to avoid platform retries.

---

## Manual tests (cURL)
Use a **fresh** `call_control_id` from your live logs.

**Answer:**
```bash
curl -i -X POST "https://api.telnyx.com/v2/calls/<CCID>/actions/answer"   -H "Authorization: Bearer $TELNYX_API_KEY"   -H "Content-Type: application/json"   -d '{"command_id":"cli-check-001"}'
```

**Transfer:**
```bash
curl -i -X POST "https://api.telnyx.com/v2/calls/<CCID>/actions/transfer"   -H "Authorization: Bearer $TELNYX_API_KEY"   -H "Content-Type: application/json"   -d '{"to":"sip:abdulla429@sip.telnyx.com","command_id":"cli-transfer-001"}'
```

---

## Troubleshooting (quick)
- **401 Authentication failed** → wrong/missing `TELNYX_API_KEY`.
- **422 Invalid Call Control ID** → call ended or wrong leg; use a fresh `CCID`.
- **Transfer 4xx** → SIP user typo or agent not registered.
- **No DTMF** → verify `valid_digits="123"` and you handle `call.gather.ended`.

See `docs/TROUBLESHOOTING.md` for more.

---

## Repository structure (suggested)
```
.
├─ app.py
├─ requirements.txt
├─ .env.example
├─ README.md
└─ docs/
   ├─ ARCHITECTURE.md
   ├─ WEBHOOKS.md
   ├─ CONFIGURATION.md
   ├─ RUNBOOK.md
   ├─ TROUBLESHOOTING.md
   ├─ SECURITY.md
   └─ img/
      ├─ call_flow.png            # <- copy your chosen A/B/C/D/E image here
      └─ call_flow_exec.svg       # optional vector diagram
```

## License
MIT (see `LICENSE`).
