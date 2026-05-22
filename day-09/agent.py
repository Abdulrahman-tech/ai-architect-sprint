# agent.py — Day 9: ClinAssist v0.2 — RAG Pipeline
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

APP_NAME   = "clinassist_app"
USER_ID    = "patient_user"
SESSION_ID = "day09_session"

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

def assess_with_evidence(symptoms: str) -> dict:
    """Assesses symptom urgency AND retrieves supporting medical evidence.
    Use when user describes symptoms — provides urgency assessment
    grounded in WHO/NHS sources.
    Args:
        symptoms: Description of symptoms reported by the user
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
        urgency, action = "HIGH", "Seek medical attention within 1-2 hours."
    elif high_count == 1 or medium_count >= 2:
        urgency, action = "MEDIUM", "Schedule appointment with doctor today or tomorrow."
    else:
        urgency, action = "LOW", "Monitor symptoms. Schedule routine appointment if symptoms persist."

    return {
        "symptoms": symptoms,
        "urgency_level": urgency,
        "recommended_action": action,
        "evidence": [
            {
                "source": doc["source"],
                "title": doc["title"],
                "excerpt": doc["content"][:200] + "...",
                "relevance": doc["relevance_score"],
            }
            for doc in retrieved
        ],
        "disclaimer": "NOT a medical diagnosis. Always consult a healthcare professional.",
        "assessed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def search_medical_knowledge(query: str) -> dict:
    """Searches medical knowledge base for information on a health topic.
    Use for general health questions. Returns WHO/NHS grounded information.
    Args:
        query: Health topic e.g. 'what is malaria', 'diabetes symptoms'
    """
    retrieved = retrieve(query, top_k=2)

    if not retrieved or retrieved[0]["relevance_score"] == 0:
        return {
            "query": query,
            "found": False,
            "message": f"No specific information found for '{query}'.",
            "suggestion": "Please consult a healthcare professional.",
            "disclaimer": "General health education only. Not medical advice.",
        }

    return {
        "query": query,
        "found": True,
        "results": [
            {
                "source": doc["source"],
                "title": doc["title"],
                "content": doc["content"],
                "relevance_score": doc["relevance_score"],
            }
            for doc in retrieved
        ],
        "disclaimer": "General health education only. Not medical advice.",
    }


def build_agent(user_query: str = "") -> LlmAgent:
    rag_context = ""
    if user_query:
        retrieved = retrieve(user_query, top_k=2)
        rag_context = format_context(retrieved)

    return LlmAgent(
        name="ClinAssist",
        model="gemini-2.0-flash",
        description="ClinAssist v0.2 — RAG-powered health triage.",
        instruction=f"""You are ClinAssist, a health triage assistant
        with access to a medical knowledge base.

        PRE-RETRIEVED CONTEXT:
        {rag_context if rag_context else "No context retrieved yet."}

        Jobs:
        1. Assess symptom urgency → assess_with_evidence tool
        2. Answer health questions → search_medical_knowledge tool
        3. Always cite sources (WHO, NHS)

        STRICT RULES:
        - NEVER diagnose any condition
        - NEVER recommend specific medications
        - ALWAYS cite evidence sources
        - ALWAYS recommend consulting a doctor
        - ALWAYS end with disclaimer

        Response format:
        1. Acknowledge the query
        2. Assessment or information with evidence cited
        3. Recommended action
        4. Sources used
        5. "⚠️ ClinAssist provides general health guidance only.
            Always consult a qualified healthcare professional."
        """,
        tools=[assess_with_evidence, search_medical_knowledge],
    )


session_service = InMemorySessionService()

async def setup():
    agent = build_agent()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print(f"✅ Session ready: {session.id}")
    print(f"✅ RAG pipeline: {len(MEDICAL_KNOWLEDGE)} documents indexed")
    print("✅ Safety guardrails: ACTIVE")
    return runner

def get_hitl_confirmation(user_input: str) -> bool:
    print(f"\n  📋 HITL CHECK")
    print(f"  Message: '{user_input[:70]}'")
    confirm = input("  Proceed? (yes/no): ").strip().lower()
    return confirm in ["yes", "y"]

async def chat(message: str) -> str:
    message = sanitize_input(message)

    emergency = check_emergency(message)
    if emergency["is_emergency"]:
        return emergency["message"]

    if not get_hitl_confirmation(message):
        return "Understood. Please consult a healthcare professional if needed."

    new_agent = build_agent(message)
    new_runner = Runner(
        agent=new_agent, app_name=APP_NAME, session_service=session_service)

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
                # Fix: safely check parts exist before accessing
                if hasattr(event, 'content') and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            tools_used.append(part.function_call.name)
                if event.is_final_response():
                    # Fix: safely get response text
                    if event.content and event.content.parts:
                        response_text = event.content.parts[0].text or ""
            break
        except Exception as e:
            err = str(e)
            # Fix: catch all quota-related errors including new ADK format
            if any(x in err for x in ["429", "RESOURCE_EXHAUSTED", "ResourceExhausted"]):
                if attempt == 0:
                    print("  ⏳ Quota hit — waiting 65s then retrying...")
                    await asyncio.sleep(65)
                else:
                    return "⏳ Quota limit reached. Please wait a minute and try again."
            else:
                return f"❌ Error: {err[:150]}"

    if not response_text:
        return "⏳ No response received. Please try again in a moment."

    safety = check_output_safety(response_text)
    if not safety["is_safe"]:
        return (
            "I can't provide that specific information. "
            "Please consult a qualified healthcare professional.\n\n"
            "⚠️ ClinAssist provides general health guidance only."
        )

    latency = round((time.time() - start) * 1000, 2)
    if tools_used:
        print(f"  [tools: {', '.join(set(tools_used))}]")
    print(f"  [latency: {latency}ms]")
    return response_text

async def main():
    await setup()
    print("\n🏥 ClinAssist v0.2 running (RAG-powered)")
    print("   Every response grounded in WHO/NHS evidence")
    print("   Sources cited automatically")
    print()
    print("   Try: 'I have fever and headache for 2 days'")
    print("   Try: 'What is malaria?'")
    print("   Try: 'Tell me about dehydration'")
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