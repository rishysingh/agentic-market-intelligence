.PHONY: help setup test test-unit test-integration test-security test-e2e ingest train backtest run-api run-frontend tf-validate clean

PYTHON := .venv/bin/python3

help:
	@echo "Agentic Market Intelligence Platform — Make Targets:"
	@echo "  make setup            - Create Python venv and install dependencies"
	@echo "  make ingest           - Run BigQuery schema creation, historical backfill, and DQ validation"
	@echo "  make train            - Train & calibrate 1d, 5d, 20d quantitative forecasting models"
	@echo "  make backtest         - Run chronological walk-forward backtests with transaction costs"
	@echo "  make run-api          - Start Tier 2 FastAPI + Google ADK Agent Backend on port 8080"
	@echo "  make run-frontend     - Start Tier 1 Next.js Financial Terminal Frontend on port 3000"
	@echo "  make test             - Run complete automated test suite (unit, integration, security, e2e)"
	@echo "  make tf-validate      - Validate Terraform infrastructure configuration"

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

ingest:
	PYTHONPATH=. $(PYTHON) -m data.ingestion.pipeline --mode full

train:
	PYTHONPATH=. $(PYTHON) -m models.training.pipeline

backtest:
	PYTHONPATH=. $(PYTHON) -m models.backtesting.engine

run-api:
	PYTHONPATH=. .venv/bin/uvicorn services.api.main:app --host 0.0.0.0 --port 8080 --reload

run-frontend:
	cd apps/frontend && npm run dev

test:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

test-unit:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests/unit -p "test_*.py" -v

test-integration:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests/integration -p "test_*.py" -v

test-security:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests/security -p "test_*.py" -v

test-e2e:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests/end_to_end -p "test_*.py" -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
