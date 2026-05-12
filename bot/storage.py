import logging

import asyncpg

from bot import config

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global _pool
    if not config.DATABASE_URL:
        return
    _pool = await asyncpg.create_pool(
        config.DATABASE_URL,
        min_size=1,
        max_size=5,
    )
    logger.info("asyncpg pool initialized")


async def close_pool() -> None:
    if _pool:
        await _pool.close()


async def write_audit_log(
    *,
    slack_user_id: str,
    slack_channel_id: str,
    slack_thread_ts: str,
    message: str,
    response: str,
    success: bool,
    duration_ms: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    if not _pool:
        return
    try:
        await _pool.execute(
            """
            INSERT INTO audit_log (
                slack_user_id, slack_channel_id, slack_thread_ts,
                message, response, success, duration_ms,
                input_tokens, output_tokens
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            slack_user_id, slack_channel_id, slack_thread_ts,
            message, response, success, duration_ms,
            input_tokens, output_tokens,
        )
    except Exception:
        logger.exception("Failed to write audit log")
