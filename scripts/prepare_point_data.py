"""Install official NASA DEMs and adjacent receipts for coordinate analysis."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    from app.services.lunarsight.acquire import download, sources
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datasets', nargs='+', choices=['Site01_dem', 'Site04_dem', 'dem80', 'dem240'],
                        default=['Site01_dem', 'Site04_dem', 'dem80', 'dem240'])
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    directory = ROOT / 'data/raw/nasa'
    for item in sources():
        if item['id'] in args.datasets:
            print('Preparing', item['id'], flush=True)
            receipt = download(directory, item, args.offline)
            print(item['id'], receipt['status'], receipt['bytes'], receipt['sha256'], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
