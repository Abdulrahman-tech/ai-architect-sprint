# risk_tools.py — Day 5: Risk Assessment Tools
import json
import math
from datetime import datetime


def assess_concentration_risk(holdings: str) -> dict:
    """Analyses portfolio concentration risk.
    
    Use this when evaluating how diversified a portfolio is.
    High concentration in one stock = high risk.
    
    Args:
        holdings: JSON string with symbol and dollar values e.g.
                  '{"AAPL": 3002.30, "MSFT": 2109.60}'
    
    Returns:
        A dict with concentration percentages and risk level.
    """
    try:
        portfolio = json.loads(holdings)
        total = sum(portfolio.values())
        if total == 0:
            return {"error": "Portfolio total value is zero."}

        concentrations = {}
        for symbol, value in portfolio.items():
            pct = round((value / total) * 100, 2)
            concentrations[symbol] = {
                "value": value,
                "percentage": pct,
                "risk_flag": pct > 40,
            }

        hhi = sum((v / total * 100) ** 2 for v in portfolio.values())
        hhi = round(hhi, 2)

        if hhi > 5000:
            risk_level = "HIGH"
            risk_note = "Portfolio is heavily concentrated. Consider diversifying."
        elif hhi > 2500:
            risk_level = "MEDIUM"
            risk_note = "Portfolio has moderate concentration. Some diversification recommended."
        else:
            risk_level = "LOW"
            risk_note = "Portfolio is well diversified."

        return {
            "concentrations": concentrations,
            "hhi_score": hhi,
            "risk_level": risk_level,
            "risk_note": risk_note,
            "total_value": round(total, 2),
        }
    except json.JSONDecodeError:
        return {"error": "Invalid JSON. Use format: {\"AAPL\": 3000, \"MSFT\": 2000}"}
    except Exception as e:
        return {"error": f"Concentration analysis failed: {str(e)}"}


def assess_volatility_risk(price_data: str) -> dict:
    """Analyses volatility risk from a series of recent prices.
    
    Use this when evaluating how volatile a stock has been.
    Higher volatility = higher risk.
    
    Args:
        price_data: JSON string with symbol and list of recent prices e.g.
                    '{"symbol": "AAPL", "prices": [180, 182, 179, 185, 183]}'
    
    Returns:
        A dict with volatility metrics and risk assessment.
    """
    try:
        data = json.loads(price_data)
        symbol = data.get("symbol", "UNKNOWN")
        prices = data.get("prices", [])

        if len(prices) < 2:
            return {"error": "Need at least 2 prices to calculate volatility."}

        returns = []
        for i in range(1, len(prices)):
            daily_return = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(daily_return)

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        annual_volatility = round(std_dev * math.sqrt(252) * 100, 2)

        if annual_volatility > 40:
            risk_level = "HIGH"
            risk_note = "Very high volatility. Significant price swings expected."
        elif annual_volatility > 20:
            risk_level = "MEDIUM"
            risk_note = "Moderate volatility. Normal for most stocks."
        else:
            risk_level = "LOW"
            risk_note = "Low volatility. Price movements are relatively stable."

        return {
            "symbol": symbol,
            "price_count": len(prices),
            "price_range": f"${min(prices)} - ${max(prices)}",
            "annualized_volatility_pct": f"{annual_volatility}%",
            "risk_level": risk_level,
            "risk_note": risk_note,
        }
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for price data."}
    except Exception as e:
        return {"error": f"Volatility analysis failed: {str(e)}"}


def generate_risk_report(concentration_result: str, volatility_result: str) -> dict:
    """Generates a final structured risk report combining all assessments.
    
    Use this as the LAST step after running concentration and volatility checks.
    
    Args:
        concentration_result: JSON string from assess_concentration_risk
        volatility_result: JSON string from assess_volatility_risk
    
    Returns:
        A structured risk report with overall risk score and recommendations.
    """
    try:
        concentration = json.loads(concentration_result)
        volatility = json.loads(volatility_result)

        risk_scores = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        c_score = risk_scores.get(concentration.get("risk_level", "MEDIUM"), 2)
        v_score = risk_scores.get(volatility.get("risk_level", "MEDIUM"), 2)
        overall_score = round((c_score + v_score) / 2, 1)

        if overall_score >= 2.5:
            overall_risk = "HIGH"
            recommendation = "Consider rebalancing. Reduce concentrated positions and high-volatility holdings."
        elif overall_score >= 1.5:
            overall_risk = "MEDIUM"
            recommendation = "Portfolio is acceptable but monitor concentration and volatility regularly."
        else:
            overall_risk = "LOW"
            recommendation = "Portfolio looks well balanced. Continue monitoring regularly."

        return {
            "report_generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "concentration_risk": concentration.get("risk_level", "N/A"),
            "volatility_risk": volatility.get("risk_level", "N/A"),
            "overall_risk": overall_risk,
            "overall_score": f"{overall_score}/3.0",
            "recommendation": recommendation,
            "concentration_note": concentration.get("risk_note", ""),
            "volatility_note": volatility.get("risk_note", ""),
            "disclaimer": "Automated risk assessment for educational purposes only. Not financial advice.",
        }
    except Exception as e:
        return {"error": f"Report generation failed: {str(e)}"}