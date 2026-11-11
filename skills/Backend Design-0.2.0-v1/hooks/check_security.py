#!/usr/bin/env python3
"""
Pre-write check for everyday security horrors.

Catches the obvious anti-patterns from the security-discipline skill:
- SQL built with string concat / f-string passed to execute()
- Hard-coded API keys / tokens / secrets
- Secrets, passwords, tokens, full PII in log statements
- TLS verification disabled
- shell=True with variables, eval, exec on input
- Weak crypto (MD5/SHA1 for passwords, Math.random for tokens)
- Bearer tokens in URLs
- CORS with `*` and credentials

Warns to stderr, exits 0 (allow). The point is to flag, not gate.
"""

import json
import os
import re
import sys


SOURCE_EXTENSIONS = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rb", ".rs", ".java", ".kt", ".cs", ".php", ".sql",
)

SKIP_MARKERS = (
    "/test", "/tests/", "_test.", ".test.", ".spec.",
    "/node_modules/", "/.git/", "/dist/", "/build/",
    "/__pycache__/", "/vendor/", "/fixtures/", "/mocks/",
)


def is_skippable(path: str) -> bool:
    p = path.lower().replace("\\", "/")
    return any(m in p for m in SKIP_MARKERS)


SECRET_SHAPES = [
    # Provider-prefixed live keys
    (re.compile(r"sk_live_[0-9a-zA-Z]{16,}"), "Stripe live secret key"),
    (re.compile(r"rk_live_[0-9a-zA-Z]{16,}"), "Stripe live restricted key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"), "Slack token"),
    (re.compile(r"ghp_[0-9a-zA-Z]{30,}"), "GitHub personal access token"),
    (re.compile(r"github_pat_[0-9a-zA-Z_]{30,}"), "GitHub fine-grained PAT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "PEM private key block"),
    # Connection strings with embedded credentials
    (re.compile(r"(?i)(postgres|mysql|mongodb|redis)://[^/\s'\"]+:[^@\s'\"]+@"), "DB URL with embedded credentials"),
    # Generic assignment to a name that smells like a secret with a long literal
    (re.compile(r"""(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{20,}["']"""), "Hard-coded secret literal"),
]


SQL_INJECTION_PATTERNS = [
    (
        re.compile(r"""(?i)(?:\.execute|\.query|cursor\.execute|db\.exec)\s*\(\s*f["']\s*(SELECT|INSERT|UPDATE|DELETE|MERGE)\b"""),
        "SQL built with an f-string in execute/query. Use a parameterized placeholder, not interpolation.",
    ),
    (
        re.compile(r"""(?i)(?:\.execute|\.query|cursor\.execute|db\.exec)\s*\(\s*["'](SELECT|INSERT|UPDATE|DELETE|MERGE)[^"']*["']\s*\+\s*"""),
        "SQL built with string concatenation in execute/query. Use parameters.",
    ),
    (
        re.compile(r"""(?i)(SELECT|INSERT|UPDATE|DELETE)\s+[^"'\n]*["']\s*\+\s*\w+"""),
        "Probable SQL built by string concatenation. Use parameters.",
    ),
]


LOG_LEAK_PATTERNS = [
    (
        re.compile(r"""(?i)\b(?:\w*log\w*|console|pino|winston|structlog|slog|zap|zerolog)\.(?:log|debug|info|warn|warning|error|critical|fatal|trace)\s*\([^)\n]*\b(password|token|secret|api[_-]?key|authorization|cookie|set[_-]?cookie|credit[_-]?card|ssn|pan|cvv|bearer)\b"""),
        "Sensitive field referenced in a log call. Redact or remove before shipping.",
    ),
    (
        re.compile(r"""(?i)\b(?:\w*log\w*|console|pino|winston|structlog|slog|zap|zerolog)\.(?:log|debug|info|warn|warning|error|critical|fatal|trace)\s*\([^)\n]*\b(req(?:uest)?\.(?:body|headers)|request\.json|request\.data)\b"""),
        "Whole request body or headers in a log call. Often captures credentials and PII. Log fields explicitly.",
    ),
]


TLS_DISABLED_PATTERNS = [
    (re.compile(r"\bverify\s*=\s*False\b"), "TLS verification disabled (verify=False). Never in production."),
    (re.compile(r"\brejectUnauthorized\s*:\s*false\b", re.IGNORECASE), "TLS verification disabled (rejectUnauthorized: false). Never in production."),
    (re.compile(r"\bInsecureSkipVerify\s*:\s*true\b"), "TLS verification disabled (InsecureSkipVerify: true). Never in production."),
    (re.compile(r"\bssl\s*\.\s*_create_unverified_context\s*\("), "Unverified TLS context. Never in production."),
]


