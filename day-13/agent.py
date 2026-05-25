# agent.py — Day 13: DevOps AutoPilot v1.0 — Deployment & Security
import os
import asyncio
import time
import json
import hmac
import hashlib

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("\n❌ API key not set!\nRun: export GOOGLE_API_KEY='your_key_here'")
print(f"✅ API key loaded: {api_key[:8]}...")

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from ci_tools import MOCK_PIPELINES, get_pipeline_status, classify_failure
from pipeline_chain import route_failure, run_full_pipeline, get_notifications
from security import (
    check_prompt_injection, validate_pipeline_id,
    sanitize_log_output, verify_webhook_signature, check_rate_limit
)

APP_NAME   = "devops_app"
USER_ID    = "engineer"
SESSION_ID = "day13_session"
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "dev_secret_change_in_prod")

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


def secure_pipeline_fix(pipeline_id: str) -> dict:
    """Securely processes a pipeline fix request with full security checks.
    Validates input, runs full chain, sanitizes output.
    This is the ONLY LLM tool.
    Args:
        pipeline_id: Pipeline ID (validated before processing)
    """
    validation = validate_pipeline_id(pipeline_id)
    if not validation["is_valid"]:
        return {"error": validation["error"], "security_blocked": True}

    result = run_full_pipeline(pipeline_id)
    if "error" in result:
        return result
    if "message" in result:
        return result

    safe_log = sanitize_log_output(result.get("log_excerpt", ""))

    return {
        "pipeline_id": result["pipeline_id"],
        "repo": result["repo"],
        "branch": result["branch"],
        "failure_type": result["failure_type"],
        "severity": result["severity"],
        "team_notified": result["team"],
        "channel": result["channel"],
        "escalated": result["escalated"],
        "log_excerpt_sanitized": safe_log,
        "fix_documentation": result["fix_documentation"],
        "security_checks_passed": [
            "✅ Pipeline ID validated",
            "✅ Log output sanitized",
            "✅ No secrets in output",
        ],
        "chain_steps_completed": [
            "✅ Classified",
            "✅ Routed",
            "✅ Notified",
            "⏳ Generating fix...",
        ],
    }


agent = LlmAgent(
    name="DevOpsAutoPilot",
    model="gemini-2.0-flash",
    description="DevOps AutoPilot v1.0 — secure, production-ready.",
    instruction="""You are DevOps AutoPilot v1.0 — production-ready.

    Tool: secure_pipeline_fix(pipeline_id)

    Security checks run automatically before you respond.

    When tool returns data:
    1. Confirm security checks passed
    2. State pipeline, repo, branch, failure type, severity
    3. Confirm team notified and channel
    4. State if escalated
    5. Give 2-3 specific fix steps from fix_documentation
    6. Reference the sanitized log
    7. Be concise and production-focused""",
    tools=[secure_pipeline_fix],
)

session_service = InMemorySessionService()
_runner = None

async def setup():
    global _runner
    _runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print(f"✅ Session ready: {session.id}")
    print("✅ Prompt injection defence: ACTIVE")
    print("✅ Input validation: ACTIVE")
    print("✅ Log sanitization: ACTIVE")
    print("✅ Webhook authentication: ACTIVE")
    print("✅ Rate limiting: ACTIVE")


def cmd_status() -> str:
    result = get_pipeline_status()
    lines = [
        f"\n📊 PIPELINE STATUS — {result['as_of']}",
        f"Total: {result['total_pipelines']} | "
        f"Failed: {result['failed_count']} | "
        f"Success: {result['success_count']}",
    ]
    if result["failed_pipelines"]:
        lines.append("\n❌ FAILED:")
        for p in result["failed_pipelines"]:
            cl = classify_failure(p["id"])
            ftype = cl.get("failure_type", "unknown").upper()
            rt = route_failure(cl.get("failure_type", "unknown"))
            lines.append(
                f"  {p['id']} | {p['repo']} | {p['branch']} | "
                f"{ftype} | {rt['severity']}"
            )
    lines.append("\nType 'fix <pipeline_id>' for secure fix (1 API call)")
    return "\n".join(lines)


