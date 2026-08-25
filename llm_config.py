"""Configure OpenAI Agents SDK: direct OpenAI or LiteLLM proxy."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(override=True)

_DEFAULT_LITELLM_BASE_URL = "http://localhost:4000"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def configure_llm() -> None:
    """Route Agents SDK through LiteLLM when USE_LITELLM is true."""
    if not _truthy(os.getenv("USE_LITELLM")):
        return

    from agents import (
        set_default_openai_api,
        set_default_openai_client,
        set_tracing_disabled,
    )
    from openai import AsyncOpenAI

    base_url = (os.getenv("LITELLM_BASE_URL") or _DEFAULT_LITELLM_BASE_URL).rstrip(
        "/"
    )
    api_key = os.getenv("litellm") or os.getenv("LITELLM_API_KEY")
    if not api_key:
        raise ValueError(
            "USE_LITELLM is True but litellm (API key) is not set in .env"
        )

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    set_default_openai_client(client)
    set_default_openai_api("chat_completions")
    set_tracing_disabled(True)


configure_llm()
