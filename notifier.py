#!/usr/bin/env python3
"""
Telegram notification helper.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment (or a
.env file next to this script) and exposes send_telegram_message() to push
a message to that chat. Uses only the standard library, so no extra
dependency (e.g. python-dotenv, requests) is required.
"""

import ssl
import os
import json
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _load_env_file(path: str) -> None:
    """Populate os.environ from a simple KEY=VALUE .env file, without overriding vars already set."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_env_file(ENV_FILE)

SERVER = os.environ.get("SERVER", "")
SERVICE = os.environ.get("SERVICE", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def _parse_chat_id(raw: str):
    """Split a TELEGRAM_CHAT_ID into (chat_id, message_thread_id).

    Supports the plain "-1001234567890" form as well as the
    "-1001234567890_13" form used to target a specific topic/thread inside
    a group (the part after the underscore is Telegram's message_thread_id).
    message_thread_id is None when no thread suffix is present.
    """
    chat_id, sep, thread_id = raw.partition("_")
    if sep and thread_id.lstrip("-").isdigit():
        return chat_id, int(thread_id)
    return raw, None


def is_configured() -> bool:
    """Whether both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_telegram_message(text: str, timeout: float = 5.0) -> bool:
    """Send *text* to the configured Telegram chat. Returns True on success.

    Never raises: network or config errors simply result in False, so a
    notification failure never interrupts the monitoring loop.
    """
    if not is_configured():
        return False

    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)
    chat_id, message_thread_id = _parse_chat_id(TELEGRAM_CHAT_ID)
    body = {"chat_id": chat_id, "text": f"[{SERVER}][{SERVICE}]\n{text}"}
    if message_thread_id is not None:
        body["message_thread_id"] = message_thread_id
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # 2. Create context to avoid SSL certificate verification
    context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            print(f"Success! Status code: {resp.status}")
            return resp.status == 200
    except Exception as e:
        # Print the error to the CMD screen to see what went wrong
        print(f"Script failed due to error: {type(e).__name__} - {e}")
        return False
