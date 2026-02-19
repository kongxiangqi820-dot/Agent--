from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

from agentfw.core.types import LLMResponse, ToolCall


class OpenAIChatCompletionsClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 600,
        timeout_s: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.timeout_s = int(timeout_s)

    def complete(self, messages: list[dict], tools=None) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = [t for t in tools]
            payload["tool_choice"] = "auto"

        req = urllib.request.Request(
            url=url,
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(f"OpenAI HTTPError {e.code}: {body or e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"OpenAI request failed: {e}") from e

        obj = json.loads(raw)
        choice = (obj.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = (msg.get("content") or "").strip()

        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            tc_id = tc.get("id") or str(uuid.uuid4())
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            args_s = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_s) if isinstance(args_s, str) else (args_s or {})
            except Exception:
                args = {}
            if name:
                tool_calls.append(ToolCall(id=tc_id, name=name, arguments=args))

        return LLMResponse(content=content, tool_calls=tool_calls)

