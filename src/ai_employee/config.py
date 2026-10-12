"""Minimal hosted model configuration; local secrets never enter graph state."""

import os
from pathlib import Path

from dotenv import dotenv_values
from langchain_groq import ChatGroq
from pydantic import SecretStr

MODEL = "openai/gpt-oss-120b"
MODEL_TIMEOUT_SECONDS = 30


class ConfigurationError(Exception):
    pass


def disable_external_tracing():
    for name in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        os.environ[name] = "false"


def load_model(env_path: Path | None = None):
    disable_external_tracing()
    try:
        key = (dotenv_values(env_path or Path.cwd() / ".env", interpolate=False).get("GROQ_API_KEY") or "").strip()
    except (OSError, UnicodeError):
        raise ConfigurationError("Cannot read local .env; check permissions and UTF-8 encoding.") from None
    if not key or key.lower() in {"your_groq_api_key_here", "...", "replace_me"}:
        raise ConfigurationError("Set GROQ_API_KEY in local .env to a valid key from the Groq console. Do not paste it into chat.")
    return ChatGroq(model=MODEL, api_key=SecretStr(key), temperature=0,
                    timeout=MODEL_TIMEOUT_SECONDS, max_retries=0, max_tokens=1200, reasoning_effort="low",
                    model_kwargs={"include_reasoning": False})
