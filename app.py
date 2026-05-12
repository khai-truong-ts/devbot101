import os
import subprocess
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])

CONVERSATION_HISTORY: dict[str, list] = {}


def ask_claude(channel_id: str, user_message: str) -> str:
    history = CONVERSATION_HISTORY.setdefault(channel_id, [])
    history.append({"role": "user", "content": user_message})

    # Keep last 20 messages
    if len(history) > 20:
        history[:] = history[-20:]

    # Build conversation context as a single prompt for the CLI
    parts = []
    for msg in history[:-1]:  # everything except the latest user message
        label = "Human" if msg["role"] == "user" else "Assistant"
        parts.append(f"{label}: {msg['content']}")
    parts.append(f"Human: {user_message}")
    prompt = "\n\n".join(parts)

    env = {
        **os.environ,
        "ANTHROPIC_API_KEY": os.environ["CLAUDE_API_KEY"],
    }

    result = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude CLI returned non-zero exit")

    reply = result.stdout.strip()
    history.append({"role": "assistant", "content": reply})
    return reply


@app.event("app_mention")
def handle_mention(event, say, client):
    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])
    bot_user_id = client.auth_test()["user_id"]

    raw_text = event.get("text", "")
    user_message = raw_text.replace(f"<@{bot_user_id}>", "").strip()

    if not user_message:
        say(text="How can I help you?", thread_ts=thread_ts)
        return

    say(text="_Thinking..._", thread_ts=thread_ts)

    try:
        reply = ask_claude(channel, user_message)
        say(text=reply, thread_ts=thread_ts)
    except Exception as e:
        logger.exception("Claude CLI error")
        say(text=f"Sorry, something went wrong: {e}", thread_ts=thread_ts)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info("Health server listening on port %d", port)
    server.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Slack bot starting in Socket Mode")
    handler.start()
