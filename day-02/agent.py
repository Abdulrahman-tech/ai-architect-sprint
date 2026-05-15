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

APP_NAME   = "tool_agent_app"
USER_ID    = "sprint_user"
SESSION_ID = "day02_session"

tool_agent = LlmAgent(
    name="ToolAgent",
    model="gemini-2.5-flash",
    description="A practical assistant with math, currency, time, and unit tools.",
    instruction="""You are a practical, precise assistant with four tools:
    a calculator, a currency converter, a world clock, and a unit converter.
    - ALWAYS use the calculator tool for any math — never compute in your head.
    - ALWAYS use the currency tool for any money conversion — never guess rates.
    - ALWAYS use the world clock tool for time questions — never guess the time.
    - ALWAYS use the unit converter for measurement conversions.
    - If asked something outside these tools, say so honestly.
    - After using a tool, explain the result in one clear sentence.
    - If a tool returns an error key, tell the user what went wrong.""",
    tools=[calculate, convert_currency, get_world_time, convert_units],
)

session_service = InMemorySessionService()
runner = Runner(agent=tool_agent, app_name=APP_NAME, session_service=session_service)

async def setup():
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print(f"✅ Session created: {session.id}")

async def chat_async(message: str) -> str:
    try:
        check_and_wait()
    except RuntimeError as e:
        return str(e)

    user_message = types.Content(role="user", parts=[types.Part(text=message)])
    response_text = ""
    tools_used = []

    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=user_message):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    tools_used.append(part.function_call.name)
        if event.is_final_response():
            response_text = event.content.parts[0].text

    if tools_used:
        print(f"  [tools called: {', '.join(tools_used)}]")
    return response_text

async def main():
    await setup()
    print("\n🔧 ToolAgent running (gemini-2.5-flash | rate-limited)")
    print("   'How many miles is 755 km?'")
    print("   'What is sqrt(256) + 15% of 400?'")
    print("   'Convert 50000 NGN to USD'")
    print("   'What time is it in Tokyo right now?'\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        if not user_input:
            continue
        try:
            response = await chat_async(user_input)
            print(f"Agent: {response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())