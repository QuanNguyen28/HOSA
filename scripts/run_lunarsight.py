"""Run the HOSA data pipeline from an HOSA checkout."""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "v0.2.0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Require an exact match in the local source cache.")
    parser.add_argument("--site01-only", action="store_true", help="Run Connecting Ridge only.")
    parser.add_argument(
        "--nasa-dir", type=Path, default=REPO_ROOT / "data/raw/nasa",
        help="Directory with NASA files and their adjacent receipt JSONs.",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(REPO_ROOT))
    from backend.app.services.lunarsight.pipeline import run

    cache = REPO_ROOT / "data/cache/lunarsight"
    runs = cache / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=runs))
    shutil.copytree(REPO_ROOT / "manifests/lunarsight/config", run_dir / "config")
    shutil.copytree(cache / SNAPSHOT / "raw/horizons", run_dir / "raw/horizons")
    print(f"HOSA run directory: {run_dir}", flush=True)
    status = run(
        run_dir, repository_root=REPO_ROOT, nasa_dir=args.nasa_dir.resolve(),
        offline=args.offline, site01_only=args.site01_only,
    )
    site01_passed = status["steps"]["Site01_pipeline"]["status"] == "PASS"
    return 0 if status["pipeline_status"] == "PASS" or (args.site01_only and site01_passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
