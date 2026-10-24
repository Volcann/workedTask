-include .env

SHELL := /bin/bash
VENV := .venv
PYTHON := $(if $(wildcard $(VENV)/bin/python3),$(VENV)/bin/python3,python3)
CLI := $(if $(wildcard $(VENV)/bin/worked-task),$(VENV)/bin/worked-task,$(PYTHON) -m src)

DATE ?= today
PROJECT ?=
CATEGORY ?=
REPO ?=
OUTPUT ?=
MODEL ?= gemini-2.5-flash-lite

.PHONY: help extract status run today yesterday demo demo1 demo2 demo3 test lint format projects clean clean-reports

help:
	@printf "\n"
	@printf "\033[1;34m  GitHub Daily Activity Extractor CLI\033[0m\n"
	@printf "\033[90m  ─────────────────────────────────────────────────────────────────\033[0m\n"
	@printf "\n"
	@printf "\033[1;33m  EXTRACT DAILY DEVELOPER ACTIVITY\033[0m\n"
	@printf "  \033[32mmake extract DATE=2026-10-21\033[0m               Extract activity for a specific day\n"
	@printf "  \033[32mmake extract\033[0m                               Extract activity for today\n"
	@printf "  \033[32mmake run DATE=2026-10-21\033[0m                   Alias for make extract\n"
	@printf "  \033[32mmake today\033[0m                                 Extract activity for today\n"
	@printf "  \033[32mmake yesterday\033[0m                             Extract activity for yesterday\n"
	@printf "\n"
	@printf "\033[1;33m  TESTING & CODE QUALITY\033[0m\n"
	@printf "  \033[32mmake test\033[0m                                  Run pytest suite\n"
	@printf "  \033[32mmake lint\033[0m                                  Run ruff linter and format check\n"
	@printf "  \033[32mmake format\033[0m                                Auto-format code with ruff\n"
	@printf "  \033[32mmake clean\033[0m                                 Clean temporary cache and build files\n"
	@printf "\n"

extract:
	@PYTHONPATH=. $(PYTHON) src/extractors/daily_activity_extractor.py $(DATE)

run: extract

status: extract

today:
	@$(MAKE) extract DATE=today

yesterday:
	@$(MAKE) extract DATE=yesterday

demo1:
	@$(CLI) --demo 1

demo2:
	@$(CLI) --demo 2

demo3:
	@$(CLI) --demo 3

demo:
	@$(CLI) --demo $(if $(DEMO),$(DEMO),1)

projects:
	@$(CLI) projects list

test:
	@$(PYTHON) -m pytest

lint:
	@$(PYTHON) -m ruff check .
	@$(PYTHON) -m ruff format --check .

format:
	@$(PYTHON) -m ruff check --fix .
	@$(PYTHON) -m ruff format .

clean:
	@rm -rf .pytest_cache .ruff_cache build/ dist/ *.egg-info
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@printf "\033[32mCleaned temporary files.\033[0m\n"

clean-reports:
	@ARGS="clean-reports"; \
	if [ -n "$(ALL)" ]; then ARGS="$$ARGS --all"; \
	elif [ -n "$(KEEP)" ]; then ARGS="$$ARGS --keep '$(KEEP)'"; \
	elif [ -n "$(DATE)" ] && [ "$(DATE)" != "today" ]; then ARGS="$$ARGS --keep '$(DATE)'"; fi; \
	$(CLI) $$ARGS

