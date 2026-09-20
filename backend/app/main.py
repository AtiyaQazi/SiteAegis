from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    alerts,
    cameras,
    dashboard,
    health,
    incidents,
    routes,
    safety,
    sites,
    zones,
)

from app.core.database import Base, engine
from app.core.config import settings

# Import all models so SQLAlchemy registers every table
# before Base.metadata.create_all() is executed.
from app import models  # noqa: F401

from app.services.monitoring_scheduler import (
    start_monitoring_scheduler,
    stop_monitoring_scheduler,
)

from app.websocket.manager import manager


# ============================================================
# DATABASE INITIALIZATION
# ============================================================


def initialize_database():
    """
    Create all SQLAlchemy tables that do not already exist.

    The actual database is determined by DATABASE_URL.
    Existing databases/tables are not deleted or recreated.
    """

    print(
        "[DATABASE] Initializing database schema..."
    )

    try:

        Base.metadata.create_all(
            bind=engine
        )

        print(
            "[DATABASE] Database schema initialized successfully."
        )

    except Exception as exc:

        print(
            f"[DATABASE ERROR] Could not initialize database: {exc}"
        )

        raise


# ============================================================
# APPLICATION LIFESPAN
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):

    print("=" * 60)
    print("SITEAEGIS BACKEND STARTING")
    print("=" * 60)

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    initialize_database()

    # --------------------------------------------------------
    # MONITORING SCHEDULER
    # --------------------------------------------------------

    try:

        start_monitoring_scheduler()

        print(
            "[STARTUP] Monitoring scheduler started."
        )

    except Exception as exc:

        print(
            f"[STARTUP ERROR] Could not start monitoring scheduler: {exc}"
        )

    # --------------------------------------------------------
    # STARTUP INFORMATION
    # --------------------------------------------------------

    print(
        "[STARTUP] WebSocket endpoint: /ws"
    )

    print(
        "[STARTUP] API endpoint: /api"
    )

    print(
        "[STARTUP] Scanner endpoint: /api/scan"
    )

    print(
        "[STARTUP] PPE endpoint: /api/scan/ppe"
    )

    print(
        "[STARTUP] Alerts endpoint: /api/alerts"
    )

    print(
        "[STARTUP] Cameras endpoint: /api/cameras"
    )

    print(
        "[STARTUP] Zones endpoint: /api/zones"
    )

    print(
        "[STARTUP] Safety endpoint: /api/safety"
    )

    print(
        "[STARTUP] Incidents endpoint: /api/incidents"
    )

    yield

    # --------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------

    print(
        "[SHUTDOWN] Stopping monitoring scheduler..."
    )

    try:

        stop_monitoring_scheduler()

        print(
            "[SHUTDOWN] Monitoring scheduler stopped."
        )

    except Exception as exc:

        print(
            f"[SHUTDOWN ERROR] Could not stop monitoring scheduler: {exc}"
        )

    print("=" * 60)
    print("SITEAEGIS BACKEND STOPPED")
    print("=" * 60)


# ============================================================
# FASTAPI APPLICATION
# ============================================================


app = FastAPI(
    title="SiteAegis API",
    description=(
        "Real-time web security monitoring and "
        "construction site safety intelligence platform."
    ),

    # Use the single version defined in config.py.
    # This keeps OpenAPI and the application version
    # consistent.
    version=settings.APP_VERSION,

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
# API ROUTERS
# ============================================================


app.include_router(
    routes.router,
    prefix="/api",
)

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

app.include_router(
    cameras.router,
    prefix="/api",
)

app.include_router(
    zones.router,
    prefix="/api",
)

app.include_router(
    safety.router,
    prefix="/api",
)

app.include_router(
    incidents.router,
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
        "version": settings.APP_VERSION,
        "api": "/api",
        "websocket": "/ws",
        "modules": {
            "web_security_monitoring": True,
            "construction_safety": True,
            "ppe_detection": True,
            "cameras": True,
            "zones": True,
            "safety_events": True,
            "incidents": True,
        },
    }


# ============================================================
# WEBSOCKET
# ============================================================


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):

    await manager.connect(
        websocket
    )

    try:

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

        while True:

            message = await websocket.receive_text()

            print(
                f"[WEBSOCKET] Received: {message}"
            )

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

        manager.disconnect(
            websocket
        )

        print(
            "[WEBSOCKET] Client removed from manager."
        )