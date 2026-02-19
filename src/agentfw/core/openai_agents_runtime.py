from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agents import (
    Agent,
    FunctionTool,
    ModelSettings,
    SessionSettings,
    set_default_openai_api,
    set_default_openai_client,
)
from agents.mcp import MCPServerManager, MCPServerSse, MCPServerStdio, MCPServerStreamableHttp
from openai import AsyncOpenAI

from agentfw.tools.registry import ToolRegistry


_ENV_VAR_PATTERN = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)|%([A-Za-z_][A-Za-z0-9_]*)%"
)


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _expand_env_str(value: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2) or match.group(3) or ""
        return os.environ.get(key, "")

    return _ENV_VAR_PATTERN.sub(_replace, value)


def configure_openai(llm_cfg: dict[str, Any]) -> None:
    provider = str(llm_cfg.get("provider") or "openai_agents").strip()
    if provider != "openai_agents":
        raise RuntimeError(
            f"Unsupported llm.provider={provider}. This project now uses openai_agents."
        )

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Set OPENAI_API_KEY (or GEMINI_API_KEY) before starting."
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not base_url:
        base_url = str(llm_cfg.get("base_url") or "").strip()
    base_url = base_url or None
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    set_default_openai_client(client)

    api_mode = str(llm_cfg.get("openai_api") or "responses").strip()
    if api_mode not in {"responses", "chat_completions"}:
        raise RuntimeError(
            "llm.openai_api must be either 'responses' or 'chat_completions'."
        )
    set_default_openai_api(api_mode)


def build_model_settings(llm_cfg: dict[str, Any]) -> ModelSettings:
    return ModelSettings(
        temperature=_to_float(llm_cfg.get("temperature"), 0.2),
        max_tokens=_to_int(llm_cfg.get("max_tokens"), 800),
    )


def build_session(memory_cfg: dict[str, Any]):
    from agents import SQLiteSession

    memory_type = str(memory_cfg.get("type") or "sqlite_session").strip()
    if memory_type != "sqlite_session":
        raise RuntimeError("memory.type currently supports only 'sqlite_session'.")

    db_path = str(memory_cfg.get("db_path") or ".agent/sessions.db").strip()
    session_id = str(memory_cfg.get("session_id") or "default").strip()

    db_parent = Path(db_path).parent
    db_parent.mkdir(parents=True, exist_ok=True)

    history_limit = memory_cfg.get("history_limit")
    settings = None
    if history_limit is not None:
        settings = SessionSettings(limit=_to_int(history_limit, 50))

    return SQLiteSession(session_id=session_id, db_path=db_path, session_settings=settings)


def tool_registry_to_agents_tools(registry: ToolRegistry) -> list[FunctionTool]:
    out: list[FunctionTool] = []

    for tool in registry.enabled_tools():

        async def _invoke(_ctx, input_json: str, _tool=tool):
            if not input_json:
                args: dict[str, Any] = {}
            else:
                obj = json.loads(input_json)
                if not isinstance(obj, dict):
                    raise ValueError(f"Tool {_tool.name} expects a JSON object input.")
                args = obj
            result = _tool.run(args)
            return str(result)

        out.append(
            FunctionTool(
                name=tool.name,
                description=tool.description,
                params_json_schema=tool.input_schema,
                on_invoke_tool=_invoke,
                strict_json_schema=False,
            )
        )

    return out


