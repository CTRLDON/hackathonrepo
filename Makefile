.PHONY: up down demo export test check payment-test prompts redteam

up:
	docker compose up --build

down:
	docker compose down

test:
	pytest -q tests/

demo:
	python scripts/run_demo.py

export:
	python scripts/export_decision_log.py

# MOCKED sale to cash: writes outputs/payment_test_log.md
payment-test:
	python scripts/run_payment_test.py

# Mirror every agent system prompt into prompts/
prompts:
	python scripts/export_prompts.py

# Attack our own guardrails with evals/trick_prompts.json
redteam:
	pytest -q tests/test_guardrails.py tests/test_trust_center.py

check:
	@echo "== syntax =="; python -m py_compile backend/*.py services/*.py agents/*.py
	@echo "== tests ==";  pytest -q tests/
