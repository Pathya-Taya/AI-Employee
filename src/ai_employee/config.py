"""Minimal hosted model configuration; local secrets never enter graph state."""

import os
from pathlib import Path
from urllib.parse import urlparse

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


def local_environment(env_path: Path | None = None):
    try:
        return dotenv_values(env_path or Path.cwd() / ".env", interpolate=False)
    except (OSError, UnicodeError):
        raise ConfigurationError("Cannot read local .env; check permissions and UTF-8 encoding.") from None


def model_info(env_path: Path | None = None, *, provider=None, model=None):
    """Public configuration only; credentials never enter this mapping."""
    values = local_environment(env_path)
    selected = (provider or values.get("AI_EMPLOYEE_PROVIDER") or "groq").strip().lower()
    if selected == "groq":
        return {"provider": "groq", "model": MODEL}
    if selected != "omniroute":
        raise ConfigurationError("AI_EMPLOYEE_PROVIDER must be groq or omniroute in local .env.")
    base_url = (values.get("OMNIROUTE_BASE_URL") or "http://127.0.0.1:20128/v1").strip().rstrip("/")
    try:
        url = urlparse(base_url)
        url.port  # Validate malformed port syntax before constructing the SDK.
    except ValueError:
        raise ConfigurationError("Set OMNIROUTE_BASE_URL to a valid localhost HTTP /v1 URL.") from None
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.query or url.fragment or url.path != "/v1"):
        raise ConfigurationError("Set OMNIROUTE_BASE_URL to a local HTTP /v1 endpoint, for example http://127.0.0.1:20128/v1.")
    selected_model = (model or values.get("OMNIROUTE_MODEL") or "").strip()
    if (not selected_model or len(selected_model) > 200 or selected_model.lower().startswith("auto")
            or selected_model.lower() in {"your_verified_model_id", "..."}):
        raise ConfigurationError("Set OMNIROUTE_MODEL to an explicit connected model ID that passes both native-tool preflights; auto is not enabled.")
    return {"provider": selected, "model": selected_model, "base_url": base_url}


def load_model(env_path: Path | None = None, *, provider=None, model=None):
    disable_external_tracing()
    info = model_info(env_path, provider=provider, model=model)
    values = local_environment(env_path)
    if info["provider"] == "omniroute":
        key = (values.get("OMNIROUTE_API_KEY") or "").strip()
        if not key or key.lower() in {"your_local_endpoint_key", "...", "replace_me"}:
            raise ConfigurationError("Set OMNIROUTE_API_KEY in local .env to your local endpoint key. Do not paste it into chat.")
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=info["model"], base_url=info["base_url"], api_key=SecretStr(key),
                              temperature=0, timeout=MODEL_TIMEOUT_SECONDS, max_retries=0,
                              max_tokens=1200, use_responses_api=False, stream_usage=False,
                              metadata=info)
        except ImportError:
            raise ConfigurationError("Optional SDK could not load. Install the pinned adapter: python -m pip install -e '.[omniroute]'; check local application-control restrictions if imports remain blocked.") from None
    key = (values.get("GROQ_API_KEY") or "").strip()
    if not key or key.lower() in {"your_groq_api_key_here", "...", "replace_me"}:
        raise ConfigurationError("Set GROQ_API_KEY in local .env to a valid key from the Groq console. Do not paste it into chat.")
    return ChatGroq(model=MODEL, api_key=SecretStr(key), temperature=0,
                    timeout=MODEL_TIMEOUT_SECONDS, max_retries=0, max_tokens=1200, reasoning_effort="low",
                    model_kwargs={"include_reasoning": False}, metadata=info)
