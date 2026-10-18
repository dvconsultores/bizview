"""Feature 020 T022: legacy reader and version projects."""

from types import SimpleNamespace

import yaml

from app.projects.compose import LEGACY_PROJECT_YAML, legacy_tree, version_projects


def _make_v1():
    artifacts = {
        "integrations": {
            "facturas": {
                "definition": {"id": "facturas", "spec": "specs/integrations/001-facturas",
                               "source": "origen"},
                "files": {"queries/facturas.sql": "select 1"},
            }
        },
        "reports": {
            "facturas-dia": {
                "definition": {"id": "facturas-dia", "spec": "specs/reports/001-facturas-dia"}
            }
        },
    }
    specs = {
        "integrations/facturas": {
            "folder": "specs/integrations/001-facturas",
            "documents": {
                "spec.md": "# F\n\n**Spec type**: integration\n\n**Status**: Approved\n",
                "plan.md": "p",
                "tasks.md": "t",
            },
        },
        "reports/facturas-dia": {
            "folder": "specs/reports/001-facturas-dia",
            "documents": {"spec.md": "# R\n\n**Spec type**: report\n", "plan.md": "p",
                          "tasks.md": "t"},
        },
    }
    return SimpleNamespace(artifacts=artifacts, specs=specs, projects={})


def _make_v2():
    artifacts = {
        "integrations": {
            "x": {"definition": {"id": "x"}, "files": {"queries/a.sql": "q"},
                  "project": "ventas", "source": "id: x\n"}
        },
        "reports": {},
        "distributions": {"d": {"definition": {"id": "d"}, "project": "ventas"}},
    }
    specs = {"ventas/specs/001-x": {"documents": {"spec.md": "s"}}}
    projects = {"ventas": {"project_yaml": "name: Ventas\nslug: ventas\n"}}
    return SimpleNamespace(artifacts=artifacts, specs=specs, projects=projects)


def test_legacy_tree():
    version = _make_v1()
    tree = legacy_tree(version)
    for path in ("specs/001-facturas/spec.md", "specs/002-facturas-dia/spec.md",
                 "integrations/facturas/integration.yaml",
                 "integrations/facturas/queries/facturas.sql",
                 "reports/facturas-dia/report.yaml"):
        assert path in tree
    lines = tree["specs/001-facturas/spec.md"].splitlines()
    type_idx = next(i for i, line in enumerate(lines) if line.startswith("**Spec type**"))
    assert lines[type_idx + 2] == "**Tipo**: integracion"
    loaded = yaml.safe_load(tree["integrations/facturas/integration.yaml"])
    assert loaded["spec"] == "specs/001-facturas"
    assert legacy_tree(version) == tree
    assert version_projects(version) == {"principal": {**tree,
                                                       "project.yaml": LEGACY_PROJECT_YAML}}


def test_legacy_tree_without_documents_keeps_artifacts():
    version = _make_v1()
    version.specs = {}
    tree = legacy_tree(version)
    assert "integrations/facturas/integration.yaml" in tree


def test_version_projects_multi():
    result = version_projects(_make_v2())
    assert list(result) == ["ventas"]
    tree = result["ventas"]
    assert "project.yaml" in tree
    assert "specs/001-x/spec.md" in tree
    assert tree["integrations/x/integration.yaml"] == "id: x\n"
    assert "integrations/x/queries/a.sql" in tree
    assert "distributions/d.yaml" in tree
