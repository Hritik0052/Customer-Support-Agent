"""
HTTP transport for OpenRouter. This module knows nothing about tickets or
prompts — it sends messages and returns the assistant's raw text.
"""

import logging
import os
import random
import time

import httpx

from ai.exceptions import (
    ConfigurationError,
    RateLimitError,
    TimeoutError,
    UpstreamError,
)

logger = logging.getLogger(__name__)

# Retry on transient failures only. A 400/401/404 means the request itself is
# wrong, and sending it three more times will not fix it.
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def _config():
    """
    Read config from Django settings when available, otherwise from the
    environment. The env fallback is what lets this module be exercised from a
    plain script with no Django involved.
    """
    try:
        from django.conf import settings

        if settings.configured:
            return {
                "api_key": settings.OPENROUTER_API_KEY,
                "base_url": settings.OPENROUTER_BASE_URL,
                "timeout": settings.OPENROUTER_TIMEOUT,
                "max_retries": settings.OPENROUTER_MAX_RETRIES,
                "site_url": settings.SITE_URL,
                "site_name": settings.SITE_NAME,
            }
    except (ImportError, Exception):  # noqa: B014 - ImproperlyConfigured included
        pass

    return {
        "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
        "base_url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "timeout": int(os.environ.get("OPENROUTER_TIMEOUT", 30)),
        "max_retries": int(os.environ.get("OPENROUTER_MAX_RETRIES", 3)),
        "site_url": os.environ.get("SITE_URL", "http://127.0.0.1:8000"),
        "site_name": os.environ.get("SITE_NAME", "SupportIQ"),
    }


def chat_completion(messages, model, temperature=0.2, max_tokens=900):
    """
    Send a chat completion request and return the assistant's message content.

    Raises ConfigurationError, RateLimitError, TimeoutError or UpstreamError.
    """
    cfg = _config()

    if not cfg["api_key"]:
        raise ConfigurationError("OPENROUTER_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
        # OpenRouter uses these for attribution on their model leaderboard.
        "HTTP-Referer": cfg["site_url"],
        "X-Title": cfg["site_name"],
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Nudges compliant models toward valid JSON. Free models often ignore
        # it, which is exactly why parser.py is defensive.
        "response_format": {"type": "json_object"},
    }

    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
    last_error = None

    for attempt in range(cfg["max_retries"]):
        try:
            with httpx.Client(timeout=cfg["timeout"]) as client:
                response = client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                return _extract_content(response.json())

            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                if attempt < cfg["max_retries"] - 1:
                    _sleep_backoff(attempt, response)
                    continue
                if response.status_code == 429:
                    raise RateLimitError(last_error)
                raise UpstreamError(last_error)

            raise UpstreamError(f"HTTP {response.status_code}: {response.text[:300]}")

        except httpx.TimeoutException as exc:
            last_error = f"Request timed out after {cfg['timeout']}s"
            if attempt < cfg["max_retries"] - 1:
                _sleep_backoff(attempt)
                continue
            raise TimeoutError(last_error) from exc

        except httpx.HTTPError as exc:
            last_error = f"Network error: {exc}"
            if attempt < cfg["max_retries"] - 1:
                _sleep_backoff(attempt)
                continue
            raise UpstreamError(last_error) from exc

    raise UpstreamError(last_error or "Request failed.")


def _extract_content(data):
    """Pull the assistant text out of an OpenRouter response envelope."""
    # OpenRouter can return 200 with an error body when a provider fails.
    if "error" in data and data["error"]:
        message = data["error"].get("message", str(data["error"]))
        if "rate" in message.lower() or data["error"].get("code") == 429:
            raise RateLimitError(message)
        raise UpstreamError(message)

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise UpstreamError(f"Unexpected response shape: {str(data)[:300]}") from exc

    if not content or not content.strip():
        raise UpstreamError("Model returned an empty response.")

    return content


def _sleep_backoff(attempt, response=None):
    """
    Exponential backoff with jitter, honouring Retry-After when the server
    sends one. Jitter keeps concurrent retries from lining up.
    """
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                time.sleep(min(float(retry_after), 20))
                return
            except ValueError:
                pass

    delay = (2 ** attempt) + random.uniform(0, 0.5)
    logger.warning("OpenRouter attempt %s failed; retrying in %.1fs", attempt + 1, delay)
    time.sleep(delay)
