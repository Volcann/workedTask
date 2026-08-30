-include .env

SHELL := /bin/bash
VENV := .venv
PYTHON := $(if $(wildcard $(VENV)/bin/python3),$(VENV)/bin/python3,python3)
CLI := $(if $(wildcard $(VENV)/bin/status-reporter),$(VENV)/bin/status-reporter,$(PYTHON) -m status_reporter)

DATE ?= today
PROJECT ?=
CATEGORY ?=
REPO ?=
OUTPUT ?=
MODEL ?= gemini-2.5-flash-lite

.PHONY: help status run today yesterday demo demo1 demo2 demo3 test lint format projects clean clean-reports

help:
	@printf "\n"
	@printf "\033[1;34m  GitHub Daily Status Reporter CLI\033[0m\n"
	@printf "\033[90m  ─────────────────────────────────────────────────────────────────\033[0m\n"
	@printf "\n"
	@printf "\033[1;33m  GENERATE STATUS REPORT FOR A SPECIFIC DATE\033[0m\n"
	@printf "  \033[32mmake status DATE=11-SEP-2026\033[0m               Generate report for a specific day\n"
	@printf "  \033[32mmake run DATE=16-SEP-2026\033[0m                  Alias for make status\n"
	@printf "  \033[32mmake today\033[0m                                 Generate report for today\n"
	@printf "  \033[32mmake yesterday\033[0m                             Generate report for yesterday\n"
	@printf "\n"
	@printf "\033[1;33m  OPTIONAL PARAMETERS\033[0m\n"
	@printf "  \033[32mmake status DATE=11-SEP-2026 PROJECT=HR-Tool\033[0m   Filter by project\n"
	@printf "  \033[32mmake status DATE=11-SEP-2026 CATEGORY=Backend\033[0m Filter by category\n"
	@printf "  \033[32mmake status DATE=11-SEP-2026 OUTPUT=out.txt\033[0m   Save to custom file\n"
	@printf "  \033[32mmake status DATE=11-SEP-2026 NO_AI=1\033[0m          Run offline without AI\n"
	@printf "\n"
	@printf "\033[1;33m  CANONICAL DEMOS\033[0m\n"
	@printf "  \033[32mmake demo1\033[0m                                 Run Example 1 (11-SEP-2026)\n"
	@printf "  \033[32mmake demo2\033[0m                                 Run Example 2 (16-SEP-2026)\n"
	@printf "  \033[32mmake demo3\033[0m                                 Run Example 3 (22-SEP-2026)\n"
	@printf "\n"
	@printf "\033[1;33m  PROJECT MANAGEMENT & TESTING\033[0m\n"
	@printf "  \033[32mmake projects\033[0m                              List all configured projects\n"
	@printf "  \033[32mmake test\033[0m                                  Run pytest suite\n"
	@printf "  \033[32mmake lint\033[0m                                  Run ruff linter and format check\n"
	@printf "  \033[32mmake format\033[0m                                Auto-format code with ruff\n"
	@printf "  \033[32mmake clean-reports\033[0m                         Remove unused reports (keeps active report)\n"
	@printf "  \033[32mmake clean-reports ALL=1\033[0m                   Remove all generated reports\n"
	@printf "  \033[32mmake clean-reports KEEP=24-SEP-2026\033[0m        Keep specific report and remove others\n"
	@printf "  \033[32mmake clean\033[0m                                 Clean temporary cache and build files\n"
	@printf "\n"

status:
	@ARGS="--date $(DATE)"; \
	if [ -n "$(PROJECT)" ]; then ARGS="$$ARGS --project '$(PROJECT)'"; fi; \
	if [ -n "$(CATEGORY)" ]; then ARGS="$$ARGS --category '$(CATEGORY)'"; fi; \
	if [ -n "$(REPO)" ]; then ARGS="$$ARGS --repo '$(REPO)'"; fi; \
	if [ -n "$(OUTPUT)" ]; then ARGS="$$ARGS --output '$(OUTPUT)'"; fi; \
	if [ -n "$(NO_AI)" ]; then ARGS="$$ARGS --no-ai"; else ARGS="$$ARGS --model $(MODEL)"; fi; \
	$(CLI) $$ARGS

run: status

today:
	@$(MAKE) status DATE=today

yesterday:
	@$(MAKE) status DATE=yesterday

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

