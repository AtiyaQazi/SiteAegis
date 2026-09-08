import asyncio
import logging
import threading

from fastapi import WebSocket


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage active SiteAegis WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

        self.loop: asyncio.AbstractEventLoop | None = None

        self._lock = threading.Lock()

    async def connect(
        self,
        websocket: WebSocket,
    ):
        """Accept and register a WebSocket connection."""

        await websocket.accept()

        current_loop = asyncio.get_running_loop()

        with self._lock:

            if websocket not in self.active_connections:
                self.active_connections.append(
                    websocket
                )

            self.loop = current_loop

        print(
            f"[WEBSOCKET] Client connected. "
            f"Active clients: {len(self.active_connections)}"
        )

    def disconnect(
        self,
        websocket: WebSocket,
    ):
        """Remove a WebSocket connection."""

        with self._lock:

            if websocket in self.active_connections:
                self.active_connections.remove(
                    websocket
                )

            if not self.active_connections:
                self.loop = None

        print(
            f"[WEBSOCKET] Client disconnected. "
            f"Active clients: {len(self.active_connections)}"
        )

    async def broadcast(
        self,
        message: dict,
    ):
        """Broadcast JSON message to all connected clients."""

        with self._lock:
            connections = list(
                self.active_connections
            )

        if not connections:
            print(
                "[WEBSOCKET] No active clients. "
                "Message not delivered."
            )
            return

        disconnected = []

        print(
            f"[WEBSOCKET] Broadcasting to "
            f"{len(connections)} client(s)."
        )

        for websocket in connections:

            try:

                await websocket.send_json(
                    message
                )

            except Exception as exc:

                logger.warning(
                    "WebSocket broadcast failed: %s",
                    exc,
                )

                disconnected.append(
                    websocket
                )

        for websocket in disconnected:
            self.disconnect(websocket)

    def broadcast_sync(
        self,
        message: dict,
    ):
        """
        Safely broadcast from synchronous/background
        scheduler code into the FastAPI event loop.
        """

        with self._lock:

            loop = self.loop
            has_connections = bool(
                self.active_connections
            )

        if not has_connections:
            print(
                "[WEBSOCKET] No connected dashboard clients."
            )
            return

        if loop is None:
            print(
                "[WEBSOCKET] Event loop unavailable."
            )
            return

        if loop.is_closed():
            print(
                "[WEBSOCKET] Event loop is closed."
            )
            return

        try:

            future = asyncio.run_coroutine_threadsafe(
                self.broadcast(message),
                loop,
            )

            def handle_result(done_future):
                try:
                    done_future.result()

                except Exception as exc:
                    logger.error(
                        "WebSocket broadcast error: %s",
                        exc,
                    )

            future.add_done_callback(
                handle_result
            )

            print(
                "[WEBSOCKET] Broadcast scheduled successfully."
            )

        except Exception as exc:

            logger.error(
                "Could not schedule WebSocket broadcast: %s",
                exc,
            )


manager = ConnectionManager()