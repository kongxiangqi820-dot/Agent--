---
name: nearby-food-analysis
description: Analyze nearby food options around a target location for business decisions and local market scanning.
triggers:
  - 周边美食
  - 附近餐饮
  - 1公里美食
  - 门店餐饮分析
  - food analysis
---

# Nearby Food Analysis

## Goal
Produce a practical nearby-food report with clear distance, category mix, and business implications.

## Workflow
1. Confirm target location and analysis radius (default 1000m).
2. Collect nearby stores using map/tool data and keep source date explicit.
3. Deduplicate stores and keep key fields:
   - name
   - distance
   - address
   - category or tag
4. Summarize:
   - nearest choices
   - category distribution
   - quick opportunity and risk notes

## Output
Use this structure:
1. Summary
2. Data snapshot (location, radius, source, date)
3. Top nearby food list
4. Business insight and next actions

## Constraints
- Do not invent names, addresses, or distances.
- Always show source and date.
- Mark uncertainty when data is incomplete.
