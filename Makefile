# Makefile for loop-engine.
# Every run target activates the virtualenv, then runs the code inside it.
#
# Quick start:
#   make setup            # create the venv + install (first time only)
#   make check-good       # run the example checks / scan
#   make check-bad
#   make scan-example
#
# Run on YOUR input:
#   make check FILE=my_candidate.json
#   make check FILE=my_candidate.json GENRE=sleepcast
#   make scan  FILE=my_script.txt
#   make run   ARGS="check my_candidate.json --json"
#
# Housekeeping:
#   make clean            # delete the venv + build artifacts

VENV        := .venv
ACTIVATE    := . $(VENV)/bin/activate
PYTHON      := python3

# Optional variables you can override on the command line.
FILE  ?=
GENRE ?=
ARGS  ?=
GENRE_FLAG := $(if $(GENRE),--genre $(GENRE),)

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Environment setup — the venv is (re)built whenever this marker is missing.
# ---------------------------------------------------------------------------
$(VENV)/bin/activate:
	@echo "[make] Creating virtualenv in $(VENV) ..."
	$(PYTHON) -m venv $(VENV)
	@echo "[make] Installing loop-engine ..."
	$(ACTIVATE) && pip install --quiet --upgrade pip setuptools
	$(ACTIVATE) && pip install --quiet -e .
	@echo "[make] Setup complete."

.PHONY: setup
setup: $(VENV)/bin/activate ## Create the venv and install the package
	@echo "[make] Environment ready. Try: make check-good"

# ---------------------------------------------------------------------------
# Run targets — each activates the env, then runs the code in that env.
# ---------------------------------------------------------------------------
.PHONY: check
check: $(VENV)/bin/activate ## Check YOUR candidate: make check FILE=my_candidate.json [GENRE=sleepcast]
	@test -n "$(FILE)" || { echo "error: pass FILE=path/to/candidate.json"; exit 2; }
	$(ACTIVATE) && loop-engine check $(FILE) $(GENRE_FLAG)

.PHONY: scan
scan: $(VENV)/bin/activate ## Scan YOUR raw script: make scan FILE=my_script.txt
	@test -n "$(FILE)" || { echo "error: pass FILE=path/to/script.txt"; exit 2; }
	$(ACTIVATE) && loop-engine scan $(FILE)

.PHONY: run
run: $(VENV)/bin/activate ## Run arbitrary CLI args: make run ARGS="check f.json --json"
	$(ACTIVATE) && loop-engine $(ARGS)

# ---------------------------------------------------------------------------
# Example shortcuts.
# ---------------------------------------------------------------------------
.PHONY: check-good
check-good: $(VENV)/bin/activate ## Check the passing example candidate
	$(ACTIVATE) && loop-engine check examples/candidate.good.json

.PHONY: check-bad
check-bad: $(VENV)/bin/activate ## Check the failing example candidate
	$(ACTIVATE) && loop-engine check examples/candidate.bad.json

.PHONY: scan-example
scan-example: $(VENV)/bin/activate ## Scan the example raw script
	$(ACTIVATE) && loop-engine scan examples/raw_script.txt

# ---------------------------------------------------------------------------
# Housekeeping.
# ---------------------------------------------------------------------------
.PHONY: clean
clean: ## Remove the venv and build artifacts
	rm -rf $(VENV) build *.egg-info loop_engine/__pycache__

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
