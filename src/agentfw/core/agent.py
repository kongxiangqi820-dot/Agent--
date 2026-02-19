from __future__ import annotations

import json

from agentfw.core.types import Message


class Agent:
    def __init__(
        self,
        llm,
        tools,
        memory,
        system_prompt: str,
        max_tool_steps: int = 6,
        history_messages: int = 20,
    ):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.system_prompt = system_prompt or ""
        self.max_tool_steps = max(0, int(max_tool_steps))
        self.history_messages = max(0, int(history_messages))

    def _build_messages(self, user_text: str) -> list[dict]:
        msgs: list[dict] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})

        for m in self.memory.load_last_messages(self.history_messages):
            d = {"role": m.role, "content": m.content}
            if m.tool_call_id:
                d["tool_call_id"] = m.tool_call_id
            msgs.append(d)

        msgs.append({"role": "user", "content": user_text})
        return msgs

    def chat(self, user_text: str) -> str:
        messages = self._build_messages(user_text)
        tool_specs = self.tools.openai_tool_specs()

        # record user
        self.memory.append(Message(role="user", content=user_text))

        steps = 0
        while True:
            resp = self.llm.complete(messages=messages, tools=tool_specs)

            if resp.tool_calls and steps < self.max_tool_steps:
                steps += 1
                # Assistant message with tool calls (OpenAI-compatible format)
                messages.append(
                    {
                        "role": "assistant",
                        "content": resp.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)},
                            }
                            for tc in resp.tool_calls
                        ],
                    }
                )

                for tc in resp.tool_calls:
                    out = self.tools.call(tc.name, tc.arguments)
                    # Tool message
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})
                    self.memory.append(Message(role="tool", name=tc.name, tool_call_id=tc.id, content=str(out)))

                continue

            # No tool calls (or exceeded steps)
            final = (resp.content or "").strip()
            if not final:
                final = "(空响应)"

            self.memory.append(Message(role="assistant", content=final))
            return final
