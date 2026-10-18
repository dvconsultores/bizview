"""Feature 020 T021: problem line numbers."""

from app.projects.positions import line_for, markdown_line, problem_line

YAML_DOC = """\
id: facturas
datasets:
  facturas:
    columns:
      fecha: {type: date}
      total:
        type: numeric
views:
  - type: kpis
  - type: trend
"""

MARKDOWN_DOC = """\
# T

**Tipo**: reporte

**Status**: Draft
- [X] a
- [ ] b
"""


def test_line_for_yaml_pointers():
    assert line_for(YAML_DOC, "/id") == 1
    assert line_for(YAML_DOC, "/datasets/facturas/columns/total/type") == 7
    assert line_for(YAML_DOC, "/datasets/facturas/columns/fecha") == 5
    assert line_for(YAML_DOC, "/views/1") == 10
    assert line_for(YAML_DOC, "/views/1/type") == 10
    assert line_for(YAML_DOC, "/datasets/nope") == 2
    assert line_for("a: [", "/a") is None


def test_markdown_line_markers():
    assert markdown_line(MARKDOWN_DOC, "status") == 5
    assert markdown_line(MARKDOWN_DOC, "kind") == 3
    assert markdown_line(MARKDOWN_DOC, "open_task") == 7


def test_problem_line():
    problem = {"code": "open_tasks", "file": "specs/001-x/tasks.md", "path": None}
    assert problem_line(problem, MARKDOWN_DOC) == 7
    problem = {"code": "schema_error", "file": "integrations/x/integration.yaml", "path": "/id"}
    assert problem_line(problem, YAML_DOC) == 1
    problem = {"code": "x", "file": "other.txt", "path": None}
    assert problem_line(problem, "text") is None
