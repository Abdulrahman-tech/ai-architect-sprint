import math
import requests
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def calculate(expression: str) -> dict:
    """Evaluates a mathematical expression and returns the result.
    Use this tool when the user asks to calculate, compute, or solve any math problem.
    Args:
        expression: A math expression as a string e.g. 'sqrt(144)', '2**10', '15/100 * 200'
    Returns:
        A dict with 'result' (number) and 'expression' (what was evaluated).
    """
    try:
        safe_globals = {
            "__builtins__": {},
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "log": math.log, "pi": math.pi,
            "e": math.e, "abs": abs, "round": round,
        }
        result = eval(expression, safe_globals)
        return {"result": round(result, 6), "expression": expression}
    except ZeroDivisionError:
        return {"error": "Cannot divide by zero.", "expression": expression}
    except Exception as e:
        return {"error": f"Could not evaluate '{expression}': {str(e)}"}


def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """Converts an amount from one currency to another using live exchange rates.
    Use this when the user asks to convert money between currencies.
    Args:
        amount: The numeric amount to convert
        from_currency: Source currency code e.g. 'USD', 'NGN', 'EUR', 'GBP'
        to_currency: Target currency code e.g. 'EUR', 'USD', 'JPY'
    """
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency.upper()}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        rates = data.get("rates", {})
        to_curr = to_currency.upper()
        if to_curr not in rates:
            return {"error": f"Currency '{to_currency}' not found. Use codes like USD, EUR, GBP, NGN."}
        rate = rates[to_curr]
        return {
            "original_amount": amount,
            "from_currency": from_currency.upper(),
            "to_currency": to_curr,
            "converted_amount": round(amount * rate, 2),
            "exchange_rate": rate,
        }
    except requests.exceptions.Timeout:
        return {"error": "Exchange rate API timed out. Try again."}
    except Exception as e:
        return {"error": f"Could not reach exchange rate API: {str(e)}"}


def get_world_time(timezone: str) -> dict:
    """Returns the current date and time in a given timezone.
    Use this when the user asks what time it is in a city or country.
    Args:
        timezone: IANA timezone name e.g. 'Africa/Lagos', 'America/New_York', 'Europe/London'
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return {
            "timezone": timezone,
            "current_time": now.strftime("%H:%M:%S"),
            "current_date": now.strftime("%A, %d %B %Y"),
            "utc_offset": now.strftime("UTC%z"),
        }
    except ZoneInfoNotFoundError:
        return {
            "error": f"Unknown timezone '{timezone}'.",
            "hint": "Use IANA format like 'Africa/Lagos', 'America/New_York', 'Europe/London'",
        }


def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """Converts between common units of measurement.
    Supports: km/miles/meters/feet, kg/pounds/grams, celsius/fahrenheit/kelvin, liters/gallons/ml.
    Args:
        value: The number to convert
        from_unit: Source unit e.g. 'km', 'kg', 'celsius', 'liters'
        to_unit: Target unit e.g. 'miles', 'pounds', 'fahrenheit', 'gallons'
    """
    f = from_unit.lower()
    t = to_unit.lower()
    conversions = {
        ("km", "miles"): lambda v: v * 0.621371,
        ("miles", "km"): lambda v: v * 1.60934,
        ("km", "meters"): lambda v: v * 1000,
        ("meters", "km"): lambda v: v / 1000,
        ("meters", "feet"): lambda v: v * 3.28084,
        ("feet", "meters"): lambda v: v / 3.28084,
        ("kg", "pounds"): lambda v: v * 2.20462,
        ("pounds", "kg"): lambda v: v / 2.20462,
        ("kg", "grams"): lambda v: v * 1000,
        ("grams", "kg"): lambda v: v / 1000,
        ("liters", "gallons"): lambda v: v * 0.264172,
        ("gallons", "liters"): lambda v: v / 0.264172,
        ("liters", "ml"): lambda v: v * 1000,
        ("ml", "liters"): lambda v: v / 1000,
    }
    if f == "celsius" and t == "fahrenheit":
        result = (value * 9/5) + 32
    elif f == "fahrenheit" and t == "celsius":
        result = (value - 32) * 5/9
    elif f == "celsius" and t == "kelvin":
        result = value + 273.15
    elif f == "kelvin" and t == "celsius":
        result = value - 273.15
    elif (f, t) in conversions:
        result = conversions[(f, t)](value)
    else:
        return {"error": f"Conversion from '{from_unit}' to '{to_unit}' not supported."}
    return {"original": f"{value} {from_unit}", "converted": f"{round(result, 4)} {to_unit}"}