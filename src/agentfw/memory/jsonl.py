from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from agentfw.core.types import Message


class JsonlMemoryStore:
    def __init__(self, directory: str = ".agent", filename: str = "memory.jsonl"):
        self.dir = Path(directory)
        self.path = self.dir / filename
        self.dir.mkdir(parents=True, exist_ok=True)

    def append(self, msg: Message) -> None:
        rec = asdict(msg)
        rec["ts"] = time.time()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def load_last_messages(self, n: int) -> list[Message]:
        n = max(0, int(n))
        if n == 0:
            return []
        if not self.path.exists():
            return []

        # Simple approach: read all, slice last N.
        # If memory grows large, replace with a tail-reader.
        rows = self.path.read_text(encoding="utf-8").splitlines()
        out: list[Message] = []
        for line in rows[-n:]:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            out.append(
                Message(
                    role=obj.get("role"),
                    content=obj.get("content") or "",
                    name=obj.get("name"),
                    tool_call_id=obj.get("tool_call_id"),
                )
            )
        return out

