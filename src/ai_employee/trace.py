"""Public JSON events only; never serialize model message objects or exceptions."""

from datetime import datetime, timezone
import json
import re

SECRET_FIELDS = {"api_key", "groq_api_key", "authorization", "password", "token", "secret", "reasoning", "reasoning_content"}


def sanitize(value):
    if isinstance(value, dict):
        return {str(key): ("[redacted]" if str(key).lower() in SECRET_FIELDS else sanitize(item))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        if "<think" in value.lower():
            return "[private reasoning omitted]"
        return re.sub(r"\b(?:gsk_|sk-)[A-Za-z0-9_-]+", "[redacted]", value)[:4000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "[unsupported value]"


def event(kind: str, **details) -> dict:
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "event": kind, **sanitize(details)}


def print_event(value: dict):
    print(json.dumps(value, ensure_ascii=True), flush=True)
