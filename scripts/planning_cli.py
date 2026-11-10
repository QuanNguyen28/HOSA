"""Headless planning with explicit inputs; no LLM or API key required."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))

import httpx
from pydantic import ValidationError

from app.core.errors import DomainError
from app.planning.models import CompareRequest, SearchRequest
from app.planning.repository import result_csv
from app.planning.service import PlanningService


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    for command in ("capabilities", "compare", "search", "export"):
        sub = commands.add_parser(command)
        sub.add_argument("--base-url", help="HTTP server URL, e.g. http://127.0.0.1:8000; omit to call the service locally")
        sub.add_argument("--output", type=Path, help="Write the result to this file; default is stdout")
        if command == "capabilities":
            continue
        sub.add_argument("--format", choices=("json", "csv"), default="json")
        if command == "export":
            sub.add_argument("result_id")
            continue
        sub.add_argument("--request", help="JSON request file, or - for stdin; cannot be mixed with input flags")
        sub.add_argument("--scenario-id")
        sub.add_argument("--sites", nargs="+", dest="site_ids")
        sub.add_argument("--arrival", dest="arrival_utc", help="ISO 8601 timestamp with explicit timezone")
        sub.add_argument("--max-darkness-hours", type=float, help="Optional soft preference: maximum continuous darkness")
        sub.add_argument("--max-earth-blackout-hours", type=float, help="Optional soft preference: maximum continuous loss of Earth LOS")
        sub.add_argument("--min-sunlit-fraction", type=float, help="Required hard minimum Sun-visible fraction, in [0,1]")
        sub.add_argument("--min-earth-los-fraction", type=float, help="Required hard minimum Earth-LOS fraction, in [0,1]")
        sub.add_argument("--duration-hours", type=float)
        sub.add_argument("--sun-panel-height-m", type=float)
        sub.add_argument("--earth-antenna-height-m", type=float)
        sub.add_argument("--rank-by", choices=("total_earth_los_hours", "total_sun_hours", "longest_dark_hours", "longest_blackout_hours", "longest_joint_hours"))
        sub.add_argument("--current-site-id")
        sub.add_argument("--expected-source-hash")
        if command == "search":
            sub.add_argument("--until", dest="until_utc", help="Exclusive end of the allowed start-time range")
            sub.add_argument("--max-results", type=int)
            sub.add_argument("--allow-overlap", action="store_true", default=None)
    return cli


def request(args):
    excluded = {"command", "base_url", "output", "format", "request"}
    inputs = {k: v for k, v in vars(args).items() if k not in excluded and v is not None}
    if args.request:
        if inputs:
            raise ValueError("--request cannot be mixed with input flags")
        payload = json.loads(sys.stdin.read() if args.request == "-" else Path(args.request).read_text(encoding="utf-8"))
    else:
        required = ("site_ids", "arrival_utc", "min_sunlit_fraction", "min_earth_los_fraction")
        if args.command == "search":
            required += ("until_utc",)
        missing = [k for k in required if k not in inputs]
        if missing:
            raise ValueError("Missing input: " + ", ".join(missing))
        payload = {"scenario_id": "south_pole_demo_v1", **inputs}
        payload["constraints"] = {k: payload.pop(k) for k in ("max_darkness_hours", "max_earth_blackout_hours") if k in payload}
        hardware = [payload.pop(k, None) for k in ("sun_panel_height_m", "earth_antenna_height_m")]
        if any(v is not None for v in hardware):
            if any(v is None for v in hardware):
                raise ValueError("Specify both device heights")
            payload["hardware"] = dict(zip(("sun_panel", "earth_antenna"), hardware))
        if "allow_overlap" in payload:
            payload["non_overlapping"] = not payload.pop("allow_overlap")
    contract = SearchRequest if args.command == "search" else CompareRequest
    return contract.model_validate(payload)


def remote(args, query):
    # The CLI is a thin client of the existing deterministic HTTP API.
    with httpx.Client(base_url=args.base_url.rstrip("/")+"/", timeout=60, follow_redirects=False) as client:
        if args.command == "capabilities":
            response = client.get("api/planning/capabilities")
        elif args.command == "export":
            response = client.get(f"api/planning/results/{args.result_id}", params={"format": args.format})
        else:
            endpoint = "compare" if args.command == "compare" else "windows/search"
            response = client.post(f"api/planning/{endpoint}", json=query.model_dump())
            response.raise_for_status()
            if args.format == "csv":
                response = client.get(f"api/planning/results/{response.json()['result_id']}", params={"format": "csv"})
        response.raise_for_status()
        return response.text if getattr(args, "format", "json") == "csv" else json.dumps(response.json(), ensure_ascii=False, indent=2)


def main(argv=None, *, service=None):
    args = parser().parse_args(argv)
    try:
        query = request(args) if args.command in ("compare", "search") else None
        if args.base_url:
            content = remote(args, query)
        else:
            planner = service or PlanningService()
            if args.command == "capabilities":
                content = json.dumps(planner.capabilities(), ensure_ascii=False, indent=2)
            else:
                result = planner.results.load(args.result_id) if args.command == "export" else (
                    planner.compare(query) if args.command == "compare" else planner.search(query))
                content = result_csv(result) if args.format == "csv" else result.model_dump_json(indent=2)
        if args.output:
            args.output.write_text(content+"\n" if not content.endswith("\n") else content, encoding="utf-8")
        else:
            print(content, end="" if content.endswith("\n") else "\n")
        return 0
    except (DomainError, ValidationError, ValueError, OSError, httpx.HTTPError) as error:
        code = error.code if isinstance(error, DomainError) else type(error).__name__
        detail = str(error)
        if isinstance(error, httpx.HTTPStatusError):
            try:
                detail = error.response.json()
            except ValueError:
                detail = f"HTTP {error.response.status_code}"
        print(json.dumps({"error": code, "detail": detail}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
