# safety.py — Day 8: Safety guardrails for ClinAssist
import re

EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "can't breathe", "cannot breathe",
    "difficulty breathing", "stroke", "unconscious", "not breathing",
    "severe bleeding", "overdose", "suicide", "kill myself",
    "want to die", "poisoning", "seizure", "paralysis",
]

FORBIDDEN_OUTPUTS = [
    "you have", "you are diagnosed", "diagnosis is",
    "you definitely", "i can confirm", "prescribed",
    "take this medication", "dosage is",
]


def check_emergency(text: str) -> dict:
    """Check if input contains emergency keywords."""
    text_lower = text.lower()
    triggered = [kw for kw in EMERGENCY_KEYWORDS if kw in text_lower]
    if triggered:
        return {
            "is_emergency": True,
            "triggered_keywords": triggered,
            "message": (
                "🚨 EMERGENCY DETECTED\n"
                "Please call emergency services immediately:\n"
                "Nigeria: 112 or 199\n"
                "This agent cannot handle medical emergencies."
            ),
        }
    return {"is_emergency": False}


def check_output_safety(response: str) -> dict:
    """Check agent output for forbidden diagnostic language."""
    response_lower = response.lower()
    violations = [f for f in FORBIDDEN_OUTPUTS if f in response_lower]
    if violations:
        return {
            "is_safe": False,
            "violations": violations,
            "message": "Response contains diagnostic language that is not allowed.",
        }
    return {"is_safe": True}


def sanitize_input(text: str) -> str:
    """Clean and trim user input."""
    text = re.sub(r'(.)\1{10,}', r'\1\1\1', text)
    if len(text) > 1000:
        text = text[:1000] + "... [truncated]"
    return text.strip()