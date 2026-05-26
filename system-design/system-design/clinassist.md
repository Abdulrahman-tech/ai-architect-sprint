# ClinAssist — System Design Document

## Problem Statement
People in underserved areas need basic health guidance and symptom
triage without access to a doctor. The agent must be safe enough that
it helps without causing harm.

## Architecture

## Tools Chosen and Why

| Tool | Why |
|------|-----|
| Pure Python RAG | No ChromaDB/sentence-transformers needed, works offline |
| Word-frequency cosine similarity | No ML model download, no internet required |
| Pydantic schemas | Enforce safety contract — disclaimer always present |
| HITL gate | Conscious user consent before every response |
| Emergency keywords | Instant detection, zero API cost |

## Trade-offs Made

**No ML embeddings:**
Used word-frequency vectors instead of sentence-transformers.
Reason: external model downloads blocked in many environments.
Trade-off: lower retrieval accuracy for complex queries.
Mitigation: title weighting (3x) improves topic matching significantly.

**Rule-based urgency vs ML classification:**
Keyword counting instead of trained classifier.
Reason: explainable, auditable, no training data.
Trade-off: misses nuanced symptom combinations.

## Lessons Learned
- Safety layers must run BEFORE the LLM sees anything
- Pydantic schemas are safety contracts, not just data validation
- HITL confirmation forces conscious user engagement
- RAG without ML is still RAG — the principle is retrieval + grounding

## What I Would Do Differently
- Use real PubMed abstracts via API instead of hardcoded knowledge base
- Add multilingual support (Hausa, Yoruba, Igbo for Nigerian users)
- Build symptom history across sessions using Day 3 memory patterns