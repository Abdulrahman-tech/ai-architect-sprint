# AI Architect Sprint — 14 Days

Building production-grade agentic AI systems from scratch.
Based on "Building Agentic AI Systems" by Biswas & Talukdar (Packt).

**Stack:** Python 3.13 · Google ADK · Gemini 2.0 Flash · yfinance

---

## Week 1 — Foundations & FinSight Finance Agent

| Day | Topic | What I Built |
|-----|-------|-------------|
| 1 | Agent fundamentals | HelloAgent — switchable personas |
| 2 | Tool use & function calling | Multi-tool agent with rate limiter |
| 3 | Memory & state management | Stateful agent with JSON persistence |
| 4 | Multi-agent orchestration | FinSight v0.1 — live stock data |
| 5 | Planning & ReAct reasoning | FinSight v0.2 — risk assessment |
| 6 | Evaluation & observability | FinSight v1.0 — tracing + scoring |
| 7 | Architecture review | Published FinSight to GitHub |

## Week 2 — Advanced Agents (Coming)

| Day | Topic | Project |
|-----|-------|---------|
| 8 | Human-in-the-loop | ClinAssist v0.1 |
| 9 | RAG pipelines | ClinAssist v0.2 |
| 10 | Structured output | ClinAssist v1.0 |
| 11 | Autonomous agents | DevOps AutoPilot v0.1 |
| 12 | Tool chaining | DevOps AutoPilot v0.2 |
| 13 | Deployment & security | DevOps AutoPilot v1.0 |
| 14 | Portfolio day | All 3 projects live |

---

## Portfolio Projects

### 1. FinSight — Finance Agent
Multi-agent portfolio analysis with risk assessment and evaluation harness.
→ [day-04](./day-04) · [day-05](./day-05) · [day-06](./day-06)

### 2. ClinAssist — Health Agent *(Week 2)*
RAG-powered symptom triage with human-in-the-loop safety gates.

### 3. DevOps AutoPilot — Tech Agent *(Week 2)*
Autonomous CI/CD monitoring with diagnosis and fix suggestions.

---

## Key Learnings So Far

**Docstrings are routing logic.**
The agent picks tools based purely on your docstring quality.
A vague description = wrong tool selected = silent bug.

**Memory = context injection.**
AI agents don't truly remember. You load past data from disk,
format it as text, and inject it into the system prompt.

**Multi-agent = separation of concerns.**
Each agent should do one thing well.
Orchestrators coordinate. Specialists execute.

**Measure everything from day one.**
An agent that works ≠ an agent you can trust.
Trust requires traces, scores, and ground truth.

**Free tier has real limits.**
Design for quota efficiency from the start.
Collapsing multi-agent pipelines into smart single-agent
tools is a valid production decision, not a shortcut.