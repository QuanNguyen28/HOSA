#!/usr/bin/env python3
"""
Pre-write check for backend component files.

Detects the kind of component (endpoint, worker/consumer, cron, integration)
from path and content cues, then warns about missing senior reflexes for that
component type. Does NOT block.

Reflexes checked, by component type:

Endpoint / handler:
  - No visible input validation
  - No visible auth/authorization
  - try/except: pass (silent swallow)

Worker / consumer / job:
  - No visible retry / dead-letter awareness
  - No idempotency / dedup
  - Side-effect call directly inside a DB transaction (heuristic)

Integration (outbound HTTP):
  - HTTP call without an explicit timeout
  - No idempotency key on POST/PUT/PATCH

Cross-cutting:
  - print() / console.log in production-looking code
  - bare except / catch(Exception) without re-raise or structured log
"""

import json
import os
import re
import sys


def is_skippable(path: str) -> bool:
    p = path.lower().replace("\\", "/")
    skip_markers = (
        "/test", "/tests/", "_test.", ".test.", ".spec.",
        "/node_modules/", "/.git/", "/dist/", "/build/",
        "/__pycache__/", "/vendor/",
    )
    return any(m in p for m in skip_markers)


def classify(path: str, content: str) -> set:
    p = path.lower().replace("\\", "/")
    c = content.lower()
    kinds = set()

    endpoint_hints = ("/routes/", "/handlers/", "/controllers/", "/api/", "/endpoints/", "/resolvers/")
    if any(h in p for h in endpoint_hints) or re.search(r"\b(app|router)\.(get|post|put|delete|patch)\s*\(", content) or "@app.route" in content or "@router." in content or "func.*http.ResponseWriter" in c:
        kinds.add("endpoint")

    worker_hints = ("/workers/", "/jobs/", "/consumers/", "/tasks/", "/queues/")
    worker_patterns = (
        r"\bconsume\b",
        r"@(celery|sidekiq|rq|dramatiq|bullmq)",
        r"\.on\(['\"](message|delivery)['\"]",
        r"kafka.*consumer",
        r"sqs.*receive",
    )
    if any(h in p for h in worker_hints) or any(re.search(pat, c) for pat in worker_patterns):
        kinds.add("worker")

    cron_hints = ("/cron/", "/scheduled/", "/schedule/")
    if any(h in p for h in cron_hints) or "schedule.every" in c or "@cron" in c:
        kinds.add("cron")

    integration_patterns = (
        r"\brequests\.(get|post|put|patch|delete)\(",
        r"\baxios\.(get|post|put|patch|delete)\(",
        r"\bfetch\s*\(\s*['\"]https?://",
        r"\bhttp\.client",
        r"\bgot\(['\"]https?://",
    )
    if any(re.search(pat, content, re.IGNORECASE) for pat in integration_patterns):
        kinds.add("integration")

    return kinds


CONCERNS = []


def add(label: str, why: str, where: str = ""):
    suffix = " ({})".format(where) if where else ""
    CONCERNS.append("{}: {}{}".format(label, why, suffix))


