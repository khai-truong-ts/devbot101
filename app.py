import os
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import anthropic

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])
claude = anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])

CONVERSATION_HISTORY: dict[str, list] = {}


def ask_claude(channel_id: str, user_message: str) -> str:
    history = CONVERSATION_HISTORY.setdefault(channel_id, [])
    history.append({"role": "user", "content": user_message})

    # Keep last 20 messages to avoid token bloat
    if len(history) > 20:
        history[:] = history[-20:]

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system="You are a helpful assistant in a Slack workspace. Be concise and clear.",
        messages=history,
    )

    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})
    return reply


@app.event("app_mention")
def handle_mention(event, say, client):
    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])
    bot_user_id = client.auth_test()["user_id"]

    # Strip the bot mention from the message
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
        logger.exception("Claude API error")
        say(text=f"Sorry, something went wrong: {e}", thread_ts=thread_ts)


# Lightweight health-check server so Render keeps the service alive
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass  # silence access logs


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
