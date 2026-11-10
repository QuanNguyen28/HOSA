"""Derive sampled Earth visibility windows from existing backend output only.

Uses the shared standard-library contact module; no DEM reads, Horizons calls, or third-party dependencies.
Import ``analyze_contacts`` to use the same postprocessor from another client.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.lunarsight.contact_windows import (
    METHOD_VERSION, STATES, aggregate, analyze_contacts, iso, longest, minimum_check,
    minutes, normalize, number, runs, timestamp,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Full backend JSON result or native interval CSV; - reads JSON from stdin")
    source.add_argument("--url", help="GET an existing point-analysis result URL (does not submit a new job)")
    parser.add_argument("--output", type=Path, help="Write JSON to this file instead of stdout")
    parser.add_argument("--start-utc", help="Optional subwindow start, timezone required")
    parser.add_argument("--end-utc", help="Optional subwindow end, timezone required")
    parser.add_argument("--min-contact-minutes", type=float)
    parser.add_argument("--setup-minutes", type=float, default=0.)
    parser.add_argument("--required-windows", type=int)
    parser.add_argument("--first-contact-deadline-minutes", type=float)
    parser.add_argument("--max-gap-minutes", type=float)
    args = parser.parse_args(argv)
    try:
        if args.url:
            if not args.url.startswith(("http://", "https://")):
                raise ValueError("--url requires an HTTP(S) result URL")
            with urlopen(args.url, timeout=30) as response:
                raw = response.read()
        else:
            raw = sys.stdin.buffer.read() if args.input == "-" else Path(args.input).read_bytes()
        if args.input and args.input != "-" and Path(args.input).suffix.lower() == ".csv":
            payload = {"timeline": list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))}
        else:
            payload = json.loads(raw)
        result = analyze_contacts(payload, start_utc=args.start_utc, end_utc=args.end_utc,
            min_contact_minutes=args.min_contact_minutes, setup_minutes=args.setup_minutes,
            required_windows=args.required_windows, first_contact_deadline_minutes=args.first_contact_deadline_minutes,
            max_gap_minutes=args.max_gap_minutes)
        result["source"].update({"location": args.url or args.input, "sha256": hashlib.sha256(raw).hexdigest()})
        output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        parser.exit(2, f"contact_windows: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
