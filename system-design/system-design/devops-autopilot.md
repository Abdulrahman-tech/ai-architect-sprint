# DevOps AutoPilot — System Design Document

## Problem Statement
On-call engineers waste time manually reading CI/CD logs to diagnose
failures. The agent should classify failures, route to the right team,
and suggest fixes — with minimal API usage.

## Architecture

## Tools Chosen and Why

| Tool | Why |
|------|-----|
| Regex pattern matching | Fast, deterministic, zero API cost |
| Python lookup table routing | Auditable, instantly changeable |
| HMAC-SHA256 webhook auth | Industry standard, no dependencies |
| Per-IP rate limiting | Protects quota and prevents abuse |
| Log sanitization | Secrets never enter LLM context |

## Trade-offs Made

**Mock pipelines vs real CI/CD API:**
Used mock pipeline data instead of real GitHub Actions API.
Reason: requires OAuth tokens and live repo setup.
Trade-off: not production-ready without real data source.
Mitigation: architecture is identical — swap mock for real API call.

**Pattern matching vs ML classification:**
Regex patterns instead of trained log classifier.
Reason: deterministic, fast, zero cost, easy to update.
Trade-off: brittle for unfamiliar log formats.
Mitigation: self-correction loop (Day 11 sprint topic).

## Lessons Learned
- 90% of DevOps automation is deterministic — use Python not LLM
- Security must run before data enters the agent context
- Prompt injection is real — test it explicitly
- Rate limiting is not optional in production

## What I Would Do Differently
- Connect to real GitHub Actions API
- Add Slack/PagerDuty webhook for real notifications
- Build a web dashboard instead of terminal interface
- Add ML-based log anomaly detection for unknown failure types