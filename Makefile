.PHONY: backend-install backend-run backend-health frontend-install frontend-run data-plan data-acquire data-verify data-sites data-windows-plan test verify release-audit release-check package-release

backend-install:
	python3 -m venv backend/.venv
	backend/.venv/bin/python -m pip install -e 'backend[test]'

backend-run:
	backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

backend-health:
	curl --fail http://localhost:8000/api/health

frontend-install:
	cd frontend && npm ci

frontend-run:
	cd frontend && npm run dev

data-plan:
	backend/.venv/bin/python scripts/acquire_full_product_data.py --dry-run

data-acquire:
	backend/.venv/bin/python scripts/acquire_full_product_data.py

data-verify:
	backend/.venv/bin/python scripts/acquire_full_product_data.py --verify

data-sites:
	backend/.venv/bin/python scripts/build_official_site_catalog.py

.PHONY: ephemeris-prepare
ephemeris-prepare:
	PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_shared_ephemeris.py

.PHONY: precompute-catalog
precompute-catalog:
	PYTHONPATH=backend backend/.venv/bin/python scripts/precompute_catalog.py --workers 2 --report docs/validation/lunarsight/catalog-precompute-build.json

.PHONY: physics-prepare
physics-prepare:
	PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_physical_series.py --report docs/validation/lunarsight/physical-series-build.json

.PHONY: metrics-prepare
metrics-prepare:
	PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_metric_indexes.py --report docs/validation/lunarsight/metrics-index-build.json

.PHONY: metrics-century-prepare
metrics-century-prepare:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_long_range_metrics.py --viewer-heights 2 10 20 30 --workers 3 --report docs/validation/lunarsight/viewer-metrics-build.json

.PHONY: viewer-horizons-prepare
viewer-horizons-prepare:
	PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_viewer_horizons.py --workers 1 --report docs/validation/lunarsight/viewer-horizons-build.json

data-windows-plan:
	backend/.venv/bin/python scripts/materialize_dem_windows.py --dry-run

test:
	PYTHONPATH=. backend/.venv/bin/pytest -q

verify: test
	cd frontend && npm run test
	cd frontend && npm run typecheck
	cd frontend && npm run build

release-audit:
	backend/.venv/bin/python scripts/release_audit.py --output docs/validation/lunarsight/v0.2.0/reports/release_audit.json

release-check: verify release-audit

package-release:
	backend/.venv/bin/python scripts/package_release.py

.PHONY: mvp-smoke
mvp-smoke:
	backend/.venv/bin/python scripts/verify_mvp_api.py
