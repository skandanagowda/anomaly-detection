from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from datetime import datetime
import asyncio, json, os

app = FastAPI()

# --- CORS so frontend (localhost:5173) can access backend (localhost:8080) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory stores ---
ALERTS: list[dict] = []
SUBSCRIBERS: set[asyncio.Queue] = set()

# Simple per-user state for demo scoring
KNOWN_DEVICES: dict[str, set[str]] = {}  # user_id -> set(devices)
LAST_GEO: dict[str, str] = {}            # user_id -> last geo string


# -------------------- Health & History --------------------
@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/alerts")
def get_alerts():
    return {"alerts": ALERTS[-50:]}


# -------------------- SSE Stream --------------------
@app.get("/api/stream/alerts")
async def stream():
    """Server-Sent Events stream for live alerts."""
    async def event_gen():
        q: asyncio.Queue = asyncio.Queue()
        SUBSCRIBERS.add(q)
        try:
            # initial keepalive comment
            yield b": connected\n\n"
            while True:
                data = await q.get()
                yield b"event: alert\n"
                yield f"data: {json.dumps(data)}\n\n".encode()
        finally:
            SUBSCRIBERS.discard(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


async def broadcast_alert(alert: dict):
    """Send alert to all connected subscribers and save to history."""
    ALERTS.append(alert)
    for q in list(SUBSCRIBERS):
        await q.put(alert)


# -------------------- Demo push endpoint --------------------
@app.post("/api/_demo/push")
async def push_demo(alert: dict):
    await broadcast_alert(alert)
    return {"ok": True}


# -------------------- Scoring (new) --------------------
def score_session(s: dict) -> dict:
    """
    s example:
      {"user_id":"u_001","ts":"2025-10-08T03:11:00Z","geo":"US-NY","device":"Mac-Chrome","fail_auths":2}
    returns:
      {"final_risk": float, "reasons": [...], "risk_level": "LOW|MED|HIGH"}
    """
    uid = s.get("user_id", "?")
    geo = s.get("geo")
    dev = s.get("device")
    ts = s.get("ts", "")
    fail = int(s.get("fail_auths", 0))

    # time features
    hour = 0
    try:
        hour = datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
    except Exception:
        pass
    is_off_hours = int(hour < 6 or hour > 22)

    # device novelty (per user)
    is_new_device = 0
    dset = KNOWN_DEVICES.setdefault(uid, set())
    if dev and dev not in dset:
        is_new_device = 1
        dset.add(dev)

    # naive "impossible travel" (just geo changed)
    impossible_travel = 0
    if uid in LAST_GEO and geo and LAST_GEO[uid] and LAST_GEO[uid] != geo:
        impossible_travel = 1
    if geo:
        LAST_GEO[uid] = geo

    # simple weighted score (demo)
    reasons: list[str] = []
    score = 0.0
    if is_off_hours:
        reasons.append("off_hours")
        score += 0.35
    if is_new_device:
        reasons.append("new_device")
        score += 0.25
    if impossible_travel:
        reasons.append("impossible_travel")
        score += 0.25
    if fail >= 3:
        reasons.append("many_failed_auths")
        score += 0.20

    score = min(0.99, round(score, 2))
    level = "LOW" if score < 0.35 else ("MED" if score < 0.65 else "HIGH")
    return {"final_risk": score, "reasons": reasons, "risk_level": level}


@app.post("/api/score")
async def score_and_maybe_alert(session: dict = Body(...)):
    """
    Scores a session. If MED/HIGH, broadcasts an alert to the SSE stream
    and stores it in history.
    """
    res = score_session(session)
    out = {**session, **res}
    if res["risk_level"] in ("MED", "HIGH"):
        await broadcast_alert(out)
    return res
