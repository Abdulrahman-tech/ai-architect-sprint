# agent.py — Day 8: ClinAssist v0.1
# Health triage agent with HITL confirmation and safety guardrails
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

APP_NAME   = "clinassist_app"
USER_ID    = "patient_user"
SESSION_ID = "day08_session"

# ── RATE LIMITER ──────────────────────────────────────────────────────────────
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

def assess_symptom_urgency(symptoms: str) -> dict:
    """Assesses the urgency level of reported symptoms.
    Use when the user describes physical symptoms or health complaints.
    DO NOT use for emergencies — those are handled before this tool.
    DO NOT diagnose. Only assess urgency level.
    Args:
        symptoms: Description of symptoms reported by the user
    """
    symptoms_lower = symptoms.lower()

    high_urgency = [
        "chest", "breath", "severe", "worst", "sudden",
        "numbness", "vision", "speech", "confusion", "faint",
        "blood", "swelling", "high fever", "39", "40", "41",
    ]
    medium_urgency = [
        "fever", "vomiting", "diarrhea", "pain", "ache",
        "dizzy", "nausea", "rash", "infection", "wound",
        "sprain", "burn", "cut",
    ]

    high_count = sum(1 for kw in high_urgency if kw in symptoms_lower)
    medium_count = sum(1 for kw in medium_urgency if kw in symptoms_lower)

    if high_count >= 2:
        urgency = "HIGH"
        action = "Seek medical attention within 1-2 hours or visit emergency room."
        timeframe = "1-2 hours"
    elif high_count == 1 or medium_count >= 2:
        urgency = "MEDIUM"
        action = "Schedule appointment with doctor today or tomorrow."
        timeframe = "24-48 hours"
    else:
        urgency = "LOW"
        action = "Monitor symptoms. Schedule routine appointment if symptoms persist."
        timeframe = "3-7 days"

    return {
        "symptoms_received": symptoms,
        "urgency_level": urgency,
        "recommended_action": action,
        "recommended_timeframe": timeframe,
        "disclaimer": "This is NOT a medical diagnosis. Always consult a healthcare professional.",
        "assessed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_general_health_info(topic: str) -> dict:
    """Provides general health education on a topic.
    Use for general health questions — NOT for diagnosing the user.
    Examples: 'what is diabetes', 'how does fever work', 'what causes headaches'.
    Args:
        topic: Health topic e.g. 'fever', 'headache', 'diabetes', 'dehydration'
    """
    health_info = {
        "fever": {
            "definition": "Temporary rise in body temperature, often the body fighting infection.",
            "normal_range": "36.1°C to 37.2°C (97°F to 99°F)",
            "when_to_worry": "Adults: above 39.4°C (103°F). Children: consult doctor.",
            "general_care": "Rest, stay hydrated, monitor temperature regularly.",
        },
        "headache": {
            "definition": "Pain or discomfort in the head or neck area.",
            "common_causes": "Stress, dehydration, lack of sleep, eye strain.",
            "when_to_worry": "Sudden severe headache, with fever/stiff neck, after head injury.",
            "general_care": "Rest, stay hydrated, reduce screen time.",
        },
        "dehydration": {
            "definition": "Body loses more fluids than it takes in.",
            "symptoms": "Thirst, dark urine, fatigue, dizziness, dry mouth.",
            "when_to_worry": "No urination for 8+ hours, extreme dizziness, rapid heartbeat.",
            "general_care": "Drink water, oral rehydration salts for severe cases.",
        },
        "diabetes": {
            "definition": "Condition affecting how the body processes blood sugar.",
            "types": "Type 1 (autoimmune), Type 2 (lifestyle/genetic), Gestational.",
            "common_symptoms": "Frequent urination, excessive thirst, fatigue, blurred vision.",
            "note": "Diagnosis requires medical testing. Cannot be self-diagnosed.",
        },
        "malaria": {
            "definition": "Parasitic infection spread through mosquito bites.",
            "common_symptoms": "Fever, chills, headache, muscle aches, fatigue.",
            "when_to_worry": "High fever, confusion, difficulty breathing, seek care immediately.",
            "general_care": "Seek medical testing. Do not self-medicate.",
        },
    }

    topic_lower = topic.lower()
    for key, info in health_info.items():
        if key in topic_lower:
            return {
                "topic": topic,
                "information": info,
                "disclaimer": "General health education only. Not medical advice.",
            }

    return {
        "topic": topic,
        "information": f"General info about '{topic}' not in database.",
        "suggestion": "Please consult a healthcare professional.",
        "disclaimer": "General health education only. Not medical advice.",
    }


# ── AGENT ─────────────────────────────────────────────────────────────────────
clinassist = LlmAgent(
    name="ClinAssist",
    model="gemini-2.0-flash",
    description="ClinAssist — health triage and general health education.",
    instruction="""You are ClinAssist, a health triage assistant.

    Your ONLY jobs:
    1. Assess urgency of symptoms using assess_symptom_urgency tool
    2. Provide general health education using get_general_health_info tool
    3. Direct users to appropriate care

    STRICT RULES — never break these:
    - NEVER diagnose any condition
    - NEVER tell a user they have any disease
    - NEVER recommend specific medications or dosages
    - ALWAYS recommend consulting a doctor
    - ALWAYS add disclaimer at end of every response

    Tool selection:
    - User describes symptoms → assess_symptom_urgency
    - User asks general health question → get_general_health_info

    Response format:
    1. Acknowledge what user shared
    2. Tool result clearly explained
    3. Recommended action
    4. Always end with:
       "⚠️ ClinAssist provides general health guidance only.
        Always consult a qualified healthcare professional."
    """,
    tools=[assess_symptom_urgency, get_general_health_info],
)

session_service = InMemorySessionService()
runner = Runner(agent=clinassist, app_name=APP_NAME, session_service=session_service)

async def setup():
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print(f"✅ Session ready: {session.id}")
    print("✅ Safety guardrails: ACTIVE")
    print("✅ HITL confirmation: ACTIVE")

# ── HITL CONFIRMATION GATE ────────────────────────────────────────────────────
def get_hitl_confirmation(user_input: str) -> bool:
    """User must confirm before agent responds — human in the loop."""
    print(f"\n  📋 HITL CHECK")
    print(f"  Message: '{user_input[:70]}'")
    print(f"  ClinAssist will provide general health guidance only.")
    confirm = input("  Proceed? (yes/no): ").strip().lower()
    return confirm in ["yes", "y"]

# ── CHAT WITH FULL SAFETY PIPELINE ────────────────────────────────────────────
async def chat(message: str) -> str:
    # 1. Sanitize
    message = sanitize_input(message)

    # 2. Emergency check — BEFORE anything else
    emergency = check_emergency(message)
    if emergency["is_emergency"]:
        return emergency["message"]

    # 3. HITL confirmation gate
    if not get_hitl_confirmation(message):
        return "Understood. Please consult a healthcare professional if needed."

    # 4. Rate limit
    wait_between_calls()

    user_message = types.Content(
        role="user", parts=[types.Part(text=message)])
    response_text = ""
    tools_used = []
    start = time.time()

    for attempt in range(2):
        try:
            async for event in runner.run_async(
                user_id=USER_ID, session_id=SESSION_ID,
                new_message=user_message,
            ):
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            tools_used.append(part.function_call.name)
                if event.is_final_response():
                    response_text = event.content.parts[0].text
            break
        except Exception as e:
            if "429" in str(e) and attempt == 0:
                print("  ⏳ Quota hit — waiting 60s...")
                await asyncio.sleep(60)
            else:
                return f"❌ Error: {str(e)[:150]}"

    # 5. Output safety check
    safety = check_output_safety(response_text)
    if not safety["is_safe"]:
        return (
            "I can't provide that specific information. "
            "Please consult a qualified healthcare professional directly.\n\n"
            "⚠️ ClinAssist provides general health guidance only. "
            "Always consult a qualified healthcare professional."
        )

    latency = round((time.time() - start) * 1000, 2)
    if tools_used:
        print(f"  [tools: {', '.join(set(tools_used))}]")
    print(f"  [latency: {latency}ms]")
    return response_text

# ── MAIN ──────────────────────────────────────────────────────────────────────
async def main():
    await setup()
    print("\n🏥 ClinAssist v0.1 running")
    print("   HITL confirmation required before every response")
    print("   Emergency detection active — no API call needed")
    print()
    print("   Try: 'I have a headache and mild fever for 2 days'")
    print("   Try: 'What is diabetes?'")
    print("   Try: 'I have severe chest pain' (tests emergency gate)\n")

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