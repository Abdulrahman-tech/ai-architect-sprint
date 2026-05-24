# ci_tools.py — Day 11: CI/CD monitoring tools — pure Python, zero API calls
import json
import re
from datetime import datetime

MOCK_PIPELINES = [
    {
        "id": "pipeline_001",
        "repo": "my-app",
        "branch": "main",
        "status": "failed",
        "triggered_by": "push",
        "started_at": "2026-05-22 09:00:00",
        "duration_seconds": 145,
        "jobs": [
            {
                "name": "test",
                "status": "failed",
                "log": """
Running test suite...
PASS src/auth/login.test.js
FAIL src/payment/checkout.test.js
  ● checkout › should process payment
    TypeError: Cannot read property 'stripe' of undefined
      at processPayment (src/payment/checkout.js:42)
npm ERR! Test failed.
exit code: 1
                """,
            }
        ],
    },
    {
        "id": "pipeline_002",
        "repo": "my-app",
        "branch": "feature/new-ui",
        "status": "failed",
        "triggered_by": "pull_request",
        "started_at": "2026-05-22 10:30:00",
        "duration_seconds": 89,
        "jobs": [
            {
                "name": "build",
                "status": "failed",
                "log": """
Installing dependencies...
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR! Found: react@17.0.2
npm ERR! Could not resolve dependency: react@^18.0.0
npm ERR! Fix the upstream dependency conflict
exit code: 1
                """,
            }
        ],
    },
    {
        "id": "pipeline_003",
        "repo": "api-service",
        "branch": "main",
        "status": "failed",
        "triggered_by": "schedule",
        "started_at": "2026-05-22 11:00:00",
        "duration_seconds": 210,
        "jobs": [
            {
                "name": "deploy",
                "status": "failed",
                "log": """
Building Docker image...
Successfully built abc123def456
Deploying to production...
Error: ImagePullBackOff
failed to pull and unpack image:
unexpected status code 401 Unauthorized
exit code: 1
                """,
            }
        ],
    },
    {
        "id": "pipeline_004",
        "repo": "my-app",
        "branch": "main",
        "status": "success",
        "triggered_by": "push",
        "started_at": "2026-05-22 08:00:00",
        "duration_seconds": 98,
        "jobs": [
            {"name": "test", "status": "success", "log": "All tests passed!"},
            {"name": "build", "status": "success", "log": "Build successful."},
            {"name": "deploy", "status": "success", "log": "Deployed to staging."},
        ],
    },
]


