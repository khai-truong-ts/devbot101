import asyncio
import json
import logging
import time
from pathlib import Path

from cachetools import TTLCache

from bot import config

logger = logging.getLogger(__name__)

_TTL = 30 * 24 * 3600  # 30 days
_store: TTLCache = TTLCache(maxsize=10_000, ttl=_TTL)
_dirty = False


def get_session_id(thread_ts: str) -> str | None:
    return _store.get(thread_ts)


def set_session_id(thread_ts: str, session_id: str) -> None:
    global _dirty
    _store[thread_ts] = session_id
    _dirty = True


def load_from_disk() -> None:
    path = Path(config.SESSION_FILE_PATH)
    if not path.exists():
        return
    try:
        data: dict = json.loads(path.read_text())
        now = time.time()
        for thread_ts, entry in data.items():
            if isinstance(entry, dict):
                ts = entry.get("ts", 0)
                sid = entry.get("session_id", "")
            else:
                ts = now
                sid = str(entry)
            if sid and (now - ts) < _TTL:
                _store[thread_ts] = sid
        logger.info("Restored %d sessions from disk", len(_store))
    except Exception:
        logger.exception("Failed to load sessions from disk")


def flush_to_disk() -> None:
    global _dirty
    if not _dirty:
        return
    path = Path(config.SESSION_FILE_PATH)
    try:
        data = {k: {"session_id": v, "ts": time.time()} for k, v in _store.items()}
        path.write_text(json.dumps(data, indent=2))
        _dirty = False
    except Exception:
        logger.exception("Failed to flush sessions to disk")


async def flush_loop() -> None:
    while True:
        await asyncio.sleep(5)
        flush_to_disk()
