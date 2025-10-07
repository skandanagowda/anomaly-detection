from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
import asyncio, json, os

app = FastAPI()

# --- CORS setup so frontend (localhost:5173) can access backend (localhost:8080) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- In-memory alert store ---
ALERTS = []
SUBSCRIBERS = set()


@app.get("/api/health")
def health():
    """Simple health check."""
    return {"ok": True}


@app.get("/api/alerts")
def get_alerts():
    """Return last 50 alerts (useful for history)."""
    return {"alerts": ALERTS[-50:]}


@app.get("/api/stream/alerts")
async def stream():
    """Server-Sent Events stream for live alerts."""
    async def event_gen():
        q = asyncio.Queue()
        SUBSCRIBERS.add(q)
        try:
            # Send an initial comment so browsers keep the connection open
            yield b": connected\n\n"
            while True:
                data = await q.get()
                yield b"event: alert\n"
                yield f"data: {json.dumps(data)}\n\n".encode()
        finally:
            SUBSCRIBERS.discard(q)

    # ✅ FIX: use StreamingResponse instead of Response
    return StreamingResponse(event_gen(), media_type="text/event-stream")


async def broadcast_alert(alert):
    """Send alert to all connected subscribers."""
    ALERTS.append(alert)
    for q in list(SUBSCRIBERS):
        await q.put(alert)


@app.post("/api/_demo/push")
async def push_demo(alert: dict):
    """Endpoint to manually push a demo alert."""
    await broadcast_alert(alert)
    return {"ok": True}