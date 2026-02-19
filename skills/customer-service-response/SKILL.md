---
name: customer-service-response
description: Create professional customer service replies for complaints, refunds, delivery delays, and after-sales cases. Use when user asks for customer reply templates, escalation wording, or service scripts.
triggers:
  - 客服回复
  - 客诉
  - 投诉处理
  - 售后话术
  - refund reply
---

# Customer Service Response

## Goal
Deliver clear, polite, and executable customer-facing responses with risk control.

## Workflow
1. Identify case type: complaint, refund, delivery delay, quality issue, or account issue.
2. Extract mandatory facts: order id, timeline, customer claim, current status.
3. Generate response in four blocks:
   - empathy
   - confirmed facts
   - concrete action and ETA
   - fallback escalation path
4. Add internal note when evidence is missing.

## Output
1. External reply (for customer)
2. Internal handling note (for agent/team)
3. Risk flags (if legal or compensation risk exists)

## Constraints
- Do not promise compensation without policy basis.
- Keep wording neutral and auditable.
- Mark uncertain details as pending verification.
