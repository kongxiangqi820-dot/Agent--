---
name: ops-observability-baseline
description: Build baseline observability for production AI services with structured logs, metrics, alerts, and incident triage. Use when user asks how to monitor, alert, and troubleshoot service issues.
triggers:
  - 运维
  - 监控
  - 告警
  - 日志标准化
  - observability
---

# Ops Observability Baseline

## Goal
Make service state visible and actionable.

## Workflow
1. Enforce JSON logs with required fields:
   - request_id
   - session_id
   - user_id
   - error_code
2. Define key metrics:
   - QPS
   - success rate
   - 4xx and 5xx
   - latency P50 and P95
   - model/tool failure rate
3. Set initial alerts:
   - error rate threshold
   - latency threshold
   - repeated MCP failure threshold
4. Prepare incident triage flow using request_id.

## Output
1. Logging checklist
2. Metrics checklist
3. Alert rules (initial values)
4. Triage SOP

## Constraints
- Avoid alert storms with sensible windows.
- Keep logs free from secret values.
- Link every alert to an actionable runbook step.
