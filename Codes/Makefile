# Pratifalan: one entry point for setup, data, experiments, tests and the demo.
#
#   make install      # backend venv + frontend node_modules
#   make reproduce    # data -> prior -> stage1 -> experiments -> meal-photo -> agent-suite -> readme
#   make up           # docker compose (works with an empty .env, offline demo mode)
#
# Note on caching: stage 1 replays are cached per configuration in backend/data/cache/.
# A fresh clone has no cache, so `make reproduce` recomputes everything. After changing
# twin code, remove the affected backend/data/cache/<config>-<hash>/ folders by hand.

SHELL := /bin/bash
.DEFAULT_GOAL := help

ROOT     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND  := $(ROOT)/backend
FRONTEND := $(ROOT)/frontend
VENV     := $(BACKEND)/.venv

# Use the backend venv when it exists, otherwise whatever python3 is on PATH (e.g. in CI).
ifneq ($(wildcard $(VENV)/bin/python),)
  PY  := $(VENV)/bin/python
  BIN := $(VENV)/bin/
else
  PY  := python3
  BIN :=
endif
PYTHON_BOOT ?= python3.11

API_PORT ?= 8000
WEB_PORT ?= 8080

# Run a python module from backend/ (so pratifalan/config.py finds data/, artifacts/, reports/).
RUN = cd $(BACKEND) && $(PY) -m

.PHONY: help install install-backend install-web data prior stage1 experiments meal-photo \
        agent-suite readme reproduce personas record-fixtures test test-backend test-web \
        lint typecheck dev-api dev-web build-web up down logs secrets-scan

help: ## List targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------- setup
install: install-backend install-web ## Create backend venv and install backend + frontend deps

install-backend:
	@if [ ! -x "$(VENV)/bin/python" ]; then $(PYTHON_BOOT) -m venv $(VENV); fi
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e "$(BACKEND)[dev]"

install-web:
	cd $(FRONTEND) && npm ci

# ----------------------------------------------------------------------------- data + experiments
data: ## Download CGMacros + ShanghaiT2DM and harmonise to data/processed (never committed)
	$(RUN) pratifalan.data.download
	$(RUN) pratifalan.data.harmonise

prior: ## Fit the EHR-conditioned population prior (artifacts/prior_*.json)
	$(RUN) pratifalan.twin.prior

stage1: ## Replay every patient through the twin for every experiment config (cached)
	$(RUN) pratifalan.eval.stage1

experiments: ## Hybrid layer + all experiment reports (reports/*.json, reports/figures)
	$(RUN) pratifalan.eval.experiments

meal-photo: ## Experiment 7: vision carb error on CGMacros photos (first run: APP_MODE=live make meal-photo; vision results are cached)
	$(RUN) pratifalan.eval.meal_photo

agent-suite: ## Agent grounding + safety suite (100% grounding or template fallback; zero dose advice)
	$(RUN) pratifalan.eval.agent_suite

readme: ## Inject results tables from reports/*.json into README.md
	$(PY) $(ROOT)/scripts/build_readme.py

reproduce: ## Regenerate every report and figure from raw data
	$(MAKE) data
	$(MAKE) prior
	$(MAKE) stage1
	$(MAKE) experiments
	$(MAKE) meal-photo
	$(MAKE) agent-suite
	$(MAKE) readme

personas: ## Export demo series (artifacts/demo_*.parquet) and warm persona replay states
	$(RUN) pratifalan.twin.export_demo
	cd $(BACKEND) && $(PY) -c "from pratifalan.twin.engine import get_engine; get_engine().warm(); print('persona states warm')"

record-fixtures: ## Record LLM/vision/speech fixtures for offline demo mode (needs keys in .env)
	cd $(BACKEND) && APP_MODE=live $(PY) -m pratifalan.record_fixtures

# ----------------------------------------------------------------------------- quality
test: test-backend test-web ## Run backend and frontend tests

test-backend:
	@if [ -d "$(BACKEND)/tests" ]; then cd $(BACKEND) && $(BIN)pytest; else echo "no backend/tests yet"; fi

test-web:
	cd $(FRONTEND) && npm test

lint: ## ruff + eslint
	cd $(BACKEND) && $(BIN)ruff check pratifalan $$( [ -d tests ] && echo tests )
	cd $(FRONTEND) && npm run lint

typecheck: ## mypy (config in pyproject) + tsc
	cd $(BACKEND) && $(BIN)mypy
	cd $(FRONTEND) && npx tsc -b

secrets-scan: ## gitleaks over the git history (needs gitleaks on PATH; pre-commit scans staged files)
	cd $(ROOT) && gitleaks git --config .gitleaks.toml --redact .

# ----------------------------------------------------------------------------- run
dev-api: ## FastAPI with reload on API_PORT (default 8000)
	cd $(BACKEND) && $(BIN)uvicorn pratifalan.api.main:app --reload --host 127.0.0.1 --port $(API_PORT)

dev-web: ## Vite dev server (port 5180, proxies /api to VITE_API_TARGET)
	cd $(FRONTEND) && npm run dev

build-web: ## Production build of the frontend (frontend/dist)
	cd $(FRONTEND) && npm run build

up: ## docker compose up --build (db + api + web); open http://localhost:$(WEB_PORT)
	cd $(ROOT) && WEB_PORT=$(WEB_PORT) API_PORT=$(API_PORT) docker compose up --build -d
	@echo "Pratifalan: http://localhost:$(WEB_PORT)  (API http://localhost:$(API_PORT)/api/health)"

down: ## Stop the compose stack (keeps the database volume)
	cd $(ROOT) && docker compose down

logs: ## Follow compose logs
	cd $(ROOT) && docker compose logs -f
