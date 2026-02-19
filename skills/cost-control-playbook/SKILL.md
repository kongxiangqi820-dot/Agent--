---
name: cost-control-playbook
description: Optimize AI service cost with token budgeting, model routing, caching, and quota controls. Use when user asks how to reduce API/model spending while keeping quality.
triggers:
  - 成本控制
  - token成本
  - 降本
  - 模型路由
  - cost optimization
---

# Cost Control Playbook

## Goal
Lower total cost without breaking core user experience.

## Workflow
1. Split cost by source:
   - model tokens
   - external APIs
   - compute and storage
2. Apply baseline controls:
   - per-request token cap
   - timeout cap
   - user and tenant quota
3. Add optimization:
   - cache repeated queries
   - route simple tasks to cheaper models
   - degrade optional tool calls
4. Track cost KPIs weekly.

## Output
1. Cost breakdown
2. Immediate savings actions
3. Guardrail config list
4. KPI dashboard fields

## Constraints
- Do not degrade critical quality silently.
- Announce fallback behavior when quality may drop.
- Keep optimization rules versioned and reversible.
