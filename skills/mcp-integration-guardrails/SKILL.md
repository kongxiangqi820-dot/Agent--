---
name: mcp-integration-guardrails
description: Design reliable MCP integration with timeouts, fallback, security boundaries, and version pinning. Use when user asks about choosing or integrating MCP servers in production.
triggers:
  - MCP接入
  - MCP server
  - 工具熔断
  - 超时重试
  - mcp guardrails
---

# MCP Integration Guardrails

## Goal
Integrate MCP servers safely without turning tool failures into service failures.

## Workflow
1. Classify each MCP by criticality: required vs optional.
2. Set timeout and retry policy per MCP call.
3. Define degradation behavior:
   - optional MCP failure -> continue with no-tool answer and explicit notice
   - required MCP failure -> return controlled error code
4. Pin versions for reproducibility and rollback.
5. Add readiness checks for critical MCP only.

## Output
1. MCP inventory table
2. Timeout and retry matrix
3. Degradation rules
4. Version pin and rollback plan

## Constraints
- Do not expose secrets in tool logs.
- Do not block whole service on optional MCP failures.
- Keep error messages user-friendly and auditable.
