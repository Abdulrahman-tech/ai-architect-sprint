import time
import json
from pathlib import Path
from datetime import date

USAGE_FILE = Path(__file__).parent / "api_usage.json"

RPM_LIMIT = 25    # gemini-2.0-flash-lite: 30 RPM — we use 25 as buffer
RPD_LIMIT = 1500  # gemini-2.0-flash-lite: 1500 RPD

def load_usage() -> dict:
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text())
        except Exception:
            pass
    return {"date": str(date.today()), "daily_count": 0, "minute_timestamps": []}

def save_usage(usage: dict) -> None:
    USAGE_FILE.write_text(json.dumps(usage, indent=2))

def check_and_wait() -> dict:
    usage = load_usage()
    if usage["date"] != str(date.today()):
        usage = {"date": str(date.today()), "daily_count": 0, "minute_timestamps": []}
        print("📅 New day — daily quota reset!")
    if usage["daily_count"] >= RPD_LIMIT:
        raise RuntimeError(f"\n🚫 Daily limit reached ({RPD_LIMIT} requests).")
    now = time.time()
    usage["minute_timestamps"] = [t for t in usage["minute_timestamps"] if now - t < 60]
    if len(usage["minute_timestamps"]) >= RPM_LIMIT:
        oldest = usage["minute_timestamps"][0]
        wait_seconds = 60 - (now - oldest) + 1
        if wait_seconds > 0:
            print(f"⏳ Waiting {wait_seconds:.1f}s (RPM limit)...")
            time.sleep(wait_seconds)
            now = time.time()
            usage["minute_timestamps"] = [t for t in usage["minute_timestamps"] if now - t < 60]
    usage["minute_timestamps"].append(time.time())
    usage["daily_count"] += 1
    print(f"  📊 API calls today: {usage['daily_count']}/{RPD_LIMIT} | This minute: {len(usage['minute_timestamps'])}/{RPM_LIMIT}")
    save_usage(usage)
    return usage
