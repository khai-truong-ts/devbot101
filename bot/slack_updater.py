import asyncio
import logging
import re
import time

from slack_sdk.web.async_client import AsyncWebClient

from bot import config

logger = logging.getLogger(__name__)


async def post_thinking(client: AsyncWebClient, channel: str, thread_ts: str) -> str:
    resp = await client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text="⏳ Thinking… (0s)",
    )
    return resp["ts"]


async def tick_timer(
    client: AsyncWebClient, channel: str, ts: str, start: float, stop_event: asyncio.Event
) -> None:
    while not stop_event.is_set():
        await asyncio.sleep(5)
        if stop_event.is_set():
            break
        elapsed = int(time.monotonic() - start)
        try:
            await client.chat_update(
                channel=channel,
                ts=ts,
                text=f"⏳ Thinking… ({elapsed}s)",
            )
        except Exception:
            logger.debug("Timer update failed (message may have been deleted)")


async def post_result(
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
    thinking_ts: str,
    user_id: str,
    text: str,
) -> None:
    try:
        await client.chat_delete(channel=channel, ts=thinking_ts)
    except Exception:
        logger.debug("Failed to delete thinking message")

    slack_text = markdown_to_slack(text)
    slack_text = slack_text[: config.SLACK_MAX_CHARS]
    if len(text) > config.SLACK_MAX_CHARS:
        slack_text += f"\n_(truncated — {len(text)} chars total)_"

    await client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=f"<@{user_id}>\n{slack_text}",
    )


def markdown_to_slack(text: str) -> str:
    code_blocks: list[str] = []

    def save_block(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"\x00CODE{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\s\S]*?```", save_block, text)
    text = re.sub(r"`[^`]+`", save_block, text)

    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"_\1_", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"_\1_", text)
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^[\-\*]\s+", "• ", text, flags=re.MULTILINE)

    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODE{i}\x00", block)

    return text
