# agent.py — Day 6: FinSight v1.0 — Evaluation & Observability
import os
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("\n❌ API key not set!\nRun: export GOOGLE_API_KEY='your_key_here'")
print(f"✅ API key loaded: {api_key[:8]}...")

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ── RATE LIMITER ──────────────────────────────────────────────────────────────
_last_call_time = 0

def wait_between_calls():
    """Wait 15 seconds between every API call — stays under any RPM limit."""
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if _last_call_time > 0 and elapsed < 15:
        wait = 15 - elapsed
        print(f"  ⏳ Waiting {wait:.1f}s between calls...")
        time.sleep(wait)
    _last_call_time = time.time()

# ── TRACE LOG ─────────────────────────────────────────────────────────────────
TRACE_FILE = Path(__file__).parent / "traces.json"
traces = []

def save_trace(user_input, response, tools_used, latency_ms):
    trace = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "input": user_input,
        "tools": tools_used,
        "latency_ms": latency_ms,
        "response_preview": response[:100],
    }
    traces.append(trace)
    TRACE_FILE.write_text(json.dumps(traces, indent=2))

# ── TOOLS ─────────────────────────────────────────────────────────────────────

def get_stock_data(symbol: str) -> dict:
    """Fetches current stock price for a ticker symbol.
    Use for single stock price queries.
    Args:
        symbol: Stock ticker e.g. 'AAPL', 'MSFT', 'TSLA', 'GOOGL'
    """
    try:
        import yfinance as yf
        info = yf.Ticker(symbol.upper()).info
        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        prev = info.get("previousClose", 0)
        change_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
        return {
            "symbol": symbol.upper(),
            "company": info.get("longName", "Unknown"),
            "price": price,
            "change_pct": f"{change_pct}%",
            "sector": info.get("sector", "N/A"),
            "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
        }
    except Exception as e:
        return {"error": f"Could not fetch '{symbol}': {str(e)}"}


def get_portfolio_with_risk(holdings_json: str) -> dict:
    """Fetches prices AND calculates risk for a portfolio.
    Use when user gives share counts and wants value + risk.
    Args:
        holdings_json: JSON e.g. '{"AAPL": 10, "MSFT": 5}'
    """
    try:
        import yfinance as yf
        holdings = json.loads(holdings_json)
        positions = {}
        total_value = 0.0
        dollar_values = {}

        for symbol, shares in holdings.items():
            try:
                info = yf.Ticker(symbol.upper()).info
                price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                val = round(price * shares, 2)
                total_value += val
                positions[symbol.upper()] = {
                    "shares": shares, "price": price,
                    "value": val, "company": info.get("longName", symbol),
                }
                dollar_values[symbol.upper()] = val
            except Exception as e:
                positions[symbol.upper()] = {"error": str(e)}

        if total_value == 0:
            return {"error": "Could not fetch prices."}

        hhi = round(sum((v/total_value*100)**2 for v in dollar_values.values()), 2)
        risk = "HIGH" if hhi > 5000 else "MEDIUM" if hhi > 2500 else "LOW"
        rec = {
            "HIGH": "Heavily concentrated. Diversify across more stocks.",
            "MEDIUM": "Moderate risk. Consider adding more stocks.",
            "LOW": "Well diversified. Keep monitoring.",
        }[risk]

        return {
            "positions": positions,
            "total_value": round(total_value, 2),
            "hhi_score": hhi,
            "risk": risk,
            "recommendation": rec,
            "disclaimer": "Not financial advice. Do your own research.",
        }
    except json.JSONDecodeError:
        return {"error": 'Invalid JSON. Use: {"AAPL": 10, "MSFT": 5}'}
    except Exception as e:
        return {"error": str(e)}


def compare_stocks(symbols: str) -> dict:
    """Compares multiple stocks side by side.
    Use when user wants to compare 2 or more stocks.
    Args:
        symbols: Comma-separated tickers e.g. 'AAPL,MSFT'
    """
    try:
        import yfinance as yf
        results = {}
        for sym in [s.strip().upper() for s in symbols.split(",")]:
            try:
                info = yf.Ticker(sym).info
                price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                prev = info.get("previousClose", 0)
                chg = round(((price-prev)/prev)*100, 2) if prev else 0
                results[sym] = {
                    "company": info.get("longName", sym),
                    "price": price,
                    "change_pct": f"{chg}%",
                    "market_cap": info.get("marketCap", "N/A"),
                    "sector": info.get("sector", "N/A"),
                }
            except Exception as e:
                results[sym] = {"error": str(e)}
        return results
    except Exception as e:
        return {"error": str(e)}


