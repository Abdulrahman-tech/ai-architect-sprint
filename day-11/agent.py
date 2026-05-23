# agent.py — Day 11: DevOps AutoPilot v0.1
# QUOTA-EFFICIENT: 90% pure Python, LLM called ONCE only for fix suggestions

import os
import asyncio
import time

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("\n❌ API key not set!\nRun: export GOOGLE_API_KEY='your_key_here'")
print(f"✅ API key loaded: {api_key[:8]}...")

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from ci_tools import (
    get_pipeline_status, classify_failure,
    get_fix_context, MOCK_PIPELINES
)

APP_NAME   = "devops_app"
USER_ID    = "engineer"
SESSION_ID = "day11_session"

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

# ── ONLY TOOL: used for LLM-needed operation ──────────────────────────────────

def suggest_fix(pipeline_id: str) -> dict:
    """Generates fix suggestion data for a failed pipeline.
    Combines classification and fix documentation for the LLM to use.
    This is the ONLY tool — all other operations are pure Python commands.
    Args:
        pipeline_id: Pipeline ID to generate fix for
    """
    classification = classify_failure(pipeline_id)
    if "error" in classification:
        return classification

    if classification.get("failure_type") is None:
        return {"message": f"Pipeline {pipeline_id} succeeded — no fix needed."}

    fix_context = get_fix_context(classification["failure_type"])

    return {
        "pipeline_id": pipeline_id,
        "repo": classification["repo"],
        "branch": classification["branch"],
        "failure_type": classification["failure_type"],
        "confidence": classification["confidence"],
        "log_excerpt": classification["log_excerpt"],
        "fix_documentation": fix_context["fix_documentation"],
        "ready_for_fix_generation": True,
    }


# ── AGENT — single runner, created once ───────────────────────────────────────
agent = LlmAgent(
    name="DevOpsAutoPilot",
    model="gemini-2.0-flash",
    description="DevOps AutoPilot — CI/CD fix suggestion agent.",
    instruction="""You are DevOps AutoPilot, a CI/CD assistant.

    You have ONE tool: suggest_fix(pipeline_id)

    When suggest_fix returns data:
    1. State pipeline ID, repo, and branch clearly
    2. State the failure type
    3. Give 2-3 specific actionable fix steps from fix_documentation
    4. Reference the log excerpt to explain why this fix applies
    5. Be concise — engineers are busy

    Always be direct and technical.""",
    tools=[suggest_fix],
)

session_service = InMemorySessionService()
_runner = None

async def setup():
    global _runner
    _runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print(f"✅ Session ready: {session.id}")
    print(f"✅ Monitoring {len(MOCK_PIPELINES)} pipelines")
    print("✅ Pure Python monitoring: ACTIVE (0 API calls)")
    print("✅ LLM fix suggestions: ACTIVE (1 API call per fix)")

# ── PURE PYTHON COMMANDS — 0 API calls ────────────────────────────────────────

def cmd_status(repo: str = "") -> str:
    result = get_pipeline_status(repo)
    lines = [
        f"\n📊 PIPELINE STATUS — {result['as_of']}",
        f"Total: {result['total_pipelines']} | "
        f"Failed: {result['failed_count']} | "
        f"Success: {result['success_count']}",
    ]
    if result["failed_pipelines"]:
        lines.append("\n❌ FAILED PIPELINES:")
        for p in result["failed_pipelines"]:
            lines.append(
                f"  {p['id']} | {p['repo']} | "
                f"branch: {p['branch']}"
            )
    else:
        lines.append("✅ All pipelines passing!")
    lines.append("\nType 'classify <pipeline_id>' to analyse a failure")
    return "\n".join(lines)


def cmd_classify(pipeline_id: str) -> str:
    result = classify_failure(pipeline_id)
    if "error" in result:
        return f"❌ {result['error']}"
    if result.get("failure_type") is None:
        return f"✅ Pipeline {pipeline_id} succeeded."

    lines = [
        f"\n🔍 FAILURE ANALYSIS: {pipeline_id}",
        f"Repo: {result['repo']} | Branch: {result['branch']}",
        f"Job: {result['job_name']}",
        f"Failure type: {result['failure_type'].upper()}",
        f"Confidence: {result['confidence']}",
        f"Patterns matched: {', '.join(result['matched_patterns'])}",
        f"\nLog excerpt:",
        f"  {result['log_excerpt'][:200]}",
        f"\nType 'fix {pipeline_id}' for AI fix suggestions (1 API call)",
    ]
    return "\n".join(lines)


# ── LLM COMMAND — 1 API call ──────────────────────────────────────────────────

async def cmd_fix(pipeline_id: str) -> str:
    print(f"  🤖 Generating fix for {pipeline_id} (1 API call)...")
    wait_between_calls()

    message = f"Generate a specific fix suggestion for pipeline {pipeline_id}"
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
                    return "⏳ Quota limit reached. Wait a minute then try again."
            else:
                return f"❌ Error: {err[:150]}"

    return response_text or "⏳ No response received."


# ── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    await setup()
    print("\n⚙️  DevOps AutoPilot v0.1")
    print("   'status'                — show all pipelines (0 API calls)")
    print("   'classify pipeline_001' — analyse failure (0 API calls)")
    print("   'fix pipeline_001'      — AI fix suggestion (1 API call)")
    print("   'quit'                  — exit\n")

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

        if user_input.lower().startswith("status"):
            parts = user_input.split()
            repo = parts[1] if len(parts) > 1 else ""
            print(cmd_status(repo))

        elif user_input.lower().startswith("classify"):
            parts = user_input.split()
            if len(parts) < 2:
                print("Usage: classify <pipeline_id>")
            else:
                print(cmd_classify(parts[1]))

        elif user_input.lower().startswith("fix"):
            parts = user_input.split()
            if len(parts) < 2:
                print("Usage: fix <pipeline_id>")
            else:
                response = await cmd_fix(parts[1])
                print(f"\n🔧 Fix suggestion:\n{response}\n")

        else:
            print("Commands: 'status', 'classify <id>', 'fix <id>', 'quit'")


if __name__ == "__main__":
    asyncio.run(main())