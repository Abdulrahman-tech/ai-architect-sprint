# agent.py — Day 10: ClinAssist v1.0 — Structured Output with Pydantic
import os
import asyncio
import time
from datetime import datetime

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("\n❌ API key not set!\nRun: export GOOGLE_API_KEY='your_key_here'")
print(f"✅ API key loaded: {api_key[:8]}...")

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from safety import check_emergency, check_output_safety, sanitize_input
from rag import retrieve, format_context, MEDICAL_KNOWLEDGE
from schemas import (
    ClinicalSummary, validate_clinical_summary,
    format_summary_report
)

APP_NAME   = "clinassist_app"
USER_ID    = "patient_user"
SESSION_ID = "day10_session"

_last_call_time = 0

def wait_between_calls():
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if _last_call_time > 0 and elapsed < 15:
        wait = 15 - elapsed
        print(f"  ⏳ Waiting {wait:.1f}s...")
        time.sleep(wait)
    _last_call_time = time.time()

# ── TOOLS ─────────────────────────────────────────────────────────────────────

def triage_symptoms(symptoms: str) -> dict:
    """Performs full triage assessment with schema-validated structured output.
    Use when user describes any physical symptoms or health complaints.
    Args:
        symptoms: Patient-reported symptoms
    """
    retrieved = retrieve(symptoms, top_k=2)
    symptoms_lower = symptoms.lower()

    high_kw = ["chest", "breath", "severe", "worst", "sudden", "numbness",
               "vision", "speech", "confusion", "faint", "blood", "39", "40", "41"]
    medium_kw = ["fever", "vomiting", "diarrhea", "pain", "ache", "dizzy",
                 "nausea", "rash", "infection", "wound", "burn"]

    high_count = sum(1 for kw in high_kw if kw in symptoms_lower)
    medium_count = sum(1 for kw in medium_kw if kw in symptoms_lower)

    if high_count >= 2:
        urgency, recommendation = "HIGH", "Go to emergency room immediately"
    elif high_count == 1 or medium_count >= 2:
        urgency, recommendation = "MEDIUM", "See doctor today or tomorrow"
    elif medium_count == 1:
        urgency, recommendation = "LOW", "Schedule routine appointment (3-7 days)"
    else:
        urgency, recommendation = "LOW", "Monitor at home"

    raw = {
        "patient_reported_symptoms": symptoms,
        "urgency_level": urgency,
        "triage_recommendation": recommendation,
        "symptom_summary": (
            f"Patient reports: {symptoms[:200]}. "
            f"Urgency assessed as {urgency} based on symptom analysis."
        ),
        "evidence_sources": [
            {
                "source": doc["source"],
                "title": doc["title"],
                "excerpt": doc["content"][:150] + "...",
                "relevance_score": doc["relevance_score"],
            }
            for doc in retrieved
        ],
        "professional_consultation_required": True,
        "disclaimer": (
            "This assessment is for general guidance only and does not "
            "constitute medical advice. Always consult a qualified "
            "healthcare professional."
        ),
    }

    is_valid, summary_obj, error = validate_clinical_summary(raw)

    if not is_valid:
        return {"error": f"Schema validation failed: {error}"}

    return {
        "status": "validated",
        "urgency_level": summary_obj.urgency_level.value,
        "triage_recommendation": summary_obj.triage_recommendation.value,
        "symptom_summary": summary_obj.symptom_summary,
        "sources": [f"{s.source} — {s.title}" for s in summary_obj.evidence_sources],
        "professional_consultation_required": True,
        "disclaimer": summary_obj.disclaimer,
    }


def get_health_info(topic: str) -> dict:
    """Retrieves evidence-grounded health education on a topic.
    Use for general health questions, NOT for diagnosing symptoms.
    Args:
        topic: Health topic e.g. 'malaria', 'diabetes', 'dehydration'
    """
    retrieved = retrieve(topic, top_k=2)

    if not retrieved or retrieved[0]["relevance_score"] == 0:
        return {
            "found": False,
            "topic": topic,
            "message": f"No information found for '{topic}'.",
            "suggestion": "Please consult a healthcare professional.",
            "disclaimer": "General health education only. Not medical advice.",
        }

    return {
        "found": True,
        "topic": topic,
        "results": [
            {
                "source": doc["source"],
                "title": doc["title"],
                "content": doc["content"],
                "relevance": doc["relevance_score"],
            }
            for doc in retrieved
        ],
        "disclaimer": "General health education only. Not medical advice.",
    }


