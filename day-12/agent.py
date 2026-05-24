# agent.py — Day 12: DevOps AutoPilot v0.2 — Tool chaining & conditional routing
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
from ci_tools import MOCK_PIPELINES, get_pipeline_status, classify_failure
from pipeline_chain import (
    route_failure, notify_team, run_full_pipeline, get_notifications
)

APP_NAME   = "devops_app"
USER_ID    = "engineer"
SESSION_ID = "day12_session"

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


def generate_fix_and_notify(pipeline_id: str) -> dict:
    """Runs full chain AND prepares fix data for LLM.
    Chain: classify → route → notify → return fix context.
    This is the ONLY tool — all chaining done in Python.
    Args:
        pipeline_id: Pipeline ID to process fully
    """
    result = run_full_pipeline(pipeline_id)

    if "error" in result:
        return result
    if "message" in result:
        return result

    return {
        "pipeline_id": result["pipeline_id"],
        "repo": result["repo"],
        "branch": result["branch"],
        "failure_type": result["failure_type"],
        "severity": result["severity"],
        "team_notified": result["team"],
        "channel": result["channel"],
        "escalated": result["escalated"],
        "notification_id": result["notification_id"],
        "log_excerpt": result["log_excerpt"],
        "fix_documentation": result["fix_documentation"],
        "chain_steps_completed": [
            "✅ Failure classified",
            "✅ Severity determined",
            f"✅ Routed to {result['team']} via {result['channel']}",
            "✅ Notification sent",
            "⏳ Generating fix suggestion...",
        ],
    }


agent = LlmAgent(
    name="DevOpsAutoPilot",
    model="gemini-2.0-flash",
    description="DevOps AutoPilot v0.2 — full pipeline chain.",
    instruction="""You are DevOps AutoPilot v0.2.

    You have ONE tool: generate_fix_and_notify(pipeline_id)

    This tool runs the full chain automatically before you respond:
    classify → route → notify → returns data for your fix

    When tool returns data:
    1. Confirm the chain steps completed
    2. State: pipeline, repo, branch, failure type, severity
    3. State: team notified and channel
    4. State if escalated (critical severity)
    5. Give 2-3 specific actionable fix steps from fix_documentation
    6. Reference the log excerpt
    7. Be concise — engineers are busy""",
    tools=[generate_fix_and_notify],
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
    print("✅ Tool chaining: ACTIVE (pure Python)")
    print("✅ Conditional routing: ACTIVE (pure Python)")
    print("✅ LLM fix generation: ACTIVE (1 API call per pipeline)")


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
    lines.append("\nType 'run <pipeline_id>' for full chain + fix")
    return "\n".join(lines)


def cmd_route(failure_type: str) -> str:
    result = route_failure(failure_type)
    return (
        f"\n🔀 ROUTING: {failure_type.upper()}\n"
        f"Severity: {result['severity']}\n"
        f"Team: {result['assigned_team']}\n"
        f"Channel: {result['notification_channel']}\n"
        f"Escalate: {'Yes 🚨' if result['escalate'] else 'No'}\n"
        f"Decision: {result['routing_decision']}"
    )


def cmd_notifications() -> str:
    notifs = get_notifications()
    if not notifs:
        return "No notifications sent yet."
    lines = [f"\n📬 NOTIFICATIONS ({len(notifs)} total):"]
    for n in notifs[-5:]:
        sent_at = n.get("sent_at", "unknown")[:19]
        channel = n.get("channel", "#unknown")
        title = n.get("message", {}).get("title", "notification")[:50]
        escalated = n.get("escalated", False)
        lines.append(
            f"  [{sent_at}] {channel} — {title}"
            + (" 🚨 ESCALATED" if escalated else "")
        )
    return "\n".join(lines)


async def cmd_run(pipeline_id: str) -> str:
    print(f"\n  ⛓️  Running full chain for {pipeline_id}...")
    print("  Step 1: Classify failure... (Python)")
    print("  Step 2: Determine routing... (Python)")
    print("  Step 3: Send notification... (Python)")
    print("  Step 4: Generate fix... (1 API call)")

    wait_between_calls()

    message = f"Run full pipeline chain for {pipeline_id} and generate fix"
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
    print("\n⚙️  DevOps AutoPilot v0.2 (full chain)")
    print("   'status'           — pipelines with routing (0 API calls)")
    print("   'route <type>'     — routing for failure type (0 API calls)")
    print("   'notifications'    — sent notifications (0 API calls)")
    print("   'run <id>'         — full chain + fix (1 API call)")
    print("   'quit'             — exit\n")
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
        elif user_input.lower() == "notifications":
            print(cmd_notifications())
        elif user_input.lower().startswith("route"):
            parts = user_input.split()
            if len(parts) < 2:
                print("Types: docker_auth, test_failure, dependency_conflict")
            else:
                print(cmd_route(parts[1]))
        elif user_input.lower().startswith("run"):
            parts = user_input.split()
            if len(parts) < 2:
                print("Usage: run <pipeline_id>")
            else:
                response = await cmd_run(parts[1])
                print(f"\n🔧 AutoPilot:\n{response}\n")
        else:
            print("Commands: 'status', 'route <type>', 'notifications', 'run <id>', 'quit'")


if __name__ == "__main__":
    asyncio.run(main())