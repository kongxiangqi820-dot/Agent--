from __future__ import annotations

import re

from agentfw.core.types import LLMResponse


class MockLLMClient:
    """
    Offline mock:
    - Never calls tools automatically.
    - Provides predictable, short answers for smoke testing.
    """

    def complete(self, messages: list[dict], tools=None) -> LLMResponse:
        user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user = (m.get("content") or "").strip()
                break

        if not user:
            return LLMResponse(content="请提供你的问题。", tool_calls=[])

        if re.search(r"你是谁|介绍一下|help|帮助", user, re.I):
            return LLMResponse(
                content="我是一个可扩展的智能体框架示例。你可以用 /tools 查看工具，用 !tool 直接调用工具。",
                tool_calls=[],
            )

        return LLMResponse(content=f"(mock) 我收到了：{user}", tool_calls=[])
