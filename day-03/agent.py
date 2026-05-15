# agent.py — Day 3: Memory & State Management
import os
import asyncio

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("\n❌ API key not set!\nRun: export GOOGLE_API_KEY='your_key_here'")
print(f"✅ API key loaded: {api_key[:8]}...")

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from tools import calculate, convert_currency, get_world_time, convert_units
from rate_limiter import check_and_wait
from memory import load_memory, save_memory, add_tool_call, get_history_summary

APP_NAME   = "memory_agent_app"
USER_ID    = "sprint_user"
SESSION_ID = "day03_session"

# ── LOAD MEMORY FROM DISK ─────────────────────────────────────────────────────
memory_state = load_memory()
memory_state["session_count"] += 1
print(f"✅ Memory ready — session #{memory_state['session_count']}")


def build_agent() -> LlmAgent:
    """Build agent with memory injected into system prompt."""
    history_context = get_history_summary(memory_state)
    return LlmAgent(
        name="MemoryAgent",
        model="gemini-2.5-flash",
        description="A stateful assistant that remembers past tool calls.",
        instruction=f"""You are a practical, stateful assistant with four tools:
        a calculator, a currency converter, a world clock, and a unit converter.

        You have memory of past interactions:
        {history_context}

        Rules:
        - ALWAYS use the calculator tool for any math.
        - ALWAYS use the currency tool for any money conversion.
        - ALWAYS use the world clock tool for time questions.
        - ALWAYS use the unit converter for measurement conversions.
        - If the user asks 'what did I ask before?' or 'recall my history',
          summarise the tool history shown above clearly.
        - After each tool call, explain the result in one clear sentence.
        - If a tool returns an error, tell the user what went wrong.""",
        tools=[calculate, convert_currency, get_world_time, convert_units],
    )


session_service = InMemorySessionService()

async def setup():
    agent = build_agent()
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    print(f"✅ Session created: {session.id}")
    return runner


async def chat_async(runner, message: str) -> str:
    try:
        check_and_wait()
    except RuntimeError as e:
        return str(e)

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=message)]
    )
    response_text = ""
    tools_used = []

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=user_message,
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    tools_used.append(part.function_call.name)
        if event.is_final_response():
            response_text = event.content.parts[0].text

    for tool in tools_used:
        add_tool_call(memory_state, tool, message, response_text[:120])

    if tools_used:
        print(f"  [tools called: {', '.join(tools_used)}]")

    save_memory(memory_state)
    return response_text


async def main():
    runner = await setup()

    if memory_state["last_seen"]:
        print(f"👋 Welcome back! Last seen: {memory_state['last_seen'][:19]}")
    else:
        print("👋 First session! I will remember everything you ask.")

    print("\n🧠 MemoryAgent running (gemini-2.5-flash | rate-limited)")
    print("   I remember your past tool calls even after restart!")
    print("   Try: 'what did I ask before?'")
    print("   Try: 'How many miles is 755 km?'")
    print("   Try: quit → restart → 'what did I ask before?'\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            save_memory(memory_state)
            print("\n💾 Memory saved. Goodbye!")
            break

        if user_input.lower() in ["quit", "exit", "q"]:
            save_memory(memory_state)
            print("💾 Memory saved. Goodbye!")
            break
        if not user_input:
            continue

        try:
            response = await chat_async(runner, user_input)
            print(f"Agent: {response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())