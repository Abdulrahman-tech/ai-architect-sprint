# agent.py — Day 4: FinSight v0.1 Multi-Agent Orchestration
import os
import asyncio

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("\n❌ API key not set!\nRun: export GOOGLE_API_KEY='your_key_here'")
print(f"✅ API key loaded: {api_key[:8]}...")

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from finance_tools import get_stock_data, get_multiple_stocks, calculate_portfolio_value
from rate_limiter import check_and_wait

APP_NAME   = "finsight_app"
USER_ID    = "sprint_user"
SESSION_ID = "day04_session"

# ── SUB-AGENT: DATA FETCHER ───────────────────────────────────────────────────
# Only job: fetch financial data using tools
data_fetcher = LlmAgent(
    name="DataFetcher",
    model="gemini-2.5-flash",
    description="""Fetches real-time financial market data.
    Call this agent when you need current stock prices, company info,
    or portfolio valuations. Provide the stock symbols clearly.""",
    instruction="""You are a financial data specialist. Your only job is
    to fetch accurate market data using your tools and return it clearly.

    Rules:
    - ALWAYS use get_stock_data for single stock queries.
    - ALWAYS use get_multiple_stocks when comparing 2 or more stocks.
    - ALWAYS use calculate_portfolio_value when given holdings with share counts.
    - Return the raw data clearly — do not add opinions or analysis.
    - If a symbol is not found, say so clearly.
    - Never invent or guess prices.""",
    tools=[get_stock_data, get_multiple_stocks, calculate_portfolio_value],
)

# ── ORCHESTRATOR AGENT ────────────────────────────────────────────────────────
# Receives user queries, delegates to DataFetcher, then analyses results
orchestrator = LlmAgent(
    name="FinSightOrchestrator",
    model="gemini-2.5-flash",
    description="FinSight financial analysis orchestrator.",
    instruction="""You are FinSight, a financial analysis assistant.
    You help users understand stocks, portfolios, and market data.

    You have a DataFetcher sub-agent that retrieves live market data.

    How to work:
    - When the user asks about a stock or portfolio, delegate to DataFetcher.
    - Once you receive data back, analyse it and give a clear, helpful response.
    - Always mention the stock symbol and company name in your response.
    - Format numbers clearly: use $ for prices, commas for large numbers.
    - Add brief context: is the stock up or down today?
    - Always end with this disclaimer:
      "⚠️ This is not financial advice. Always do your own research."

    What you do NOT do:
    - Never make up stock prices.
    - Never give buy/sell recommendations.
    - Never predict future prices.""",
    tools=[AgentTool(agent=data_fetcher)],
)

# ── SESSION & RUNNER ───────────────────────────────────────────────────────────
session_service = InMemorySessionService()
runner = Runner(
    agent=orchestrator,
    app_name=APP_NAME,
    session_service=session_service,
)

async def setup():
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    print(f"✅ Session created: {session.id}")
    print("✅ Multi-agent system ready:")
    print("   FinSightOrchestrator → DataFetcher")

async def chat_async(message: str) -> str:
    try:
        check_and_wait()
    except RuntimeError as e:
        return str(e)

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=message)]
    )
    response_text = ""
    agents_called = []
    tools_called = []

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=user_message,
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    name = part.function_call.name
                    if name == "DataFetcher":
                        agents_called.append(name)
                    else:
                        tools_called.append(name)
        if event.is_final_response():
            response_text = event.content.parts[0].text

    if agents_called:
        print(f"  [sub-agents called: {', '.join(agents_called)}]")
    if tools_called:
        print(f"  [tools called: {', '.join(tools_called)}]")

    return response_text

async def main():
    await setup()
    print("\n💰 FinSight v0.1 running (multi-agent | rate-limited)")
    print("   Try: 'What is Apple's current stock price?'")
    print("   Try: 'Compare AAPL and MSFT'")
    print("   Try: 'I have 10 AAPL and 5 MSFT, what is my portfolio worth?'")
    print("   Try: 'Tell me about Tesla stock'\n")

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
            print(f"FinSight: {response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())