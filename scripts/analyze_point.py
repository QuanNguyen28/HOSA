"""Run the same coordinate pipeline as the HTTP API and save a JSON result."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    from filelock import FileLock
    from app.core.errors import DomainError
    from app.point_analysis.models import PointAnalysisRequest
    from app.point_analysis.pipeline import PointAnalysisPipeline, atomic_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True, help='JSON matching PointAnalysisRequest')
    parser.add_argument('--output', type=Path, help='Also write the full result to this JSON path')
    args = parser.parse_args()
    request = PointAnalysisRequest.model_validate_json(args.request.read_text(encoding='utf-8'))
    root = ROOT / 'data/cache/point-analysis'
    root.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(root / 'pipeline.lock')):
            result = PointAnalysisPipeline(root).run(request, lambda stage: print(stage, flush=True))
    except DomainError as error:
        print(error.code, file=sys.stderr)
        return 1
    if args.output:
        atomic_json(args.output, result)
    print(json.dumps({key: result[key] for key in ('result_id', 'coordinate', 'decision', 'metrics_hours', 'coverage')},
                     ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
