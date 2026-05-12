import os
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN: str = os.environ.get("SLACK_APP_TOKEN", "")

ALLOWED_CHANNEL_IDS: str = os.environ.get("ALLOWED_CHANNEL_IDS", "")
ALLOWED_USER_IDS: str = os.environ.get("ALLOWED_USER_IDS", "")
MAX_CONCURRENT_SESSIONS: int = int(os.environ.get("MAX_CONCURRENT_SESSIONS", "10"))

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
AUDIT_LOG_ENABLED: bool = os.environ.get("AUDIT_LOG_ENABLED", "false").lower() == "true"

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_TIMEOUT_SECONDS: int = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "600"))
SLACK_MAX_CHARS: int = int(os.environ.get("SLACK_MAX_CHARS", "3800"))

DIRECT_REPLY_ENABLED: bool = os.environ.get("DIRECT_REPLY_ENABLED", "false").lower() == "true"
SESSION_FILE_PATH: str = os.environ.get("SESSION_FILE_PATH", "/workspace/sessions.json")


def validate():
    required = {
        "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
        "SLACK_APP_TOKEN": SLACK_APP_TOKEN,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    import logging
    _log = logging.getLogger(__name__)

    if not ANTHROPIC_API_KEY and not os.path.exists(os.path.join(os.environ.get("HOME", ""), ".claude", ".credentials.json")):
        _log.warning("Neither ANTHROPIC_API_KEY nor OAuth credentials found — Claude calls will fail")

    if not ALLOWED_CHANNEL_IDS:
        _log.warning("ALLOWED_CHANNEL_IDS is not set — all channel requests will be rejected")
