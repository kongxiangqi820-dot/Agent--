# Project Agent Notes

This repository now runs on **OpenAI Agents SDK (Python)**.

## Runtime

- `src/agentfw/cli.py`: CLI entrypoint
- `src/agentfw/core/openai_agents_runtime.py`: OpenAI Agents SDK integration
- `src/agentfw/tools/`: local tools
- `agent.json`: runtime config

## Run

- `run.cmd` (recommended on Windows)
- or `run.ps1`

## Extend

1. Add local tools in `src/agentfw/tools/`
2. Register them in `src/agentfw/tools/registry.py`
3. Enable tool names in `agent.json` -> `tools.enabled`
4. Add MCP servers in `agent.json` -> `mcp.servers`

## Environment

- Required: `OPENAI_API_KEY`
- Optional: `OPENAI_BASE_URL`
