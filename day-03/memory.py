# memory.py — Day 3: Memory & State Management
import json
from pathlib import Path
from datetime import datetime

MEMORY_FILE = Path(__file__).parent / "memory.json"


def load_memory() -> dict:
    """Load memory from disk. Returns fresh state if no file exists."""
    if MEMORY_FILE.exists():
        try:
            data = json.loads(MEMORY_FILE.read_text())
            count = len(data.get("tool_history", []))
            print(f"📂 Memory loaded — {count} past tool calls found")
            return data
        except Exception:
            print("⚠️  Memory file corrupted — starting fresh")
    return {
        "tool_history": [],
        "facts_learned": {},
        "session_count": 0,
        "last_seen": None,
    }


def save_memory(state: dict) -> None:
    """Save current memory to disk."""
    state["last_seen"] = datetime.now().isoformat()
    MEMORY_FILE.write_text(json.dumps(state, indent=2))


def add_tool_call(state: dict, tool_name: str, user_input: str, result: str) -> None:
    """Record a tool call into memory."""
    state["tool_history"].append({
        "tool": tool_name,
        "input": user_input,
        "result": result[:120],
        "timestamp": datetime.now().isoformat(),
    })
    # Keep only last 50 entries
    if len(state["tool_history"]) > 50:
        state["tool_history"] = state["tool_history"][-50:]


def get_history_summary(state: dict) -> str:
    """Return last 5 tool calls to inject into agent system prompt."""
    history = state.get("tool_history", [])
    if not history:
        return "No previous tool calls yet."
    recent = history[-5:]
    lines = ["Recent tool history (last 5 calls):"]
    for h in recent:
        lines.append(f"  - {h['tool']}({h['input'][:50]}) → {h['result'][:60]}")
    return "\n".join(lines)