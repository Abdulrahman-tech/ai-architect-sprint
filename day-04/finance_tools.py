# finance_tools.py — Day 4: Financial data tools
# Uses yfinance for real market data — free, no API key needed

import json
from datetime import datetime


def get_stock_data(symbol: str) -> dict:
    """Fetches current stock price and basic info for a given ticker symbol.
    
    Use this tool when asked about a stock price, company valuation,
    or market data for any publicly traded company.
    
    Args:
        symbol: Stock ticker symbol e.g. 'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN'
    
    Returns:
        A dict with current price, company name, market cap, and price change.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info

        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        prev_close = info.get("previousClose", 0)
        change = round(current_price - prev_close, 2) if prev_close else 0
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0

        return {
            "symbol": symbol.upper(),
            "company_name": info.get("longName", "Unknown"),
            "current_price": current_price,
            "currency": info.get("currency", "USD"),
            "previous_close": prev_close,
            "price_change": change,
            "price_change_pct": f"{change_pct}%",
            "market_cap": info.get("marketCap", "N/A"),
            "sector": info.get("sector", "N/A"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", "N/A"),
        }
    except ImportError:
        return {"error": "yfinance not installed. Run: pip install yfinance"}
    except Exception as e:
        return {"error": f"Could not fetch data for '{symbol}': {str(e)}"}


def get_multiple_stocks(symbols: str) -> dict:
    """Fetches stock data for multiple ticker symbols at once.
    
    Use this when the user asks to compare multiple stocks or
    wants a portfolio overview.
    
    Args:
        symbols: Comma-separated ticker symbols e.g. 'AAPL,GOOGL,MSFT'
    
    Returns:
        A dict with data for each symbol.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    results = {}
    for symbol in symbol_list:
        results[symbol] = get_stock_data(symbol)
    return results


def calculate_portfolio_value(holdings: str) -> dict:
    """Calculates the total value of a stock portfolio.
    
    Use this when the user provides stock holdings and wants to know
    the total portfolio value.
    
    Args:
        holdings: JSON string of holdings e.g. '{"AAPL": 10, "GOOGL": 5}'
                  where keys are ticker symbols and values are number of shares.
    
    Returns:
        A dict with individual position values and total portfolio value.
    """
    try:
        portfolio = json.loads(holdings)
        positions = {}
        total_value = 0.0

        for symbol, shares in portfolio.items():
            data = get_stock_data(symbol)
            if "error" in data:
                positions[symbol] = {"error": data["error"], "shares": shares}
                continue
            price = data["current_price"]
            position_value = round(price * shares, 2)
            total_value += position_value
            positions[symbol] = {
                "shares": shares,
                "price": price,
                "position_value": position_value,
                "company": data["company_name"],
            }

        return {
            "positions": positions,
            "total_portfolio_value": round(total_value, 2),
            "currency": "USD",
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except json.JSONDecodeError:
        return {"error": "Invalid format. Use JSON like: {\"AAPL\": 10, \"GOOGL\": 5}"}
    except Exception as e:
        return {"error": f"Portfolio calculation failed: {str(e)}"}