def cmd_webhook_test() -> str:
    payload = json.dumps({
        "pipeline_id": "pipeline_003",
        "repo": "api-service",
        "status": "failed",
        "branch": "main",
    })
    signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    rate_check = check_rate_limit("10.0.0.1")
    if not rate_check["allowed"]:
        return f"🚫 Rate limited: {rate_check['error']}"
    sig_check = verify_webhook_signature(payload, signature, WEBHOOK_SECRET)
    if not sig_check["is_valid"]:
        return f"🚫 Invalid signature: {sig_check['error']}"
    data = json.loads(payload)
    return (
        f"✅ WEBHOOK RECEIVED & VERIFIED\n"
        f"Pipeline: {data['pipeline_id']}\n"
        f"Repo: {data['repo']} | Branch: {data['branch']}\n"
        f"Status: {data['status']}\n"
        f"Rate limit: {rate_check['requests_used']}/10 used\n"
        f"→ Type 'fix {data['pipeline_id']}' to process"
    )


def cmd_sanitize_test() -> str:
    test_log = (
        "Deploy started...\n"
        "api_key=sk-prod-abc123secretkey\n"
        "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9\n"
        "password=super_secret_prod_password\n"
        "AKIAIOSFODNN7EXAMPLE\n"
        "Deploy complete!"
    )
    sanitized = sanitize_log_output(test_log)
    return f"🔐 LOG SANITIZATION\n\nBEFORE:\n{test_log}\n\nAFTER:\n{sanitized}"


def cmd_security_test(user_input: str) -> str:
    result = check_prompt_injection(user_input)
    if not result["is_safe"]:
        return (
            f"🚨 INJECTION DETECTED\n"
            f"Threat: {result['threat_type']}\n"
            f"Patterns: {len(result['matched_patterns'])} matched"
        )
    return f"✅ Input safe: '{user_input[:50]}'"


async def cmd_fix(pipeline_id: str) -> str:
    injection_check = check_prompt_injection(pipeline_id)
    if not injection_check["is_safe"]:
        return "🚨 Security: Input blocked — injection detected."
    validation = validate_pipeline_id(pipeline_id)
    if not validation["is_valid"]:
        return f"❌ Security: {validation['error']}"

    print(f"\n  🔒 Security checks passed")
    print(f"  ⛓️  Running chain...")
    wait_between_calls()

    message = f"Securely fix pipeline {pipeline_id}"
    user_message = types.Content(
        role="user", parts=[types.Part(text=message)])
    response_text = ""

    for attempt in range(2):
        try:
            async for event in _runner.run_async(
                user_id=USER_ID, session_id=SESSION_ID,
                new_message=user_message,
            ):
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
                    return "⏳ Quota limit reached. Wait a minute."
            else:
                return f"❌ Error: {err[:150]}"

    return response_text or "⏳ No response received."


async def main():
    await setup()
    print("\n⚙️  DevOps AutoPilot v1.0 — Production Ready")
    print("   'status'          — pipeline overview (0 API calls)")
    print("   'webhook'         — simulate webhook (0 API calls)")
    print("   'sanitize'        — test log sanitization (0 API calls)")
    print("   'security <text>' — test injection detection (0 API calls)")
    print("   'fix <id>'        — secure fix (1 API call)")
    print("   'quit'            — exit\n")
    print("   IDs: pipeline_001, pipeline_002, pipeline_003\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        if user_input.lower() == "status":
            print(cmd_status())
        elif user_input.lower() == "webhook":
            print(cmd_webhook_test())
        elif user_input.lower() == "sanitize":
            print(cmd_sanitize_test())
        elif user_input.lower().startswith("security "):
            print(cmd_security_test(user_input[9:]))
        elif user_input.lower().startswith("fix"):
            parts = user_input.split()
            if len(parts) < 2:
                print("Usage: fix <pipeline_id>")
            else:
                response = await cmd_fix(parts[1])
                print(f"\n🔧 AutoPilot v1.0:\n{response}\n")
        else:
            print("Commands: 'status', 'webhook', 'sanitize', 'security <text>', 'fix <id>'")


if __name__ == "__main__":
    asyncio.run(main())