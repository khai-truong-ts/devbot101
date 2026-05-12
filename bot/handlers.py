import asyncio
import logging
import re
import time

from cachetools import TTLCache
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from bot import config
from bot import guardrail
from bot import session_store
from bot import storage
from bot.claude_runner import run_claude
from bot.slack_updater import post_result, post_thinking, tick_timer

logger = logging.getLogger(__name__)

_dedup: TTLCache = TTLCache(maxsize=1000, ttl=60)
_semaphore: asyncio.BoundedSemaphore | None = None
_MAX_RETRIES = 3


def _get_semaphore() -> asyncio.BoundedSemaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.BoundedSemaphore(config.MAX_CONCURRENT_SESSIONS)
    return _semaphore


def register_handlers(app: AsyncApp) -> None:
    global _semaphore
    _semaphore = asyncio.BoundedSemaphore(config.MAX_CONCURRENT_SESSIONS)
    app.event("app_mention")(handle_mention)
    if config.DIRECT_REPLY_ENABLED:
        app.event("message")(handle_dm)


async def handle_mention(event: dict, client: AsyncWebClient, say) -> None:
    await _dispatch(event, client)


async def handle_dm(event: dict, client: AsyncWebClient, say) -> None:
    if event.get("channel_type") != "im":
        return
    user_id = event.get("user", "")
    if not guardrail.is_allowed_user(user_id):
        return
    await _dispatch(event, client)


async def _dispatch(event: dict, client: AsyncWebClient) -> None:
    msg_id = event.get("client_msg_id") or event.get("ts")
    if msg_id in _dedup:
        logger.debug("Dropping duplicate event %s", msg_id)
        return
    _dedup[msg_id] = True

    channel = event["channel"]
    user_id = event.get("user", "")
    ts = event["ts"]
    thread_ts = event.get("thread_ts") or ts

    if not guardrail.is_allowed_channel(channel, user_id):
        logger.info("Rejected event from channel %s user %s", channel, user_id)
        return

    sem = _get_semaphore()
    if sem._value == 0:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"⚠️ <@{user_id}> High load right now — please try again in a moment.",
        )
        return

    await sem.acquire()
    try:
        await _run_with_thinking(event, client, channel, thread_ts, user_id, ts)
    finally:
        sem.release()


async def _run_with_thinking(
    event: dict,
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
    user_id: str,
    ts: str,
) -> None:
    start = time.monotonic()

    raw_text = _strip_bot_mention(event.get("text", ""))
    prompt = await _build_prompt(event, raw_text, user_id, channel, thread_ts, client)
    sanitized = guardrail.sanitize_prompt(prompt)

    thinking_ts = await post_thinking(client, channel, thread_ts)
    stop_timer = asyncio.Event()
    timer_task = asyncio.create_task(
        tick_timer(client, channel, thinking_ts, start, stop_timer)
    )

    result = None
    session_id = session_store.get_session_id(thread_ts)
    last_error = ""
    for attempt in range(_MAX_RETRIES):
        result = await run_claude(sanitized, session_id=session_id)
        if result.success:
            break
        last_error = result.text
        if "no conversation found" in (result.text + last_error).lower():
            session_id = None
        logger.warning("Claude attempt %d failed: %s", attempt + 1, last_error[:100])
        if attempt < _MAX_RETRIES - 1:
            await asyncio.sleep(2)

    stop_timer.set()
    await timer_task

    if result and result.success:
        if result.session_id:
            session_store.set_session_id(thread_ts, result.session_id)
        await post_result(client, channel, thread_ts, thinking_ts, user_id, result.text)
    else:
        await post_result(
            client, channel, thread_ts, thinking_ts, user_id,
            last_error or "❌ Something went wrong. Please try again.",
        )

    if config.AUDIT_LOG_ENABLED and result:
        duration_ms = int((time.monotonic() - start) * 1000)
        await storage.write_audit_log(
            slack_user_id=user_id,
            slack_channel_id=channel,
            slack_thread_ts=thread_ts,
            message=raw_text,
            response=result.text if result else "",
            success=result.success if result else False,
            duration_ms=duration_ms,
            input_tokens=result.input_tokens if result else 0,
            output_tokens=result.output_tokens if result else 0,
        )


def _strip_bot_mention(text: str) -> str:
    return re.sub(r"^<@[A-Z0-9]+>\s*", "", text).strip()


async def _build_prompt(
    event: dict, raw_text: str, user_id: str, channel: str, thread_ts: str, client: AsyncWebClient
) -> str:
    if session_store.get_session_id(thread_ts):
        return raw_text

    thread_context = await _fetch_thread_context(client, channel, thread_ts)

    parts = [
        f"[Slack context] User: <@{user_id}>, Channel: {channel}, Thread: {thread_ts}",
    ]
    if thread_context:
        parts.append(f"[Thread history]\n{thread_context}")
    parts.append(f"[Current message]\n{raw_text}")

    return "\n\n".join(parts)


async def _fetch_thread_context(
    client: AsyncWebClient, channel: str, thread_ts: str, max_chars: int = 8000
) -> str:
    try:
        resp = await client.conversations_replies(channel=channel, ts=thread_ts, limit=50)
    except Exception:
        return ""
    messages = resp.get("messages", [])
    lines = []
    for msg in messages[:-1]:
        user = msg.get("user", "bot")
        text = msg.get("text", "").strip()
        if text:
            lines.append(f"<@{user}>: {text}")
    context = "\n".join(lines)
    return context[-max_chars:]
