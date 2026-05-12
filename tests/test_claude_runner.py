import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.claude_runner import run_claude


@pytest.mark.asyncio
async def test_run_claude_success(mocker):
    lines = [
        json.dumps({"type": "assistant", "message": {"content": []}}).encode() + b"\n",
        json.dumps({
            "type": "result",
            "subtype": "success",
            "result": "hello world",
            "session_id": "sess-abc",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }).encode() + b"\n",
        b"",
    ]
    proc = AsyncMock()
    proc.stdout.readline = AsyncMock(side_effect=lines)
    proc.stderr.read = AsyncMock(return_value=b"")
    proc.wait = AsyncMock(return_value=0)
    proc.pid = 1234

    mocker.patch("asyncio.create_subprocess_exec", return_value=proc)

    result = await run_claude("say hi")
    assert result.success is True
    assert result.text == "hello world"
    assert result.session_id == "sess-abc"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


@pytest.mark.asyncio
async def test_run_claude_not_found(mocker):
    mocker.patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError)
    result = await run_claude("say hi")
    assert result.success is False
    assert "not found" in result.text


@pytest.mark.asyncio
async def test_run_claude_error_subtype(mocker):
    lines = [
        json.dumps({
            "type": "result",
            "subtype": "error",
            "error": "rate limit exceeded",
            "session_id": None,
        }).encode() + b"\n",
        b"",
    ]
    proc = AsyncMock()
    proc.stdout.readline = AsyncMock(side_effect=lines)
    proc.stderr.read = AsyncMock(return_value=b"")
    proc.wait = AsyncMock(return_value=1)
    proc.pid = 1234

    mocker.patch("asyncio.create_subprocess_exec", return_value=proc)

    result = await run_claude("say hi")
    assert result.success is False
    assert "rate limit" in result.text
