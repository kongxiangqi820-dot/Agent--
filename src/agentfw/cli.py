from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from agents import Runner

from agentfw.core.config import load_config
from agentfw.core.openai_agents_runtime import (
    build_agent,
    build_mcp_manager,
    build_mcp_servers,
    build_session,
    configure_openai,
)
from agentfw.core.skills import compose_prompt_with_skills, load_skill_store
from agentfw.tools.registry import ToolRegistry, build_default_tools


def _format_output(value: Any) -> str:
    if value is None:
        return "(empty response)"
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _build_registry(cfg: dict[str, Any]) -> ToolRegistry:
    reg = ToolRegistry()
    tools_cfg = cfg.get("tools", {}) or {}
    enabled = tools_cfg.get("enabled") or []
    fs_root = tools_cfg.get("fs_root") or "."

    for t in build_default_tools(fs_root=fs_root):
        reg.register(t)

    if enabled:
        reg.enable_only(set(enabled))

    return reg


async def _run_cli(cfg: dict[str, Any], dump_tools: bool, *, config_dir: Path) -> int:
    reg = _build_registry(cfg)

    if dump_tools:
        print(json.dumps(reg.openai_tool_specs(), ensure_ascii=False, indent=2))
        return 0

    llm_cfg = cfg.get("llm", {}) or {}
    agent_cfg = cfg.get("agent", {}) or {}
    mem_cfg = cfg.get("memory", {}) or {}
    mcp_cfg = cfg.get("mcp", {}) or {}
    skills_cfg = cfg.get("skills", {}) or {}

    configure_openai(llm_cfg)

    session = build_session(mem_cfg)
    max_turns = int(agent_cfg.get("max_turns", agent_cfg.get("max_tool_steps", 10)))

    servers = build_mcp_servers(mcp_cfg)
    mcp_manager = build_mcp_manager(servers, mcp_cfg)

    active_servers = []
    if mcp_manager is not None:
        await mcp_manager.__aenter__()
        active_servers = mcp_manager.active_servers

    skill_store = load_skill_store(skills_cfg, config_dir=config_dir)
    agent_cache: dict[tuple[str, ...], Any] = {}

    def _agent_for_input(user_input: str):
        active_skills = skill_store.match(user_input) if skill_store is not None else []
        key = tuple(skill.name for skill in active_skills)
        if key in agent_cache:
            return agent_cache[key], active_skills

        scoped_agent_cfg = dict(agent_cfg)
        base_prompt = str(agent_cfg.get("system_prompt") or "")
        scoped_agent_cfg["system_prompt"] = compose_prompt_with_skills(base_prompt, active_skills)

        agent = build_agent(
            agent_cfg=scoped_agent_cfg,
            llm_cfg=llm_cfg,
            registry=reg,
            mcp_servers=active_servers,
        )
        agent_cache[key] = agent
        return agent, active_skills

    print("Agent CLI (OpenAI Agents SDK). Type /help for commands.")
    if mcp_manager is not None:
        print(f"MCP connected: {len(mcp_manager.active_servers)} active, {len(mcp_manager.failed_servers)} failed")
    if skill_store is None:
        print("Skills: disabled")
    else:
        print(f"Skills: enabled, loaded {len(skill_store.skills)}")

    try:
        while True:
            try:
                user = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return 0

            if not user:
                continue

            if user in ("/exit", "/quit"):
                print("Bye.")
                return 0

            if user == "/help":
                print(
                    "\nCommands:\n"
                    "  /help              Show help\n"
                    "  /exit              Exit\n"
                    "  /tools             Show enabled local tools\n"
                    "  /mcp               Show MCP connection status\n"
                    "  /skills            Show loaded skills\n"
                    "  !<tool> <json>     Call local tool directly, e.g. !echo {\"text\":\"hi\"}\n"
                )
                continue

            if user == "/tools":
                for name in reg.list_enabled():
                    print(f"- {name}")
                continue

            if user == "/mcp":
                if mcp_manager is None:
                    print("MCP disabled")
                else:
                    print(
                        f"MCP active={len(mcp_manager.active_servers)}, "
                        f"failed={len(mcp_manager.failed_servers)}"
                    )
                continue

            if user == "/skills":
                if skill_store is None:
                    print("Skills disabled")
                elif not skill_store.skills:
                    print("Skills enabled but none found")
                else:
                    for skill in skill_store.skills:
                        desc = f" - {skill.description}" if skill.description else ""
                        print(f"- {skill.name}{desc}")
                continue

            if user.startswith("!"):
                try:
                    tool_name, rest = user[1:].split(" ", 1)
                except ValueError:
                    tool_name, rest = user[1:], "{}"

                tool_name = tool_name.strip()
                rest = rest.strip() or "{}"
                try:
                    args_obj = json.loads(rest)
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON: {e}")
                    continue

                try:
                    out = reg.call(tool_name, args_obj)
                except Exception as e:
                    print(f"Tool error: {e}")
                    continue

                print(out)
                continue

            try:
                agent, active_skills = _agent_for_input(user)
                if active_skills:
                    print(f"Using skills: {', '.join(s.name for s in active_skills)}")
                result = await Runner.run(
                    agent,
                    user,
                    max_turns=max_turns,
                    session=session,
                )
                print(f"\nAssistant> {_format_output(result.final_output)}")
            except Exception as e:
                print(f"Run failed: {e}")
                continue
    finally:
        if mcp_manager is not None:
            await mcp_manager.__aexit__(None, None, None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agentfw", description="Agent CLI built on OpenAI Agents SDK")
    ap.add_argument("--config", default="agent.json", help="Path to config file")
    ap.add_argument("--dump-tools", action="store_true", help="Print local tools schema and exit")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    config_dir = Path(args.config).resolve().parent
    try:
        return asyncio.run(_run_cli(cfg, dump_tools=args.dump_tools, config_dir=config_dir))
    except Exception as e:
        print(f"Startup failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
