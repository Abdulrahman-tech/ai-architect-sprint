# FinSight v1.0 — Finance Agent

A financial analysis agent with live market data, 
risk assessment, and a full evaluation harness.

## Architecture
## Tools

| Tool | Purpose | API Used |
|------|---------|----------|
| get_stock_data | Single stock price + info | yfinance |
| get_portfolio_with_risk | Portfolio value + HHI risk score | yfinance |
| compare_stocks | Side-by-side stock comparison | yfinance |

## Evaluation Results

Overall Grade: **A** (96.7/100)

| Query | Tool | Score |
|-------|------|-------|
| Apple stock price | get_stock_data | 100/100 |
| Portfolio risk 10 AAPL + 5 MSFT | get_portfolio_with_risk | 90/100 |
| Compare AAPL and MSFT | compare_stocks | 90/100 |

## Risk Model

Uses **Herfindahl-Hirschman Index (HHI)**:
- HHI > 5000 → HIGH risk
- HHI 2500-5000 → MEDIUM risk  
- HHI < 2500 → LOW risk

## Design Decisions

**Why single agent instead of multi-agent?**
Multi-agent (Orchestrator → DataFetcher → RiskAssessor) requires
6-8 API calls per query. Free tier allows 5 RPM.
Collapsed into single agent with smart tools = 1-2 calls per query.
Same output, 75% fewer API calls.

**Why HHI for risk?**
Simple, explainable, and widely used in portfolio theory.
Doesn't require historical price data — works with current values only.

**Why trace everything?**
Production agents need observability from day one.
Adding it later means you missed bugs you didn't know existed.

## Known Limitations

- No historical price data for volatility calculation
- HHI only measures concentration, not market risk
- Free tier quota limits rapid testing
- yfinance data has ~15 min delay

## How to Run

```bash
export GOOGLE_API_KEY="your_key"
pip install google-adk yfinance
python agent.py
``` 

Commands:
- Type any financial question
- `eval` — run evaluation report
- `traces` — see all traced calls
- `quit` — exit