from __future__ import annotations

from pathlib import Path
from typing import Any

from agentfw.tools.base import Tool


def _resolve_under_root(root: str, p: str) -> Path:
    root_p = Path(root).resolve()
    target = (root_p / p).resolve()
    if root_p != target and root_p not in target.parents:
        raise PermissionError("path escapes fs_root")
    return target


class FsListTool(Tool):
    name = "fs_list"
    description = "List files/sub-directories under a directory."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to fs_root. Default '.'"},
            "limit": {"type": "integer", "description": "Max items to return. Default 200"},
        },
        "additionalProperties": False,
    }

    def __init__(self, root: str = "."):
        self.root = root

    def run(self, args: dict[str, Any]) -> str:
        rel = (args.get("path") or ".").strip()
        limit = int(args.get("limit") or 200)
        if limit <= 0:
            limit = 200

        p = _resolve_under_root(self.root, rel)
        if not p.exists():
            raise FileNotFoundError(str(p))
        if not p.is_dir():
            raise NotADirectoryError(str(p))

        items = []
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            t = "dir" if child.is_dir() else "file"
            items.append(f"{t}\t{child.name}")
            if len(items) >= limit:
                break
        return "\n".join(items)


class FsReadTool(Tool):
    name = "fs_read"
    description = "Read a text file under fs_root."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to fs_root"},
            "max_chars": {"type": "integer", "description": "Max chars to read. Default 8000"},
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, root: str = "."):
        self.root = root

    def run(self, args: dict[str, Any]) -> str:
        rel = (args.get("path") or "").strip()
        if not rel:
            raise ValueError("path is required")
        max_chars = int(args.get("max_chars") or 8000)
        if max_chars <= 0:
            max_chars = 8000

        p = _resolve_under_root(self.root, rel)
        if not p.exists():
            raise FileNotFoundError(str(p))
        if p.is_dir():
            raise IsADirectoryError(str(p))

        try:
            s = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            s = p.read_text(errors="replace")

        if len(s) > max_chars:
            s = s[:max_chars] + "\n...[truncated]..."

        return s
