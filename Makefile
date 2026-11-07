# Deterministic targets: what they write is compared byte for byte in CI.
# Makefile deliberately minimal — the project builds with `starter.py`, `uv` and `npm`, not make.

PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: starter-template check help

help:
	@echo "make starter-template   render bizview-starter-template.zip at the repository root"
	@echo "make check              every gate, plus the English/Spanish document parity"

starter-template:
	$(PY) scripts/build_starter_template.py

check:
	sh scripts/gates/all.sh
	$(PY) scripts/check_docs_parity.py
