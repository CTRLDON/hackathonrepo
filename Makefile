.PHONY: setup up down demo export test check payment-test prompts redteam

# Local virtualenv for running tests and scripts outside Docker (`make setup` once).
VENV := .venv
PY := $(shell [ -x $(VENV)/bin/python ] && echo $(VENV)/bin/python || echo python3)

setup:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -r requirements.txt
	@echo "Ready: run 'make test'"

up:
	docker compose up --build

down:
	docker compose down

test:
	@$(PY) -c "import pytest, fastapi" 2>/dev/null || { echo "Dependencies missing: run 'make setup' first."; exit 1; }
	$(PY) -m pytest -q tests/

demo:
	$(PY) scripts/run_demo.py

export:
	$(PY) scripts/export_decision_log.py

# MOCKED sale to cash: writes outputs/payment_test_log.md
payment-test:
	$(PY) scripts/run_payment_test.py

# Mirror every agent system prompt into prompts/
prompts:
	$(PY) scripts/export_prompts.py

# Attack our own guardrails with evals/trick_prompts.json
redteam:
	$(PY) -m pytest -q tests/test_guardrails.py tests/test_trust_center.py

check:
	@echo "== syntax =="; $(PY) -m py_compile backend/*.py services/*.py agents/*.py
	@echo "== tests ==";  $(PY) -m pytest -q tests/
