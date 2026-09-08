from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, dashboard, health, sites
from app.services.monitoring_scheduler import (
    start_monitoring_scheduler,
    stop_monitoring_scheduler,
)
from app.websocket.manager import manager


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("SITEAEGIS BACKEND STARTING")
    print("=" * 60)

    # Start monitoring scheduler
    try:
        start_monitoring_scheduler()
        print("[STARTUP] Monitoring scheduler started.")
    except Exception as exc:
        print(
            f"[STARTUP ERROR] Could not start monitoring scheduler: {exc}"
        )

    print("[STARTUP] WebSocket endpoint: /ws")
    print("[STARTUP] API endpoint: /api")
    print("[STARTUP] Alerts endpoint: /api/alerts")

    yield

    # Stop monitoring scheduler
    print("[SHUTDOWN] Stopping monitoring scheduler...")

    try:
        stop_monitoring_scheduler()
        print("[SHUTDOWN] Monitoring scheduler stopped.")
    except Exception as exc:
        print(
            f"[SHUTDOWN ERROR] Could not stop monitoring scheduler: {exc}"
        )

    print("=" * 60)
    print("SITEAEGIS BACKEND STOPPED")
    print("=" * 60)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="SiteAegis API",
    description="Real-time web security monitoring platform.",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(
    sites.router,
    prefix="/api",
)

app.include_router(
    dashboard.router,
    prefix="/api",
)

app.include_router(
    alerts.router,
    prefix="/api",
)

app.include_router(
    health.router,
    prefix="/api",
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "name": "SiteAegis",
        "status": "online",
        "message": "SiteAegis backend is running.",
        "api": "/api",
        "websocket": "/ws",
    }


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main SiteAegis WebSocket endpoint.

    Frontend connects to:
        ws://127.0.0.1:8000/ws
    """

    # Register connection ONCE
    await manager.connect(websocket)

    try:
        # ----------------------------------------------------
        # Initial connection confirmation
        # ----------------------------------------------------

        await websocket.send_json(
            {
                "type": "connection",
                "status": "connected",
                "message": "SiteAegis WebSocket is active.",
            }
        )

        print(
            "[WEBSOCKET] Connection confirmation sent."
        )

        # ----------------------------------------------------
        # Keep connection alive
        # ----------------------------------------------------

        while True:
            message = await websocket.receive_text()

            print(
                f"[WEBSOCKET] Received: {message}"
            )

            # ------------------------------------------------
            # Acknowledge frontend messages
            # ------------------------------------------------

            await websocket.send_json(
                {
                    "type": "ack",
                    "message": "Message received.",
                }
            )

    except WebSocketDisconnect:
        print(
            "[WEBSOCKET] Client disconnected normally."
        )

    except Exception as exc:
        print(
            f"[WEBSOCKET ERROR] {exc}"
        )

    finally:
        # ----------------------------------------------------
        # Always remove connection
        # ----------------------------------------------------

        manager.disconnect(websocket)

        print(
            "[WEBSOCKET] Client removed from manager."
        )