def build_mcp_servers(mcp_cfg: dict[str, Any]) -> list[Any]:
    if not mcp_cfg or not bool(mcp_cfg.get("enabled", False)):
        return []

    servers_cfg = mcp_cfg.get("servers") or []
    if not isinstance(servers_cfg, list):
        raise RuntimeError("mcp.servers must be a list.")

    servers: list[Any] = []
    for idx, item in enumerate(servers_cfg):
        if not isinstance(item, dict):
            raise RuntimeError(f"mcp.servers[{idx}] must be an object.")

        name = item.get("name")
        transport = str(item.get("transport") or "stdio").strip()

        cache_tools_list = bool(item.get("cache_tools_list", False))
        use_structured_content = bool(item.get("use_structured_content", False))

        if transport == "stdio":
            command = _expand_env_str(str(item.get("command") or "").strip())
            if not command:
                raise RuntimeError(f"mcp.servers[{idx}].command is required for stdio transport.")
            params: dict[str, Any] = {"command": command}

            args = item.get("args")
            if isinstance(args, list):
                params["args"] = [_expand_env_str(str(x)) for x in args]

            env = item.get("env")
            if isinstance(env, dict):
                params["env"] = {str(k): _expand_env_str(str(v)) for k, v in env.items()}

            cwd = item.get("cwd")
            if cwd is not None:
                params["cwd"] = _expand_env_str(str(cwd))

            servers.append(
                MCPServerStdio(
                    params=params,
                    name=name,
                    cache_tools_list=cache_tools_list,
                    use_structured_content=use_structured_content,
                )
            )
            continue

        if transport == "sse":
            url = _expand_env_str(str(item.get("url") or "").strip())
            if not url:
                raise RuntimeError(f"mcp.servers[{idx}].url is required for sse transport.")
            params = {"url": url}

            headers = item.get("headers")
            if isinstance(headers, dict):
                params["headers"] = {str(k): _expand_env_str(str(v)) for k, v in headers.items()}

            timeout = item.get("timeout")
            if timeout is not None:
                params["timeout"] = _to_float(timeout, 10.0)

            sse_read_timeout = item.get("sse_read_timeout")
            if sse_read_timeout is not None:
                params["sse_read_timeout"] = _to_float(sse_read_timeout, 10.0)

            servers.append(
                MCPServerSse(
                    params=params,
                    name=name,
                    cache_tools_list=cache_tools_list,
                    use_structured_content=use_structured_content,
                )
            )
            continue

        if transport == "streamable_http":
            url = _expand_env_str(str(item.get("url") or "").strip())
            if not url:
                raise RuntimeError(
                    f"mcp.servers[{idx}].url is required for streamable_http transport."
                )
            params = {"url": url}

            headers = item.get("headers")
            if isinstance(headers, dict):
                params["headers"] = {str(k): _expand_env_str(str(v)) for k, v in headers.items()}

            timeout = item.get("timeout")
            if timeout is not None:
                params["timeout"] = _to_float(timeout, 10.0)

            sse_read_timeout = item.get("sse_read_timeout")
            if sse_read_timeout is not None:
                params["sse_read_timeout"] = _to_float(sse_read_timeout, 10.0)

            terminate_on_close = item.get("terminate_on_close")
            if terminate_on_close is not None:
                params["terminate_on_close"] = bool(terminate_on_close)

            servers.append(
                MCPServerStreamableHttp(
                    params=params,
                    name=name,
                    cache_tools_list=cache_tools_list,
                    use_structured_content=use_structured_content,
                )
            )
            continue

        raise RuntimeError(
            f"Unsupported mcp transport '{transport}'. Use stdio, sse, or streamable_http."
        )

    return servers


def build_mcp_manager(servers: list[Any], mcp_cfg: dict[str, Any]) -> MCPServerManager | None:
    if not servers:
        return None

    return MCPServerManager(
        servers,
        connect_timeout_seconds=_to_float(mcp_cfg.get("connect_timeout_seconds"), 10.0),
        cleanup_timeout_seconds=_to_float(mcp_cfg.get("cleanup_timeout_seconds"), 10.0),
        drop_failed_servers=bool(mcp_cfg.get("drop_failed_servers", True)),
        strict=bool(mcp_cfg.get("strict", False)),
        connect_in_parallel=bool(mcp_cfg.get("connect_in_parallel", True)),
    )


def build_agent(
    *,
    agent_cfg: dict[str, Any],
    llm_cfg: dict[str, Any],
    registry: ToolRegistry,
    mcp_servers: list[Any],
) -> Agent:
    tools = tool_registry_to_agents_tools(registry)
    model = str(llm_cfg.get("model") or "gpt-4.1-mini")

    return Agent(
        name=str(agent_cfg.get("name") or "assistant"),
        instructions=str(agent_cfg.get("system_prompt") or "You are a helpful assistant."),
        model=model,
        model_settings=build_model_settings(llm_cfg),
        tools=tools,
        mcp_servers=mcp_servers,
    )
