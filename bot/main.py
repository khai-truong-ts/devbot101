import asyncio
import logging
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from bot import config
from bot import session_store
from bot import storage
from bot.handlers import register_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass


def _start_health_server() -> None:
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), _HealthHandler).serve_forever()


async def main() -> None:
    config.validate()
    session_store.load_from_disk()

    if config.AUDIT_LOG_ENABLED:
        await storage.init_pool()

    app = AsyncApp(token=config.SLACK_BOT_TOKEN)
    register_handlers(app)

    flush_task = asyncio.create_task(session_store.flush_loop())

    loop = asyncio.get_running_loop()

    def _on_signal():
        logger.info("Shutdown signal received")
        flush_task.cancel()
        session_store.flush_to_disk()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _on_signal)

    handler = AsyncSocketModeHandler(app, config.SLACK_APP_TOKEN)
    logger.info("Starting bot in Socket Mode…")
    await handler.start_async()

    session_store.flush_to_disk()
    await storage.close_pool()


if __name__ == "__main__":
    threading.Thread(target=_start_health_server, daemon=True).start()
    asyncio.run(main())
