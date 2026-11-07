.PHONY: backend-install backend-run backend-health

backend-install:
	cd backend && python -m pip install -e .

backend-run:
	cd backend && uvicorn app.main:app --reload --port 8000

backend-health:
	curl --fail http://localhost:8000/api/health
