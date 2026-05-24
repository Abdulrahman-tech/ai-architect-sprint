# pipeline_chain.py — Day 12: Tool chaining and conditional routing
# Pure Python — zero API calls
import json
from datetime import datetime
from pathlib import Path
from ci_tools import (
    get_pipeline_status, classify_failure,
    get_fix_context, MOCK_PIPELINES
)

NOTIF_LOG = Path(__file__).parent / "notifications.json"

def _load_notifications() -> list:
    if NOTIF_LOG.exists():
        try:
            return json.loads(NOTIF_LOG.read_text())
        except Exception:
            return []
    return []

def _save_notification(notif: dict):
    notifs = _load_notifications()
    notifs.append(notif)
    NOTIF_LOG.write_text(json.dumps(notifs, indent=2))


ROUTING_RULES = {
    "docker_auth":         ("critical", "devops",   "#devops-alerts",   True),
    "dependency_conflict": ("high",     "frontend", "#frontend-alerts",  True),
    "test_failure":        ("medium",   "dev",      "#dev-alerts",       True),
    "build_error":         ("high",     "dev",      "#dev-alerts",       True),
    "network_error":       ("critical", "devops",   "#devops-alerts",   True),
    "unknown":             ("low",      "dev",      "#general-alerts",   False),
}


def route_failure(failure_type: str) -> dict:
    """Determines routing for a failure type. Pure Python — zero API calls.
    Args:
        failure_type: From classify_failure result
    """
    rule = ROUTING_RULES.get(failure_type, ROUTING_RULES["unknown"])
    severity, team, channel, needs_fix = rule
    escalate = severity in ["critical"]

    return {
        "failure_type": failure_type,
        "severity": severity,
        "assigned_team": team,
        "notification_channel": channel,
        "needs_llm_fix": needs_fix,
        "escalate": escalate,
        "routing_decision": (
            f"Route to {team} team via {channel} (severity: {severity})"
            + (" — ESCALATE" if escalate else "")
        ),
    }


def notify_team(pipeline_id: str, routing: dict, fix_summary: str = "") -> dict:
    """Sends mock notification. Pure Python — zero API calls.
    Args:
        pipeline_id: Pipeline that failed
        routing: From route_failure result
        fix_summary: Optional fix text
    """
    pipeline = next(
        (p for p in MOCK_PIPELINES if p["id"] == pipeline_id), None)
    if not pipeline:
        return {"error": f"Pipeline {pipeline_id} not found"}

    notification = {
        "id": f"notif_{int(datetime.now().timestamp())}",
        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "channel": routing["notification_channel"],
        "team": routing["assigned_team"],
        "severity": routing["severity"],
        "escalated": routing["escalate"],
        "message": {
            "title": f"❌ Pipeline Failed: {pipeline['repo']} ({pipeline['branch']})",
            "pipeline_id": pipeline_id,
            "failure_type": routing["failure_type"].upper(),
            "severity": routing["severity"].upper(),
            "fix_available": bool(fix_summary),
        },
    }

    _save_notification(notification)

    return {
        "status": "sent",
        "notification_id": notification["id"],
        "channel": routing["notification_channel"],
        "team": routing["assigned_team"],
        "message_preview": notification["message"]["title"],
        "escalated": routing["escalate"],
    }


def run_full_pipeline(pipeline_id: str) -> dict:
    """Full chain: classify → route → notify. Returns fix context for LLM.
    Pure Python — zero API calls.
    Args:
        pipeline_id: Pipeline to process
    """
    classification = classify_failure(pipeline_id)
    if "error" in classification:
        return {"error": classification["error"], "step": "classify"}

    if classification.get("failure_type") is None:
        return {"status": "success", "message": f"Pipeline {pipeline_id} passed."}

    routing = route_failure(classification["failure_type"])
    fix_docs = get_fix_context(classification["failure_type"])
    notification = notify_team(pipeline_id, routing)

    return {
        "pipeline_id": pipeline_id,
        "repo": classification["repo"],
        "branch": classification["branch"],
        "failure_type": classification["failure_type"],
        "severity": routing["severity"],
        "team": routing["assigned_team"],
        "channel": routing["notification_channel"],
        "escalated": routing["escalate"],
        "log_excerpt": classification["log_excerpt"],
        "fix_documentation": fix_docs["fix_documentation"],
        "notification_sent": notification["status"] == "sent",
        "notification_id": notification["notification_id"],
        "needs_llm_fix": routing["needs_llm_fix"],
        "chain_complete": True,
    }


def get_notifications() -> list:
    """Returns all sent notifications. Pure Python — zero API calls."""
    return _load_notifications()