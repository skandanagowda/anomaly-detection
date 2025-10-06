from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json, os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"]
)

ALERTS = []
SUBSCRIBERS = set()

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/alerts")
def get_alerts():
    return {"alerts": ALERTS[-50:]}

@app.get("/api/stream/alerts")
async def stream():
    async def event_gen():
        q = asyncio.Queue()
        SUBSCRIBERS.add(q)
        try:
            while True:
                data = await q.get()
                yield f"event: alert\\n".encode()
                yield f"data: {json.dumps(data)}\\n\\n".encode()
        finally:
            SUBSCRIBERS.discard(q)
    return Response(event_gen(), media_type="text/event-stream")

async def broadcast_alert(alert):
    ALERTS.append(alert)
    for q in list(SUBSCRIBERS):
        await q.put(alert)

@app.post("/api/_demo/push")
async def push_demo(alert: dict):
    await broadcast_alert(alert)
    return {"ok": True}