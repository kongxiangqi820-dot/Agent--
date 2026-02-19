from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentfw.tools.base import Tool


class TimeNowTool(Tool):
    name = "time_now"
    description = "Return current UTC time in ISO8601 format."
    input_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def run(self, args: dict[str, Any]) -> str:
        return datetime.now(timezone.utc).isoformat()