# ── AGENT ─────────────────────────────────────────────────────────────────────
def build_agent(user_query: str = "") -> LlmAgent:
    rag_context = ""
    if user_query:
        docs = retrieve(user_query, top_k=2)
        rag_context = format_context(docs)

    return LlmAgent(
        name="ClinAssist",
        model="gemini-2.0-flash",
        description="ClinAssist v1.0 — schema-validated health triage.",
        instruction=f"""You are ClinAssist v1.0, a health triage assistant.

        PRE-RETRIEVED CONTEXT:
        {rag_context if rag_context else "No context yet."}

        Tools:
        - triage_symptoms: for any symptom descriptions
        - get_health_info: for general health education

        STRICT RULES:
        - NEVER diagnose any condition
        - NEVER recommend specific medications
        - ALWAYS use triage_symptoms for symptom reports
        - ALWAYS cite evidence sources
        - ALWAYS include the disclaimer from tool results

        Response format for triage:
        1. Urgency level clearly stated
        2. Recommended action
        3. Brief summary
        4. Evidence sources
        5. Disclaimer from tool result
        """,
        tools=[triage_symptoms, get_health_info],
    )


session_service = InMemorySessionService()
_runner = None  # global runner — created once, reused forever

async def setup():
    global _runner
    agent = build_agent()  # initial agent with no query context
    _runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print(f"✅ Session ready: {session.id}")
    print(f"✅ Knowledge base: {len(MEDICAL_KNOWLEDGE)} documents")
    print("✅ Pydantic schema validation: ACTIVE")
    print("✅ Safety guardrails: ACTIVE")
    

def get_hitl_confirmation(user_input: str) -> bool:
    print(f"\n  📋 HITL CHECK — '{user_input[:60]}'")
    confirm = input("  Proceed? (yes/no): ").strip().lower()
    return confirm in ["yes", "y"]

async def chat(message: str) -> str:
    message = sanitize_input(message)

    emergency = check_emergency(message)
    if emergency["is_emergency"]:
        return emergency["message"]

    if not get_hitl_confirmation(message):
        return "Understood. Please consult a healthcare professional if needed."

   # Inject RAG context into the existing runner's agent instruction
    # No new runner created — reuses existing one
   # Reuse the existing runner — no new API calls on initialization
    new_runner = _runner
    wait_between_calls()

    user_message = types.Content(
        role="user", parts=[types.Part(text=message)])
    response_text = ""
    tools_used = []
    start = time.time()

    for attempt in range(2):
        try:
            async for event in new_runner.run_async(
                user_id=USER_ID, session_id=SESSION_ID,
                new_message=user_message,
            ):
                if hasattr(event, 'content') and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            tools_used.append(part.function_call.name)
                if event.is_final_response():
                    if event.content and event.content.parts:
                        response_text = event.content.parts[0].text or ""
            break
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["429", "RESOURCE_EXHAUSTED", "ResourceExhausted"]):
                if attempt == 0:
                    print("  ⏳ Quota hit — waiting 65s...")
                    await asyncio.sleep(65)
                else:
                    return "⏳ Quota limit reached. Please wait a minute."
            else:
                return f"❌ Error: {err[:150]}"

    if not response_text:
        return "⏳ No response. Please try again."

    safety = check_output_safety(response_text)
    if not safety["is_safe"]:
        return (
            "I can't provide that information. "
            "Please consult a healthcare professional.\n\n"
            "⚠️ ClinAssist provides general health guidance only."
        )

    latency = round((time.time() - start) * 1000, 2)
    if tools_used:
        print(f"  [tools: {', '.join(set(tools_used))}]")
    print(f"  [latency: {latency}ms]")
    return response_text

async def main():
    await setup()
    print("\n🏥 ClinAssist v1.0 (Pydantic-validated | RAG-grounded | HITL-gated)")
    print("   Try: 'I have fever and headache for 2 days'")
    print("   Try: 'What is malaria?'")
    print("   Try: 'I have severe chest pain' (emergency test)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! Stay healthy.")
            break
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye! Stay healthy.")
            break
        if not user_input:
            continue
        response = await chat(user_input)
        print(f"\nClinAssist: {response}\n")

if __name__ == "__main__":
    asyncio.run(main())
