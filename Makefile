# Two targets, both deterministic: what they write is compared byte for byte in CI.
# Makefile deliberately minimal — the project builds with `starter.py`, `uv` and `npm`, not make.

PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: starter-template help

help:
	@echo "make starter-template   render bizview-starter-template.zip at the repository root"

starter-template:
	$(PY) scripts/build_starter_template.py
