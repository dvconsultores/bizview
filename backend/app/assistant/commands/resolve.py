"""Target spec of a /speckit-* command (feature 028 defect fix, section A).

A command's argument is the strongest signal of which spec it works on: an explicit folder, a
spec number ("002", "la 002", "reporte 002") or a title. Only when the argument names no spec does
the conversation's `current_spec` decide. Resolution is deterministic and happens before the
model runs, so a run can never be routed by a stale `current_spec`.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

_EXPLICIT = re.compile(r"(?<![\w-])(\d{3}-[A-Za-z0-9][A-Za-z0-9-]*)(?![\w-])")
_NUMBER = re.compile(r"(?<![\d-])(\d{3})(?!\d)")
_FORCE = re.compile(r"(?:^|\s)--force(?=\s|$)", re.IGNORECASE)
_ONLY = re.compile(r"(?:^|\s)--only(?:=|\s+)(?P<value>[Tt]\d{2,}(?:[,\s]+[Tt]\d{2,})*)",
                   re.IGNORECASE)


@dataclass(frozen=True)
class Resolution:
    spec: str | None
    source: str | None        # argument | number | title | current


def strip_force(arguments: str) -> tuple[str, bool]:
    """The arguments without `--force`, and whether the user asked to bypass a guard."""
    if not _FORCE.search(arguments or ""):
        return (arguments or "").strip(), False
    cleaned = _FORCE.sub(" ", arguments or "")
    return " ".join(cleaned.split()), True


def strip_only(arguments: str) -> tuple[str, tuple[str, ...]]:
    """The arguments without `--only T025,T026`, and the task ids it names (feature 040).

    `/speckit-implement <spec> --only T025,T026` is the honest action of the problems panel:
    the stage implements the tasks that are open instead of the whole spec again.
    """
    match = _ONLY.search(arguments or "")
    if match is None:
        return (arguments or "").strip(), ()
    ids: list[str] = []
    for item in re.split(r"[,\s]+", match.group("value") or ""):
        value = item.strip().upper()
        if value and value not in ids:
            ids.append(value)
    cleaned = f"{arguments[:match.start()]} {arguments[match.end():]}"
    return " ".join(cleaned.split()), tuple(ids)


def normalise(text: str | None) -> str:
    """Accents stripped, casefolded, punctuation turned into single spaces (padded)."""
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return f" {value.strip()} "


def _slug_phrase(folder: str) -> str:
    """`002-ventas-facturacion` → `ventas facturacion`."""
    short = folder.split("-", 1)[1] if "-" in folder else folder
    return normalise(short).strip()


def _title_phrase(item: dict[str, Any]) -> str:
    title = item.get("title")
    return normalise(title).strip() if isinstance(title, str) else ""


def resolve(specs: list[dict[str, Any]], arguments: str,
            current: str | None) -> Resolution:
    """Resolve the target spec of a command, in the order the product documents (section A)."""
    folders = [item["folder"] for item in specs]
    known = set(folders)
    args = arguments or ""

    # 1. An explicit folder id in the arguments.
    for match in _EXPLICIT.finditer(args):
        folder = match.group(1).lower()
        if folder in known:
            return Resolution(folder, "argument")

    # 2. A three-digit number ("002", "spec 002", "reporte 002", "la 002").
    seen: set[str] = set()
    for match in _NUMBER.finditer(args):
        matches = [folder for folder in folders if folder.startswith(f"{match.group(1)}-")]
        seen.update(matches)
    if len(seen) == 1:
        return Resolution(seen.pop(), "number")

    # 3. A title or folder slug mentioned in the arguments, when it names exactly one spec.
    normalised = normalise(args)
    titled: set[str] = set()
    for item in specs:
        folder = item["folder"]
        phrases = {phrase for phrase in (_slug_phrase(folder), _title_phrase(item))
                   if len(phrase) >= 4}
        if any(f" {phrase} " in normalised for phrase in phrases):
            titled.add(folder)
    if len(titled) == 1:
        return Resolution(titled.pop(), "title")

    # 4. The conversation's current spec.
    if current and current in known:
        return Resolution(current, "current")
    if current:
        return Resolution(current, "current")

    # 5. Nothing to work on.
    return Resolution(None, None)
