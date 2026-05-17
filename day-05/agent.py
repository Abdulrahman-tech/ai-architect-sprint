# agent.py — Day 5: FinSight v0.2 (ReAct reasoning | quota-efficient)
# Single agent with all tools — 1-2 API calls per query instead of 8
import os
import asyncio
import json
from datetime import datetime

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("\n❌ API key not set!\nRun: export GOOGLE_API_KEY='your_key_here'")
print(f"✅ API key loaded: {api_key[:8]}...")

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from rate_limiter import check_and_wait

APP_NAME   = "finsight_app"
USER_ID    = "sprint_user"
SESSION_ID = "day05_session"

# ── TOOL 1: SINGLE STOCK ──────────────────────────────────────────────────────
def get_stock_data(symbol: str) -> dict:
    """Fetches current stock price and info for a ticker symbol.
    Use for single stock price queries.
    Args:
        symbol: Stock ticker e.g. 'AAPL', 'MSFT', 'TSLA', 'GOOGL'
    """
    try:
        import yfinance as yf
        info = yf.Ticker(symbol.upper()).info
        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        prev = info.get("previousClose", 0)
        change = round(price - prev, 2) if prev else 0
        change_pct = round((change / prev) * 100, 2) if prev else 0
        return {
            "symbol": symbol.upper(),
            "company_name": info.get("longName", "Unknown"),
            "current_price": price,
            "currency": info.get("currency", "USD"),
            "price_change": change,
            "price_change_pct": f"{change_pct}%",
            "market_cap": info.get("marketCap", "N/A"),
            "sector": info.get("sector", "N/A"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", "N/A"),
        }
    except Exception as e:
        return {"error": f"Could not fetch '{symbol}': {str(e)}"}


# ── TOOL 2: PORTFOLIO + RISK IN ONE CALL ─────────────────────────────────────
def get_portfolio_with_risk(holdings_json: str) -> dict:
    """Fetches stock prices AND calculates risk for a portfolio in one shot.
    Use this when user gives share counts and wants portfolio value + risk.
    This tool does the full ReAct loop internally:
    THINK (what stocks?) → ACT (fetch prices) → OBSERVE (values) →
    THINK (what's the risk?) → ACT (calculate HHI) → OBSERVE (risk level) →
    THINK (what to recommend?) → ACT (generate report)
    Args:
        holdings_json: JSON string e.g. '{"AAPL": 10, "MSFT": 5}'
                       keys = ticker symbols, values = number of shares
    """
    try:
        import yfinance as yf
        holdings = json.loads(holdings_json)
        positions = {}
        total_value = 0.0
        dollar_values = {}

        # STEP 1: fetch all prices
        for symbol, shares in holdings.items():
            try:
                info = yf.Ticker(symbol.upper()).info
                price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                position_value = round(price * shares, 2)
                total_value += position_value
                positions[symbol.upper()] = {
                    "shares": shares,
                    "price": price,
                    "position_value": position_value,
                    "company": info.get("longName", symbol),
                }
                dollar_values[symbol.upper()] = position_value
            except Exception as e:
                positions[symbol.upper()] = {"error": str(e), "shares": shares}

        if total_value == 0:
            return {"error": "Could not fetch any stock prices."}

        # STEP 2: concentration risk using HHI score
        concentrations = {}
        for sym, val in dollar_values.items():
            pct = round((val / total_value) * 100, 2)
            concentrations[sym] = {
                "percentage": pct,
                "risk_flag": pct > 40,
            }

        hhi = round(
            sum((v / total_value * 100) ** 2 for v in dollar_values.values()), 2
        )

        # STEP 3: risk level and recommendation
        if hhi > 5000:
            overall_risk = "HIGH"
            recommendation = (
                "Portfolio is heavily concentrated. "
                "Consider spreading across more stocks and sectors."
            )
        elif hhi > 2500:
            overall_risk = "MEDIUM"
            recommendation = (
                "Moderate concentration. "
                "Consider adding 2-3 more stocks from different sectors."
            )
        else:
            overall_risk = "LOW"
            recommendation = (
                "Portfolio is well diversified. "
                "Keep monitoring regularly."
            )

        return {
            "positions": positions,
            "total_portfolio_value": round(total_value, 2),
            "currency": "USD",
            "concentrations": concentrations,
            "hhi_score": hhi,
            "overall_risk": overall_risk,
            "recommendation": recommendation,
            "report_generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "disclaimer": "Not financial advice. Always do your own research.",
        }
    except json.JSONDecodeError:
        return {"error": "Invalid JSON. Use: {\"AAPL\": 10, \"MSFT\": 5}"}
    except Exception as e:
        return {"error": f"Portfolio analysis failed: {str(e)}"}


# ── TOOL 3: COMPARE STOCKS ────────────────────────────────────────────────────
def compare_stocks(symbols: str) -> dict:
    """Fetches and compares multiple stocks side by side.
    Use when user wants to compare 2 or more stocks.
    Args:
        symbols: Comma-separated tickers e.g. 'AAPL,MSFT,GOOGL'
    """
    try:
        import yfinance as yf
        results = {}
        for sym in [s.strip().upper() for s in symbols.split(",")]:
            try:
                info = yf.Ticker(sym).info
                price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                prev = info.get("previousClose", 0)
                chg_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
                results[sym] = {
                    "company": info.get("longName", sym),
                    "price": price,
                    "change_pct": f"{chg_pct}%",
                    "market_cap": info.get("marketCap", "N/A"),
                    "sector": info.get("sector", "N/A"),
                    "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
                    "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
                }
            except Exception as e:
                results[sym] = {"error": str(e)}
        return results
    except Exception as e:
        return {"error": f"Comparison failed: {str(e)}"}


# ── SINGLE AGENT WITH REACT REASONING ─────────────────────────────────────────
finsight_agent = LlmAgent(
    name="FinSightAgent",
    model="gemini-2.0-flash",
    description="FinSight financial analysis agent with ReAct reasoning.",
    instruction="""You are FinSight, a financial analysis assistant.
    You use ReAct reasoning — THINK before every action, OBSERVE every result.

    You have three tools:
    - get_stock_data: for single stock price queries
    - get_portfolio_with_risk: for portfolio value AND risk in one call
    - compare_stocks: for comparing 2 or more stocks

    ReAct process for every query:
    THINK: What is the user asking? Which tool fits?
    ACT: Call the right tool with correct arguments.
    OBSERVE: What did the tool return? Any errors?
    THINK: How do I present this clearly?
    RESPOND: Give a clear, formatted answer.

    Tool selection rules:
    - Single stock question → get_stock_data
    - Portfolio question with share counts → get_portfolio_with_risk
    - Comparison question → compare_stocks

    Response format:
    - Always use $ for prices
    - Always show risk level (LOW/MEDIUM/HIGH) for portfolio queries
    - Always show the recommendation for portfolio queries
    - Always end with: "⚠️ Not financial advice. Always do your own research."
    - Never invent prices or data""",
    tools=[get_stock_data, get_portfolio_with_risk, compare_stocks],
)

# ── SESSION & RUNNER ───────────────────────────────────────────────────────────
session_service = InMemorySessionService()
runner = Runner(
    agent=finsight_agent,
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
    print("✅ FinSight v0.2 ready (ReAct reasoning | 1-2 API calls per query)")

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
    tools_called = []

    # Auto-retry once if quota hit
    for attempt in range(2):
        try:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=SESSION_ID,
                new_message=user_message,
            ):
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            tools_called.append(part.function_call.name)
                if event.is_final_response():
                    response_text = event.content.parts[0].text
            break
        except Exception as e:
            if "429" in str(e) and attempt == 0:
                print("  ⏳ Quota hit — waiting 65s then retrying automatically...")
                await asyncio.sleep(65)
            else:
                return f"❌ Error: {str(e)[:200]}"

    if tools_called:
        print(f"  [tools called: {', '.join(set(tools_called))}]")
    return response_text

async def main():
    await setup()
    print("\n💰 FinSight v0.2 running")
    print("   Try: 'What is Apple stock price?'")
    print("   Try: 'Assess risk: 10 AAPL and 5 MSFT'")
    print("   Try: 'Compare AAPL and GOOGL'\n")

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