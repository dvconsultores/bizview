"""Applying a project must leave the other projects byte for byte as they were.

`workspace_version.artifacts` used to keep only the parsed definition of each integration and
report, and composing the next version dumped it back with `yaml.safe_dump`: every project that
was not being applied came out reformatted, so its file hashes no longer matched its folder and it
started showing "Cambios sin aplicar" right after somebody else applied (reported 2026-10-25:
applying `coinmarketcap` marked `artemisa` as changed, and the other way round).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from app.projects.compose import version_projects
from app.workspace.service import _artifacts

REPORT_TEXT = """\
id: ventas
spec: specs/001-ventas
# El comentario y el orden son del autor: aplicarlos no puede reescribirlos.
title: "Ventas y facturación"
description: 'Resumen de ventas'
icon: chart-line
uses:
  lines: ventas-prueba.sale_lines
date: lines.local_date
metrics:
  ventas:
    label: Ventas
    format: currency
    sql: sum(lines.net_amount)
periods: {default: mtd, allowed: [mtd]}
views:
  - {type: kpis, metrics: [ventas]}
"""


def _entry(folder: str, kind: str, text: str, files: dict[str, str]) -> SimpleNamespace:
    """What `_artifacts` reads from a validated entry (the CLI's `Entry`)."""
    prefix = f"{folder}/"
    return SimpleNamespace(
        folder=Path(folder), kind=kind, id=Path(folder).name,
        files={f"{prefix}{kind}.yaml": text.encode(),
               **{f"{prefix}{rel}": body.encode() for rel, body in files.items()}},
        artifact=yaml.safe_load(text) or {}, project="demo", spec={}, key=folder,
    )


def _version() -> SimpleNamespace:
    entry = _entry("projects/demo/reports/ventas", "report", REPORT_TEXT, {})
    result = SimpleNamespace(manifest={"name": "Cliente"}, integrations={},
                             reports={entry.id: entry}, distributions={}, layout="v2",
                             projects={"demo": {"specs": {}}})
    artifacts, _specs = _artifacts(result, None)
    return SimpleNamespace(id=1, artifacts=artifacts, specs={},
                           projects={"demo": {"project_id": 1, "name": "demo",
                                              "origin": "app",
                                              "project_yaml": 'name: "demo"\nslug: demo\n'}})


def test_the_version_keeps_the_artifact_text():
    entry = _version().artifacts["reports"]["ventas"]
    assert entry["source"] == REPORT_TEXT
    assert yaml.safe_dump(entry["definition"], sort_keys=False,
                          allow_unicode=True) != REPORT_TEXT       # why the source is needed


def test_composing_replays_the_tree_the_version_stored():
    """The definitive case: every file of the project as it was applied, replayed as it is."""
    version = _version()
    version.projects["demo"]["tree"] = {
        "project.yaml": 'name: "demo"\nslug: demo\n',
        ".specify/memory/constitution.md": "# Constitución\n",
        "reports/ventas/report.yaml": REPORT_TEXT,
    }
    assert version_projects(version)["demo"] == version.projects["demo"]["tree"]


def test_composing_replays_the_artifact_text_instead_of_dumping_it():
    tree = version_projects(_version())["demo"]
    assert tree["reports/ventas/report.yaml"] == REPORT_TEXT


def test_an_artifact_without_source_is_still_composed():
    """Versions applied before this change keep working: the definition is dumped as before."""
    version = _version()
    version.artifacts["reports"]["ventas"].pop("source")
    tree = version_projects(version)["demo"]
    assert tree["reports/ventas/report.yaml"] == yaml.safe_dump(
        version.artifacts["reports"]["ventas"]["definition"], sort_keys=False, allow_unicode=True)
