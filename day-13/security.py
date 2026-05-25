# security.py — Day 13: Security for DevOps AutoPilot
import re
import hashlib
import hmac
import time

INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+instructions",
    r"forget\s+(everything|all|previous)",
    r"new\s+system\s+prompt",
    r"you\s+are\s+now\s+a",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a\s+different)",
    r"disregard\s+(your|all)\s+(instructions|rules)",
    r"(override|bypass|disable)\s+(safety|filter|guardrail)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"\[system\]",
    r"<\s*system\s*>",
    r"print\s+(all|your)\s+(secrets|api\s+key|token)",
    r"reveal\s+(your|the)\s+(api|secret|token|key)",
    r"what\s+is\s+your\s+(api\s+key|secret|password)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def check_prompt_injection(text: str) -> dict:
    """Checks input for prompt injection attempts.
    Args:
        text: User input to check
    """
    detected = []
    for i, pattern in enumerate(COMPILED_PATTERNS):
        if pattern.search(text):
            detected.append(INJECTION_PATTERNS[i])
    if detected:
        return {
            "is_safe": False,
            "threat_type": "prompt_injection",
            "matched_patterns": detected,
            "message": "Input blocked: potential prompt injection detected.",
            "action": "reject",
        }
    return {"is_safe": True}


def validate_pipeline_id(pipeline_id: str) -> dict:
    """Validates pipeline ID format to prevent injection via parameters.
    Args:
        pipeline_id: Pipeline ID to validate
    """
    pattern = re.compile(r'^[a-zA-Z0-9_\-]{1,50}$')
    if not pattern.match(pipeline_id):
        return {
            "is_valid": False,
            "error": f"Invalid pipeline ID: '{pipeline_id}'. "
                     f"Only alphanumeric, underscore, hyphen allowed.",
        }
    return {"is_valid": True, "pipeline_id": pipeline_id}


def sanitize_log_output(log_text: str) -> str:
    """Removes sensitive data from log output before displaying.
    Args:
        log_text: Raw log text to sanitize
    """
    log_text = re.sub(
        r'(api[_-]?key|apikey|api[_-]?token)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{10,})["\']?',
        r'\1=***REDACTED***', log_text, flags=re.IGNORECASE)
    log_text = re.sub(
        r'(Bearer\s+)([a-zA-Z0-9_\-\.]{10,})',
        r'\1***REDACTED***', log_text, flags=re.IGNORECASE)
    log_text = re.sub(
        r'(password|passwd|pwd)\s*[=:]\s*["\']?(\S+)["\']?',
        r'\1=***REDACTED***', log_text, flags=re.IGNORECASE)
    log_text = re.sub(r'(AKIA[0-9A-Z]{16})', r'***AWS_KEY_REDACTED***', log_text)
    return log_text


def verify_webhook_signature(payload: str, signature: str, secret: str) -> dict:
    """Verifies GitHub-style webhook HMAC signature.
    Args:
        payload: Raw webhook payload
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret
    """
    if not signature.startswith("sha256="):
        return {"is_valid": False, "error": "Invalid signature format."}
    expected = "sha256=" + hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, signature):
        return {"is_valid": True}
    return {"is_valid": False, "error": "Signature mismatch. Webhook rejected."}


_request_timestamps: dict = {}

def check_rate_limit(client_ip: str, max_requests: int = 10, window_seconds: int = 60) -> dict:
    """Per-IP rate limiting.
    Args:
        client_ip: Client IP address
        max_requests: Max requests in window
        window_seconds: Time window
    """
    now = time.time()
    if client_ip not in _request_timestamps:
        _request_timestamps[client_ip] = []
    _request_timestamps[client_ip] = [
        t for t in _request_timestamps[client_ip] if now - t < window_seconds]
    count = len(_request_timestamps[client_ip])
    if count >= max_requests:
        return {
            "allowed": False,
            "error": f"Rate limit exceeded: {count}/{max_requests} in {window_seconds}s",
            "retry_after": window_seconds,
        }
    _request_timestamps[client_ip].append(now)
    return {
        "allowed": True,
        "requests_used": count + 1,
        "requests_remaining": max_requests - count - 1,
    }