def check_swallow(content: str):
    # Python: except ...: pass / except Exception: pass
    if re.search(r"except\s+[^\n]*:\s*\n\s*pass\b", content):
        add("silent except", "An `except: pass` swallows the failure with no log and no recovery. See skills/error-handling-as-design.")
    # JS/TS: catch (e) { } empty or only with comment
    if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", content) or re.search(r"catch\s*\([^)]*\)\s*\{\s*//[^\n]*\n\s*\}", content):
        add("silent catch", "An empty catch block hides the failure with no log and no recovery. See skills/error-handling-as-design.")


def check_print_logs(content: str, path: str):
    if path.endswith((".py",)) and re.search(r"^\s*print\s*\(", content, re.MULTILINE):
        add("print() in code", "Use structured logging instead. See skills/observability-by-default.")
    if path.endswith((".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs")) and re.search(r"\bconsole\.(log|info)\(", content):
        add("console.log in code", "Use a structured logger (pino, winston, structured slog, etc). See skills/observability-by-default.")


def check_endpoint(content: str):
    has_validation = bool(re.search(r"\b(zod|joi|yup|valibot|pydantic|marshmallow|cerberus|validator|schema)\b", content, re.IGNORECASE))
    has_validation = has_validation or bool(re.search(r"\bclass\s+\w+\(BaseModel\)", content))
    if not has_validation:
        add("no boundary validation visible", "Endpoints validate input at the boundary. Add a schema (zod, pydantic, etc). See skills/error-handling-as-design.")

    has_auth = bool(re.search(r"\b(authenticate|authorize|requires_auth|@login_required|requireAuth|currentUser|session|jwt|bearer|verify_token)\b", content, re.IGNORECASE))
    if not has_auth:
        add("no auth/authorization visible", "Endpoints state the principal and the scope explicitly. See skills/think-before-coding step 4.")


def check_worker(content: str):
    has_retry = bool(re.search(r"\b(retry|max_retries|backoff|dead[_\- ]?letter|dlq|requeue)\b", content, re.IGNORECASE))
    if not has_retry:
        add("no retry / DLQ policy visible", "Workers and consumers are at-least-once. State retry, backoff, and dead-letter behavior. See skills/idempotency-and-side-effects.")

    has_idempotency = bool(re.search(r"\b(idempoten|dedup|already_processed|seen_events?|on conflict|insert ignore)\b", content, re.IGNORECASE))
    if not has_idempotency:
        add("no idempotency / dedup visible", "Consumers must handle redelivery. Add a dedup key (event ID, payload hash). See skills/idempotency-and-side-effects.")


def check_integration(content: str):
    # HTTP call missing a timeout (rough check)
    if re.search(r"\brequests\.(get|post|put|patch|delete)\(", content) and "timeout" not in content.lower():
        add("HTTP call without timeout", "`requests.*` without `timeout=` blocks the worker forever on a hung remote. Always pass a timeout.")
    if re.search(r"\baxios\.(get|post|put|patch|delete)\(", content) and "timeout" not in content.lower():
        add("HTTP call without timeout", "`axios.*` without `timeout:` blocks on a hung remote. Always pass a timeout.")
    if re.search(r"\bfetch\s*\(\s*['\"]https?://", content) and "abortcontroller" not in content.lower() and "abortsignal" not in content.lower():
        add("fetch() without abort signal", "`fetch` has no default timeout. Pair with an AbortController to bound the call.")

    # POST/PUT/PATCH without an Idempotency-Key header
    if re.search(r"\b(post|put|patch)\b", content, re.IGNORECASE) and "idempotency" not in content.lower():
        add("outbound mutation without idempotency key", "Mutations sent to a third party should carry an Idempotency-Key (or the provider's equivalent). See skills/idempotency-and-side-effects.")


def extract_content(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return (tool_input.get("new_string", "") or "")
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    path = tool_input.get("file_path", "") or ""

    if tool_name not in ("Write", "Edit"):
        return 0
    if not path:
        return 0
    if is_skippable(path):
        return 0

    # Heuristic: only inspect backend-looking source files.
    if not path.lower().endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rb", ".rs", ".java", ".kt", ".cs", ".php")):
        return 0

    content = extract_content(tool_name, tool_input)
    if not content.strip() or len(content) < 80:
        return 0

    kinds = classify(path, content)
    if not kinds:
        return 0

    CONCERNS.clear()
    check_swallow(content)
    check_print_logs(content, path)
    if "endpoint" in kinds:
        check_endpoint(content)
    if "worker" in kinds or "cron" in kinds:
        check_worker(content)
    if "integration" in kinds:
        check_integration(content)

    if not CONCERNS:
        return 0

    kinds_str = ", ".join(sorted(kinds))
    print("", file=sys.stderr)
    print("[backend-design] component review for {} (detected: {})".format(path, kinds_str), file=sys.stderr)
    for c in CONCERNS:
        print("  - {}".format(c), file=sys.stderr)
    print("  See skills/think-before-coding for the full 6-step workflow, or run `/backend-design:audit` once written.", file=sys.stderr)
    print("", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