COMMAND_INJECTION_PATTERNS = [
    (re.compile(r"\bsubprocess\.\w+\([^)\n]*shell\s*=\s*True\b"), "`subprocess` with shell=True. Pass args as a list and drop shell=True, especially with any user input."),
    (re.compile(r"\bos\.system\s*\("), "os.system invokes a shell. Use subprocess with an args list instead."),
    (re.compile(r"(?<!\w)eval\s*\("), "eval on a dynamic string is arbitrary code execution. Replace with explicit parsing."),
    (re.compile(r"(?<!\w)exec\s*\("), "exec on a dynamic string is arbitrary code execution. Replace with explicit parsing."),
    (re.compile(r"\bRuntime\.getRuntime\(\)\.exec\s*\("), "Runtime.exec with concatenated input is a command injection vector."),
]


WEAK_CRYPTO_PATTERNS = [
    (re.compile(r"\bhashlib\.(md5|sha1)\s*\([^)]*password", re.IGNORECASE), "MD5/SHA1 used near `password`. Use bcrypt / argon2 / scrypt for password hashing."),
    (re.compile(r"\bbcrypt\.compare\s*\([^,)]+,\s*[^)]+\)\s*==\s*"), "bcrypt comparison with `==` defeats constant-time. Use the library's compare and trust its boolean."),
    (re.compile(r"\bMath\.random\s*\(\)"), "Math.random is not cryptographically random. Use crypto.randomBytes / crypto.getRandomValues for tokens, nonces, IDs."),
    (re.compile(r"\brandom\.(random|choice|randint)\s*\([^)]*\)\s*(?:#|//)?\s*(?:token|nonce|secret|password)", re.IGNORECASE), "`random` is not cryptographically secure. Use `secrets` (Python) for tokens, nonces, passwords."),
]


URL_TOKEN_PATTERNS = [
    (re.compile(r"""[?&](token|api[_-]?key|access[_-]?token|auth[_-]?token|password)\s*=\s*[^&\s"'<>]+""", re.IGNORECASE), "Token or credential in URL. Use Authorization header instead; URL parameters leak to logs and proxies."),
]


CORS_PATTERNS = [
    (
        re.compile(r"""(?i)access[_-]?control[_-]?allow[_-]?origin["']?\s*[:,]\s*["']?\*"""),
        "CORS `*` origin. With credentials this fails open; even without, prefer an explicit allowlist.",
    ),
    (
        re.compile(r"""(?i)cors\s*\(\s*\{[^}]*origin\s*:\s*["']?\*"""),
        "CORS configured with origin `*`. Use an explicit allowlist.",
    ),
]


REDIRECT_PATTERNS = [
    (re.compile(r"""(?i)\b(res|response|reply)\.redirect\s*\(\s*(req|request)\.(query|body|params)\."""), "Redirecting to a user-supplied URL. Allowlist destinations or strip external."),
]


ALL_RULES = (
    [("secret-shape", p, m) for p, m in SECRET_SHAPES]
    + [("sql-injection", p, m) for p, m in SQL_INJECTION_PATTERNS]
    + [("log-leak", p, m) for p, m in LOG_LEAK_PATTERNS]
    + [("tls-disabled", p, m) for p, m in TLS_DISABLED_PATTERNS]
    + [("command-injection", p, m) for p, m in COMMAND_INJECTION_PATTERNS]
    + [("weak-crypto", p, m) for p, m in WEAK_CRYPTO_PATTERNS]
    + [("token-in-url", p, m) for p, m in URL_TOKEN_PATTERNS]
    + [("cors-wildcard", p, m) for p, m in CORS_PATTERNS]
    + [("open-redirect", p, m) for p, m in REDIRECT_PATTERNS]
)


def extract_content(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string", "") or ""
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
    if not path.lower().endswith(SOURCE_EXTENSIONS):
        return 0

    content = extract_content(tool_name, tool_input)
    if not content.strip():
        return 0

    findings = []
    seen = set()
    for category, pattern, message in ALL_RULES:
        for m in pattern.finditer(content):
            snippet = m.group(0)
            key = (category, snippet[:80])
            if key in seen:
                continue
            seen.add(key)
            findings.append((category, snippet, message))

    if not findings:
        return 0

    print("", file=sys.stderr)
    print("[backend-design] security review for {}".format(path), file=sys.stderr)
    for category, snippet, message in findings:
        first_line = snippet.split("\n", 1)[0]
        if len(first_line) > 90:
            first_line = first_line[:87] + "..."
        print("  - [{}] {}".format(category, message), file=sys.stderr)
        print("    match: {}".format(first_line), file=sys.stderr)
    print("  See: skills/security-discipline. For a full pass, ask the security-reviewer agent.", file=sys.stderr)
    print("", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