def get_pipeline_status(repo: str = "") -> dict:
    """Gets recent pipeline runs. Pure Python — zero API calls.
    Args:
        repo: Optional repo name filter. Empty = all repos.
    """
    pipelines = MOCK_PIPELINES
    if repo:
        pipelines = [p for p in pipelines if repo.lower() in p["repo"].lower()]

    failed = [p for p in pipelines if p["status"] == "failed"]
    success = [p for p in pipelines if p["status"] == "success"]

    return {
        "total_pipelines": len(pipelines),
        "failed_count": len(failed),
        "success_count": len(success),
        "failed_pipelines": [
            {
                "id": p["id"],
                "repo": p["repo"],
                "branch": p["branch"],
                "started_at": p["started_at"],
                "duration_seconds": p["duration_seconds"],
            }
            for p in failed
        ],
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def classify_failure(pipeline_id: str) -> dict:
    """Classifies failure type from pipeline logs. Pure Python — zero API calls.
    Args:
        pipeline_id: Pipeline ID from get_pipeline_status
    """
    pipeline = next(
        (p for p in MOCK_PIPELINES if p["id"] == pipeline_id), None)
    if not pipeline:
        return {"error": f"Pipeline '{pipeline_id}' not found."}

    if pipeline["status"] == "success":
        return {"pipeline_id": pipeline_id, "status": "success", "failure_type": None}

    failed_job = next(
        (j for j in pipeline["jobs"] if j["status"] == "failed"), None)
    if not failed_job:
        return {"error": "No failed job found."}

    log = failed_job["log"].lower()

    # Order matters — specific patterns first
    failure_patterns = {
        "docker_auth": [
            "401 unauthorized", "imagepullbackoff",
            "failed to pull", "unauthorized",
        ],
        "dependency_conflict": [
            "eresolve", "dependency conflict",
            "could not resolve", "upstream dependency",
        ],
        "test_failure": [
            "test failed", "typeerror", "assertionerror", "● ",
        ],
        "build_error": [
            "build failed", "syntax error", "cannot find module",
        ],
        "network_error": [
            "connection refused", "econnrefused", "timeout",
        ],
    }

    detected_type = "unknown"
    confidence = "low"
    matched_patterns = []

    for failure_type, patterns in failure_patterns.items():
        matches = [p for p in patterns if p in log]
        if matches:
            detected_type = failure_type
            matched_patterns = matches
            confidence = "high" if len(matches) >= 2 else "medium"
            break

    return {
        "pipeline_id": pipeline_id,
        "repo": pipeline["repo"],
        "branch": pipeline["branch"],
        "job_name": failed_job["name"],
        "failure_type": detected_type,
        "confidence": confidence,
        "matched_patterns": matched_patterns,
        "log_excerpt": failed_job["log"].strip()[:300],
        "classified_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_fix_context(failure_type: str) -> dict:
    """Gets fix documentation for a failure type. Pure Python — zero API calls.
    Args:
        failure_type: From classify_failure result
    """
    fix_docs = {
        "dependency_conflict": {
            "description": "NPM dependency resolution conflict",
            "common_causes": [
                "Mismatched peer dependency versions",
                "Multiple packages requiring different versions",
                "Outdated package-lock.json",
            ],
            "standard_fixes": [
                "Run: npm install --legacy-peer-deps",
                "Update conflicting package versions in package.json",
                "Delete node_modules and package-lock.json then reinstall",
                "Use npm-check-updates to upgrade all deps",
            ],
        },
        "test_failure": {
            "description": "Unit or integration test failure",
            "common_causes": [
                "Code change broke existing functionality",
                "Missing mock or stub setup",
                "Undefined variable or null reference",
            ],
            "standard_fixes": [
                "Check the specific test file and line number in the log",
                "Verify mock setup for external dependencies",
                "Add null checks before property access",
                "Use jest.mock() for external modules",
            ],
        },
        "docker_auth": {
            "description": "Docker registry authentication failure",
            "common_causes": [
                "Expired registry credentials",
                "Missing IMAGE_PULL_SECRET",
                "Registry token not configured in CI",
            ],
            "standard_fixes": [
                "Refresh registry credentials in CI secrets",
                "Run: kubectl create secret docker-registry regcred",
                "Verify REGISTRY_TOKEN secret is set in pipeline config",
                "Check registry URL matches the image path",
            ],
        },
        "build_error": {
            "description": "Build or compilation failure",
            "common_causes": [
                "Syntax error in code",
                "Missing environment variable",
                "Incompatible runtime version",
            ],
            "standard_fixes": [
                "Check the specific file and line in build log",
                "Verify all env vars are set in CI config",
                "Check runtime version matches local dev",
            ],
        },
        "network_error": {
            "description": "Network connectivity failure",
            "common_causes": [
                "External service unavailable",
                "DNS resolution failure",
            ],
            "standard_fixes": [
                "Check external service status",
                "Verify network policies allow outbound connections",
                "Add retry logic to the failing step",
            ],
        },
    }

    doc = fix_docs.get(failure_type, {
        "description": f"Unknown failure type: {failure_type}",
        "common_causes": ["Could not classify automatically"],
        "standard_fixes": ["Review full pipeline log manually"],
    })

    return {"failure_type": failure_type, "fix_documentation": doc}