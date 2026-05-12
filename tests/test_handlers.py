import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers import handle_mention, _dedup
from bot import config as cfg


@pytest.fixture(autouse=True)
def clear_dedup():
    _dedup.clear()
    yield
    _dedup.clear()


@pytest.mark.asyncio
async def test_duplicate_event_is_dropped():
    cfg.ALLOWED_CHANNEL_IDS = "C1"
    cfg.ALLOWED_USER_IDS = ""
    event = {
        "client_msg_id": "msg-1",
        "ts": "1000.0",
        "channel": "C1",
        "user": "U1",
        "text": "<@UBOT> hello",
    }
    client = AsyncMock()
    with patch("bot.handlers._run_with_thinking") as mock_run:
        await handle_mention(event, client, None)
        await handle_mention(event, client, None)
    assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_rejected_channel():
    cfg.ALLOWED_CHANNEL_IDS = "C_ALLOWED"
    cfg.ALLOWED_USER_IDS = ""
    event = {
        "client_msg_id": "msg-2",
        "ts": "1001.0",
        "channel": "C_NOT_ALLOWED",
        "user": "U1",
        "text": "<@UBOT> hello",
    }
    client = AsyncMock()
    with patch("bot.handlers._run_with_thinking") as mock_run:
        await handle_mention(event, client, None)
    assert mock_run.call_count == 0
    client.chat_postMessage.assert_not_called()
