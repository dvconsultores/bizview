"""057b: every document the product ships exists in Spanish and in English, in step.

The rule is CONTRIBUTING's and `specs/046-release-docs-governance`'s (FR-020, FR-021); the check is
`scripts/check_docs_parity.py`, run by `make check` and by the gates workflow. This proves both
directions: the repository passes, and a document that drifted fails with a message naming it."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_docs_parity.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT, check=False)


def test_the_repository_is_in_step():
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "parity problem" not in result.stdout


@pytest.fixture
def drifted(tmp_path: Path) -> Path:
    """A fixture with one English section the Spanish file never got."""
    english = tmp_path / "README.md"
    english.write_text(
        "# Product\n\nIntro.\n\n## Install\n\nText.\n\n```bash\nmake install\n```\n\n"
        "## Test\n\n```bash\nmake test\n```\n\nSee [the guide](docs/AUTHORING.md).\n",
        encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "AUTHORING.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "docs" / "es").mkdir()
    (tmp_path / "docs" / "es" / "AUTHORING.md").write_text("# Guía\n", encoding="utf-8")
    # The Spanish file is missing "## Test" and its code block.
    (tmp_path / "README.es.md").write_text(
        "# Producto\n\nIntroducción.\n\n## Instalar\n\nTexto.\n\n```bash\nmake install\n```\n\n"
        "Ver [la guía](docs/es/AUTHORING.md).\n",
        encoding="utf-8")
    return tmp_path


def test_a_missing_heading_fails_and_names_the_file(drifted: Path):
    result = run("--root", str(drifted))
    assert result.returncode == 1, result.stdout
    assert "README.es.md: heading skeleton differs" in result.stdout
    assert "README.es.md: code blocks differ" in result.stdout


def test_a_missing_translation_fails(drifted: Path):
    (drifted / "README.es.md").unlink()
    result = run("--root", str(drifted))
    assert result.returncode == 1
    assert "README.es.md: missing" in result.stdout


def test_a_drifted_link_fails(drifted: Path):
    (drifted / "README.es.md").write_text(
        "# Producto\n\nIntroducción.\n\n## Instalar\n\nTexto.\n\n```bash\nmake install\n```\n\n"
        "## Probar\n\n```bash\nmake test\n```\n\nVer [la guía](docs/IMPORT.md).\n",
        encoding="utf-8")
    result = run("--root", str(drifted))
    assert result.returncode == 1
    assert "README.es.md: links differ" in result.stdout
