from __future__ import annotations

from typing import Any

from agentfw.tools.base import Tool


class EchoTool(Tool):
    name = "echo"
    description = "Return the input text as-is."
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo back."}
        },
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args: dict[str, Any]) -> str:
        return str(args.get("text", ""))
