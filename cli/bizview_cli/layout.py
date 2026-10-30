"""Project layout of feature 020 (shared by the CLI validator, the zip importer and the backend)."""

import re

ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,49}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SPEC_FOLDER_RE = re.compile(r"^[0-9]{3}-[a-z0-9][a-z0-9-]{0,59}$")

_ID = r"[a-z][a-z0-9-]{1,49}"
_NAME = r"[a-z0-9][a-z0-9._-]{0,63}"
_SPEC = r"[0-9]{3}-[a-z0-9][a-z0-9-]{0,59}"
_ASSET = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"

PROJECT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"project\.yaml"),
    re.compile(r"\.specify/memory/constitution\.md"),
    re.compile(rf"specs/{_SPEC}/"
               r"(spec|plan|tasks|research|data-model|quickstart|run-report)\.md"),
    re.compile(rf"specs/{_SPEC}/checklists/[a-z0-9][a-z0-9._-]{{0,60}}\.md"),
    re.compile(rf"integrations/{_ID}/integration\.yaml"),
    re.compile(rf"integrations/{_ID}/queries/[a-z0-9][a-z0-9._-]{{0,59}}\.sql"),
    re.compile(rf"integrations/{_ID}/requests/[a-z0-9][a-z0-9._-]{{0,58}}\.yaml"),
    re.compile(rf"reports/{_ID}/report\.yaml"),
    re.compile(rf"distributions/{_ID}\.yaml"),
    # 044: images shipped inside the project. A folder level is allowed so an author can group
    # logos by vendor or currency; the file name keeps upper case on purpose (coin tickers:
    # `assets/coins/BTC.png`), and the extension decides what may be stored (assets.py sniffs it).
    re.compile(rf"assets/(?:[a-z0-9][a-z0-9._-]{{0,40}}/)?{_ASSET}\."
               r"(?:png|jpg|jpeg|webp|svg)", re.IGNORECASE),
)


def is_allowed(path: str) -> bool:
    """Return True when *path* exactly matches one of the allowed project files."""
    return any(pattern.fullmatch(path) for pattern in PROJECT_PATTERNS)


FOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\.specify"),
    re.compile(r"\.specify/memory"),
    re.compile(r"specs"),
    re.compile(rf"specs/{_SPEC}"),
    re.compile(rf"specs/{_SPEC}/checklists"),
    re.compile(r"integrations"),
    re.compile(rf"integrations/{_ID}"),
    re.compile(rf"integrations/{_ID}/queries"),
    re.compile(rf"integrations/{_ID}/requests"),
    re.compile(r"reports"),
    re.compile(rf"reports/{_ID}"),
    re.compile(r"distributions"),
    re.compile(r"assets"),
    re.compile(r"assets/[a-z0-9][a-z0-9._-]{0,40}"),
)


def is_allowed_folder(path: str) -> bool:
    """Return True when *path* is a folder that may exist in a feature-020 project."""
    stripped = path[:-1] if path.endswith("/") else path
    return any(pattern.fullmatch(stripped) for pattern in FOLDER_PATTERNS)


ALLOWED_TEXT: str = (
    "project.yaml; .specify/memory/constitution.md; specs/NNN-nombre/"
    "{spec,plan,tasks,research,data-model,quickstart,run-report}.md; "
    "specs/NNN-nombre/checklists/<nombre>.md; integrations/<id>/integration.yaml; "
    "integrations/<id>/queries/<nombre>.sql; integrations/<id>/requests/<nombre>.yaml; "
    "reports/<id>/report.yaml; distributions/<id>.yaml; "
    "assets/[<carpeta>/]<nombre>.{png,jpg,jpeg,webp,svg}"
)

KINDS = ("fuente", "integracion", "reporte", "distribucion")
_ALIASES = {
    "fuente": "fuente",
    "source": "fuente",
    "integracion": "integracion",
    "integration": "integracion",
    "reporte": "reporte",
    "report": "reporte",
    "distribucion": "distribucion",
    "distribution": "distribucion",
}
KIND_RE = re.compile(
    r"^\s*[-*]?\s*\*\*(?:Tipo|Type|Spec type)\*\*:\s*([A-Za-záéíóúÁÉÍÓÚ]+)",
    re.MULTILINE | re.IGNORECASE,
)

_ACCENT_MAP = str.maketrans(
    {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
    }
)


def spec_kind(text: str) -> str | None:
    """Canonical kind of a spec.md; legacy `**Spec type**: integration|report` maps to
    integracion|reporte."""
    match = KIND_RE.search(text)
    if not match:
        return None
    value = match.group(1).lower().translate(_ACCENT_MAP)
    return _ALIASES.get(value)
