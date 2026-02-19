---
name: miniapp-api-integration
description: Connect backend AI APIs to WeChat Mini Program with auth headers, error mapping, timeout handling, and streaming strategy selection. Use when user asks about miniapp integration details.
triggers:
  - 小程序接入
  - 微信小程序
  - X-API-Key
  - 前端报错映射
  - miniapp api
---

# Miniapp API Integration

## Goal
Make miniapp-to-backend integration stable and debuggable.

## Workflow
1. Confirm transport mode:
   - standard request response
   - SSE stream
   - WebSocket stream
2. Define request headers and body:
   - X-API-Key
   - X-Request-ID
   - message, session_id, user_id, metadata
3. Map backend error codes to front-end user tips.
4. Add client timeout, retry boundary, and fallback UI.

## Output
1. Request template
2. Response and error mapping table
3. UX fallback plan for timeout or auth failures

## Constraints
- Do not place service secrets in miniapp frontend code.
- Keep user-facing error text concise and actionable.
- Preserve request_id for troubleshooting.
