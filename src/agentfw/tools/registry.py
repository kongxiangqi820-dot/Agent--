from __future__ import annotations

from typing import Any

from agentfw.tools.base import Tool
from agentfw.tools.tools_echo import EchoTool
from agentfw.tools.tools_fs import FsListTool, FsReadTool
from agentfw.tools.tools_time import TimeNowTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._enabled: set[str] | None = None  # None means all enabled

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool.name is empty")
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def enable_only(self, names: set[str]) -> None:
        self._enabled = set(names)

    def list_enabled(self) -> list[str]:
        names = list(self._tools.keys())
        names.sort()
        if self._enabled is None:
            return names
        return [n for n in names if n in self._enabled]

    def enabled_tools(self) -> list[Tool]:
        return [self._tools[name] for name in self.list_enabled()]

    def openai_tool_specs(self) -> list[dict]:
        specs: list[dict] = []
        for tool in self.enabled_tools():
            specs.append(tool.spec().__dict__)
        return specs

    def call(self, name: str, args: dict[str, Any]) -> str:
        if name not in self._tools:
            raise KeyError(f"tool not found: {name}")
        if self._enabled is not None and name not in self._enabled:
            raise PermissionError(f"tool disabled: {name}")
        return self._tools[name].run(args or {})


def build_default_tools(fs_root: str = ".") -> list[Tool]:
    return [
        EchoTool(),
        TimeNowTool(),
        FsListTool(root=fs_root),
        FsReadTool(root=fs_root),
    ]
