from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenAIToolSpec:
    type: str
    function: dict[str, Any]


class Tool:
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": True}

    def spec(self) -> OpenAIToolSpec:
        return OpenAIToolSpec(
            type="function",
            function={
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        )

    def run(self, args: dict[str, Any]) -> str:
        raise NotImplementedError

