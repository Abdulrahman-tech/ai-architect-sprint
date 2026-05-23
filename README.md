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


# ClinAssist v0.2 — RAG-Grounded Triage (Day 9)

Day 9 of the Agentic AI Architect Sprint: a **RAG pipeline** added to the
ClinAssist triage agent so every response is grounded in retrieved evidence
with source citations — while keeping the Day 8 human-in-the-loop (HITL) gate
and safety guardrails.

## What it does

```
symptoms ─▶ retrieve_medical_evidence  (chunk ▸ embed ▸ ChromaDB ▸ semantic search ▸ hybrid re-rank)
         ─▶ triage agent (Gemini, never diagnoses, urgency routing only)
         ─▶ HITL gate (a human must approve the draft)
         ─▶ grounded answer + citations + safety disclaimer
```

## Files

| File | Role |
|------|------|
| `knowledge_base.py` | The corpus loader + sentence-aware chunker (loads `knowledge.jsonl` if present, else illustrative defaults) |
| `ingest.py` | Fetch real pages (NHS / WHO / etc.) → clean → chunk → `knowledge.jsonl` |
| `rag.py` | The Day 9 core: pluggable embedder + pluggable re-ranker (lexical default, optional cross-encoder), ChromaDB store |
| `clinassist.py` | The agents: retrieval tool, ADK triage agent, HITL gate, orchestration |
| `test_rag.py` | Offline RAG tests, incl. the cross-encoder via an injected stub (no key, no network) |
| `test_ingest.py` | Offline tests for the HTML parser |
| `test_clinassist.py` | Offline tests for the agent layer |
| `requirements.txt` | Dependencies (with the OpenTelemetry pin explained below) |
| `.env.example` | Template for your Gemini API key |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then paste your free key from aistudio.google.com
```

## Run

```bash
python test_rag.py          # verify the RAG pipeline + cross-encoder wiring (no key)
python test_ingest.py       # verify the HTML ingestion parser (no key, no network)
python test_clinassist.py   # verify the agent layer (no key)
python rag.py               # see retrieval + re-rank scoring on sample queries
python clinassist.py        # interactive triage (uses Gemini if a key is set)
```

### Use real sources instead of the illustrative corpus

```bash
python ingest.py https://www.nhs.uk/conditions/chest-pain/ \
                 https://www.nhs.uk/conditions/fever-in-adults/
# writes knowledge.jsonl, which the pipeline then loads automatically
python rag.py   # now retrieves from the real ingested content
```

`knowledge_base.load_corpus()` uses `knowledge.jsonl` if it exists and silently
falls back to the built-in illustrative passages otherwise — so swapping in real
data needs no code change. (Only ingest openly licensed sources, e.g. NHS
content under the Open Government Licence, and respect each site's robots.txt.)

### Swap in the cross-encoder re-ranker (higher precision)

```python
from rag import RagPipeline, CrossEncoderReRanker
pipe = RagPipeline(reranker=CrossEncoderReRanker()).build()  # needs sentence-transformers
```

The default `HybridLexicalReRanker` needs no download and is great for dev/CI;
the cross-encoder re-scores each (query, chunk) pair for better ranking quality.

Without a `GOOGLE_API_KEY`, `clinassist.py` runs a **retrieval-only demo** so you
can still see grounding, citations, and the safety disclaimer working. Add the
key to enable the LLM triage step.

## How to debug it

The pipeline is built to be inspected, not guessed at:

- `pipe.query("...", debug=True)` prints the semantic score, keyword score, and
  final blended score for **every** candidate, so you can see exactly why a
  chunk ranked where it did.
- The RAG module has **zero dependency on ADK or any API key** — you can import
  `RagPipeline` in a plain `python` shell and poke at it directly.
- Every helper (`_tokenize`, `_keyword_overlap`, `_distance_to_similarity`) is a
  tiny pure function with its own test.
- The HITL `confirm` callback is injectable, so the gate is testable without
  real keyboard input.

## Design decisions

- **Retrieval is a deterministic tool, not a second LLM.** Grounding stays
  auditable and free, and citations never depend on the model remembering to
  include them. (You could instead wrap a separate `LlmAgent` as an `AgentTool`
  if you want the retrieval step itself to reason.)
- **Pluggable embedder.** The default `TfidfEmbedder` needs no model download
  and runs anywhere — ideal for tests and CI. Swap in
  `SentenceTransformerEmbedder` for production semantic quality (one extra
  dependency + a one-time download). Both share the same interface.
- **Hybrid re-ranking** = `0.7 · semantic + 0.3 · keyword-overlap` by default —
  simple and explainable. Swap in `CrossEncoderReRanker` for higher-precision
  re-ranking; both implement the same `ReRanker` interface.
- **Defense-in-depth safety.** The "never diagnose / always defer to a
  professional" rule is in the agent instruction *and* the disclaimer is
  appended programmatically, so safety doesn't rely solely on the LLM.
- **In-memory ChromaDB** keeps the project self-contained. Switch to
  `chromadb.PersistentClient(path=...)` to persist the index to disk.

## Known limitations

- The corpus is **illustrative only** — not real clinical guidance. Replace it
  with genuine public sources (WHO / NHS / PubMed) for anything beyond learning.
- TF-IDF retrieval is lexical-ish; semantic recall improves a lot with
  `sentence-transformers`.
- Schema-validated structured output (Pydantic) and PDF export come in Day 10.

## Setup gotcha worth knowing

`google-adk` and `chromadb` both depend on **OpenTelemetry** and pin
incompatible ranges. If you see an `ImportError` from `chromadb` about
`opentelemetry`, pin every otel package to one version (done in
`requirements.txt`, `==1.41.1`, which satisfies google-adk 2.0).