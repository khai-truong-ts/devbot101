import asyncio
import json
import logging
import os
import signal
from dataclasses import dataclass, field

from bot import config

logger = logging.getLogger(__name__)

SANDBOX_DIR = "/workspace/sandbox"


@dataclass
class RunResult:
    text: str
    session_id: str | None
    success: bool
    input_tokens: int = 0
    output_tokens: int = 0


async def run_claude(prompt: str, session_id: str | None = None) -> RunResult:
    args = [
        "claude",
        "--dangerously-skip-permissions",
        "--verbose",
        "--output-format", "stream-json",
    ]
    if session_id:
        args += ["--resume", session_id]
    args += ["-p", prompt]

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY,
    }

    logger.info("Spawning Claude (session=%s)", session_id)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=SANDBOX_DIR,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
            limit=10 * 1024 * 1024,
        )
    except FileNotFoundError:
        return RunResult(
            text="❌ `claude` CLI not found. Is `@anthropic-ai/claude-code` installed?",
            session_id=None,
            success=False,
        )

    result_event: dict | None = None

    async def _read_stdout():
        nonlocal result_event
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Non-JSON stdout: %s", line[:200])
                continue
            if event.get("type") == "result":
                result_event = event

    try:
        await asyncio.wait_for(_read_stdout(), timeout=config.CLAUDE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Claude timed out after %ds — killing", config.CLAUDE_TIMEOUT_SECONDS)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        return RunResult(
            text=f"❌ Claude timed out after {config.CLAUDE_TIMEOUT_SECONDS}s.",
            session_id=None,
            success=False,
        )
    finally:
        try:
            stderr_bytes = await asyncio.wait_for(proc.stderr.read(), timeout=30)
            stderr_text = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
            if stderr_text:
                logger.debug("Claude stderr: %s", stderr_text[:500])
        except (asyncio.TimeoutError, Exception):
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except (asyncio.TimeoutError, Exception):
            pass

    if result_event is None:
        return RunResult(text="❌ Claude returned no result.", session_id=None, success=False)

    if result_event.get("subtype") != "success":
        error = result_event.get("error", "unknown error")
        return RunResult(
            text=f"❌ Claude error: {error}",
            session_id=result_event.get("session_id"),
            success=False,
        )

    usage = result_event.get("usage", {})
    return RunResult(
        text=result_event.get("result", ""),
        session_id=result_event.get("session_id"),
        success=True,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )
