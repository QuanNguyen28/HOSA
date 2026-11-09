.PHONY: backend-install backend-run backend-health frontend-install frontend-run test verify release-audit release-check package-release

backend-install:
	cd backend && python -m pip install -e .

backend-run:
	cd backend && uvicorn app.main:app --reload --port 8000

backend-health:
	curl --fail http://localhost:8000/api/health

frontend-install:
	cd frontend && npm install

frontend-run:
	cd frontend && npm run dev

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
