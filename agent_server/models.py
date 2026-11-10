"""OpenAI-compatible model providers with bounded responses and retries."""
import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def validate_base_url(value):
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid provider URL")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
        raise ValueError("provider URL requires HTTPS or local HTTP")
    if not parsed.hostname:
        raise ValueError("provider host required")
    return value.rstrip("/")


class ModelClient:
    def __init__(self, memory):
        self.memory = memory

    def config(self):
        values = self.memory.settings()
        return {"base_url": values.get("model_base_url") or os.getenv("LOVEPILOT_MODEL_URL", "https://api.deepseek.com"),
                "model": values.get("model_name") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "api_key": values["model_api_key"] if "model_api_key" in values else os.getenv("DEEPSEEK_API_KEY", "")}

    def complete(self, system, history):
        config = self.config()
        if not config["api_key"]:
            raise RuntimeError("model credentials required")
        base = validate_base_url(config["base_url"])
        payload = json.dumps({"model": config["model"], "messages": [{"role": "system", "content": system}] + history,
                              "max_tokens": 1200, "response_format": {"type": "json_object"}}).encode()
        request = urllib.request.Request(base + "/chat/completions", data=payload,
            headers={"Authorization": "Bearer " + config["api_key"], "Content-Type": "application/json"})
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ValueError("model response too large")
                data = json.loads(raw)
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                if attempt or exc.code not in (429, 502, 503, 504):
                    raise
            except (TimeoutError, urllib.error.URLError):
                if attempt:
                    raise
            time.sleep(0.5)
