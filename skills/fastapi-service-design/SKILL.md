---
name: fastapi-service-design
description: Design and refine FastAPI service architecture including endpoints, request and response schema, auth, health checks, and deploy readiness. Use when user asks about API serviceization from CLI workflows.
triggers:
  - FastAPI
  - 服务化
  - API设计
  - healthz
  - readyz
---

# FastAPI Service Design

## Goal
Make backend APIs stable, clear, and ready for external integration.

## Workflow
1. Confirm API purpose and client side (web, miniapp, workflow engine).
2. Define endpoint set:
   - business endpoint (`/v1/chat`)
   - health endpoint (`/healthz`)
   - readiness endpoint (`/readyz`)
   - metrics endpoint (`/metrics`)
3. Standardize schema:
   - request: message, session_id, user_id, metadata
   - response: code, message, request_id, timestamp, data, error
4. Enforce auth and timeout defaults.

## Output
1. API contract summary
2. Example request and response
3. Error code mapping
4. Deployment checklist

## Constraints
- Keep backward compatibility for existing clients.
- Separate liveness and readiness semantics clearly.
- Include request_id for traceability.
