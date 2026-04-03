"""OpenRouter API client using stdlib only."""
import json
import os
import subprocess
import urllib.request
from pathlib import Path


def _get_api_key() -> str:
    """Get OpenRouter API key from env or macOS keychain."""
    # Try env var first
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key

    # Fall back to macOS keychain
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "OPENROUTER_API_KEY", "-w"],
            capture_output=True,
            text=True,
            check=True,
        )
        key = result.stdout.strip()
        if key:
            return key
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    raise RuntimeError(
        "OPENROUTER_API_KEY not found in env or macOS keychain. "
        "Set via: export OPENROUTER_API_KEY=... or "
        "security add-generic-password -s OPENROUTER_API_KEY -a $(whoami) -w <key>"
    )


def chat_completion_stream(
    prompt: str,
    *,
    model: str | None = None,
    timeout: int = 600,
):
    """
    Stream a prompt to OpenRouter, yielding text tokens as they arrive.

    Uses OpenRouter's SSE streaming (`stream: true`). Each yielded value is a
    plain string token. Raises RuntimeError on API or parse errors.
    """
    if model is None:
        model = os.environ.get(
            "OPENROUTER_MODEL_NEWSLETTER",
            "stepfun/step-3.5-flash:free"
        )

    api_key = _get_api_key()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    referer  = os.environ.get("OPENROUTER_HTTP_REFERER", "http://localhost:8787")
    app_title = os.environ.get("OPENROUTER_APP_TITLE", "newsletters")

    request_body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    headers = {
        "Authorization":  f"Bearer {api_key}",
        "Content-Type":   "application/json",
        "HTTP-Referer":   referer,
        "X-Title":        app_title,
        "Accept":         "text/event-stream",
    }

    url = f"{base_url}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").rstrip("\n\r")
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0]["delta"]
                    token = delta.get("content") or ""
                    if token:
                        yield token
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"OpenRouter {e.code}: {error_body[:300]}") from e
    except Exception as e:
        raise RuntimeError(f"OpenRouter stream failed: {e}") from e


def chat_completion(
    prompt: str,
    *,
    model: str | None = None,
    timeout: int = 600
) -> str:
    """
    Send a prompt to OpenRouter and return the assistant's text response.

    Args:
        prompt: The user prompt
        model: Model to use. Defaults to OPENROUTER_MODEL_NEWSLETTER env var,
               then stepfun/step-3.5-flash:free
        timeout: Request timeout in seconds

    Returns:
        The assistant's text response

    Raises:
        RuntimeError: On API errors or invalid responses
    """
    if model is None:
        model = os.environ.get(
            "OPENROUTER_MODEL_NEWSLETTER",
            "stepfun/step-3.5-flash:free"
        )

    api_key = _get_api_key()
    base_url = os.environ.get(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1"
    )
    referer = os.environ.get(
        "OPENROUTER_HTTP_REFERER",
        "http://localhost:8787"
    )
    app_title = os.environ.get("OPENROUTER_APP_TITLE", "newsletters")

    request_body = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": referer,
        "X-Title": app_title,
    }

    url = f"{base_url}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(
            f"OpenRouter {e.code}: {error_body[:300]}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"OpenRouter request failed: {e}") from e

    # Extract assistant text
    try:
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Handle content blocks (rare)
            return "".join(
                block.get("text", "")
                for block in content
                if block.get("type") == "text"
            )
        else:
            raise RuntimeError(f"Unexpected content type: {type(content)}")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Invalid OpenRouter response: {e}") from e