# ── AGENT ─────────────────────────────────────────────────────────────────────
agent = LlmAgent(
    name="FinSightAgent",
    model="gemini-2.5-flash-lite",
    description="FinSight v1.0 financial agent.",
    instruction="""You are FinSight, a financial assistant.
    Tools:
    - get_stock_data: single stock queries
    - get_portfolio_with_risk: portfolio value + risk
    - compare_stocks: compare multiple stocks

    Rules:
    - Single stock → get_stock_data
    - Portfolio with shares → get_portfolio_with_risk
    - Comparison → compare_stocks
    - Always show $ for prices
    - Always show risk level for portfolios
    - End every response with: "⚠️ Not financial advice. Do your own research."
    - Never invent prices""",
    tools=[get_stock_data, get_portfolio_with_risk, compare_stocks],
)

session_service = InMemorySessionService()
runner = Runner(agent=agent, app_name="finsight", session_service=session_service)

async def setup():
    session = await session_service.create_session(
        app_name="finsight", user_id="user", session_id="day06")
    print(f"✅ Session ready: {session.id}")

# ── CHAT WITH TRACING ─────────────────────────────────────────────────────────
async def chat(message: str) -> str:
    wait_between_calls()

    user_message = types.Content(role="user", parts=[types.Part(text=message)])
    response_text = ""
    tools_used = []
    start = time.time()

    for attempt in range(2):
        try:
            async for event in runner.run_async(
                user_id="user", session_id="day06", new_message=user_message
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
                return f"❌ {str(e)[:150]}"

    latency = round((time.time() - start) * 1000, 2)
    save_trace(message, response_text, list(set(tools_used)), latency)

    if tools_used:
        print(f"  [tools: {', '.join(set(tools_used))}]")
    print(f"  [latency: {latency}ms]")
    return response_text

# ── EVAL REPORT ───────────────────────────────────────────────────────────────
def show_eval():
    if not traces:
        print("No traces yet. Ask questions first!\n")
        return

    ground_truth = {
        "apple stock": ("get_stock_data", ["$"]),
        "assess risk": ("get_portfolio_with_risk", ["risk", "$"]),
        "compare": ("compare_stocks", ["AAPL", "MSFT"]),
    }

    print("\n" + "="*50)
    print("FINSIGHT EVALUATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)

    total_score = 0
    count = 0

    for trace in traces:
        score = 100
        reasons = []
        inp = trace["input"].lower()
        resp = trace["response_preview"].lower()
        tools = trace["tools"]

        matched_gt = None
        for keyword, (expected_tool, expected_words) in ground_truth.items():
            if keyword in inp:
                matched_gt = (expected_tool, expected_words)
                break

        if matched_gt:
            expected_tool, expected_words = matched_gt
            if expected_tool not in tools:
                score -= 40
                reasons.append(f"❌ Wrong tool (expected {expected_tool})")
            else:
                reasons.append(f"✅ Correct tool: {expected_tool}")
            for word in expected_words:
                if word.lower() not in resp:
                    score -= 20
                    reasons.append(f"❌ Missing: '{word}'")
                else:
                    reasons.append(f"✅ Has '{word}'")
            if "not financial advice" not in resp and "own research" not in resp:
                score -= 10
                reasons.append("❌ Missing disclaimer")
            else:
                reasons.append("✅ Has disclaimer")

        grade = "A" if score>=90 else "B" if score>=75 else "C" if score>=60 else "F"
        print(f"\n[{grade}] {score}/100 — {trace['input'][:45]}")
        print(f"  Tools: {tools} | Latency: {trace['latency_ms']}ms")
        for r in reasons:
            print(f"  {r}")
        total_score += score
        count += 1

    avg = round(total_score/count, 1) if count else 0
    overall = "A" if avg>=90 else "B" if avg>=75 else "C" if avg>=60 else "F"
    print(f"\n{'='*50}")
    print(f"OVERALL: [{overall}] {avg}/100 across {count} traces")
    print("="*50)
    Path(__file__).parent.joinpath("eval_report.txt").write_text(
        f"Overall: {overall} | Score: {avg}/100 | Traces: {count}")
    print("📄 Saved to eval_report.txt\n")

# ── MAIN ─────────────────────────────────────────────────────────────────────
async def main():
    await setup()
    print("\n💰 FinSight v1.0 (15s wait between calls — quota safe)")
    print("   'What is Apple stock price?'")
    print("   'Assess risk: 10 AAPL and 5 MSFT'")
    print("   'Compare AAPL and MSFT'")
    print("   'eval' — run evaluation report")
    print("   'traces' — see trace log\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if user_input.lower() in ["quit", "exit", "q"]:
            break
        if not user_input:
            continue
        if user_input.lower() == "eval":
            show_eval()
            continue
        if user_input.lower() == "traces":
            print(f"\n📋 {len(traces)} traces:")
            for t in traces:
                print(f"  [{t['time']}] {t['input'][:40]} | {t['tools']}")
            print()
            continue
        response = await chat(user_input)
        print(f"FinSight: {response}\n")

if __name__ == "__main__":
    asyncio.run(main())