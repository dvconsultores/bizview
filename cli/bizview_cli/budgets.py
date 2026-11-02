"""The two allowances an imported project is charged to (feature 049).

One place decides what a project costs. 031 measured every file against one budget ("400 files,
2 MB per file, 20 MB"); 044 added `assets/**` and never gave the images a budget of their own, so a
project that ships a logo set was refused — and it could not be imported however well it was
authored. There are two allowances now:

    artifacts   project.yaml, specs/**, integrations/**, reports/**, themes/**, distributions/**
    assets      assets/**

Each has its own file count, per-file size and total. `layout.budget_of` says which one a path is
charged to; this module measures and refuses. The ZIP importer, the file writer and the CLI all
call it, because the constitution makes the layout the single source of the authoring contract and
two implementations of "how big may this be" is how the defect happened.

Refusals travel as a `Refusal` (code + params), never as prose: each side translates the same key
from its own catalogue, so the API and the CLI say the same sentence in the same language.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from . import layout

#: The deployment defaults. A `Settings` field and, in the product, a stored override sit on top.
ARTIFACTS_DEFAULT = {"max_files": 400, "max_kb": 2048, "max_mb": 20}
ASSETS_DEFAULT = {"max_files": 2000, "max_kb": 300, "max_mb": 25}

#: The folders each allowance pays for, as the author reads them in the refusal.
LABELS = {
    layout.ARTIFACTS: "project.yaml, specs/, integrations/, reports/, themes/, distributions/",
    layout.ASSETS: "assets/",
}

#: Content that is never part of a project, whatever allowance it would have been charged to.
#: An authoring pack zipped by mistake carries text and pictures, not programs.
DISALLOWED_EXTENSIONS = frozenset({
    ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".vbs", ".scr",
    ".exe", ".dll", ".so", ".dylib", ".jar", ".class", ".py", ".pyc", ".rb", ".php", ".pl", ".lua",
    ".wasm", ".com", ".msi", ".bin", ".app", ".apk", ".dmg", ".iso",
})

#: Same rule, by content: a `.txt` that starts like a program is a program.
EXECUTABLE_MAGIC = (
    b"\x7fELF",          # ELF
    b"MZ",               # PE / DOS
    b"#!",               # shebang
    b"\xca\xfe\xba\xbe",  # Mach-O fat / Java class
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",   # Mach-O
    b"\x00asm",          # WebAssembly
)


@dataclass(frozen=True)
class Budget:
    """One allowance: how many files of this class, how big each, how big in total."""

    name: str
    max_files: int
    max_kb: int
    max_mb: int

    @property
    def label(self) -> str:
        return LABELS[self.name]

    @property
    def max_bytes(self) -> int:
        return self.max_mb * 1024 * 1024

    @property
    def max_file_bytes(self) -> int:
        return self.max_kb * 1024

    def as_json(self, files: int = 0, size: int = 0, over: list[str] | None = None) -> dict:
        return {"name": self.name, "max_files": self.max_files, "max_kb": self.max_kb,
                "max_mb": self.max_mb, "label": self.label,
                "files": files, "bytes": size, "over": over or []}


@dataclass(frozen=True)
class Refusal:
    """Why an import stops: a code and the numbers the message prints, never the sentence."""

    code: str
    params: dict = field(default_factory=dict)


@dataclass
class Tally:
    """What one class of files costs in a given project, archive or folder."""

    budget: Budget
    files: int = 0
    bytes: int = 0
    largest: tuple[str, int] | None = None

    def add(self, path: str, size: int) -> None:
        self.files += 1
        self.bytes += size
        if self.largest is None or size > self.largest[1]:
            self.largest = (path, size)

    def over_files(self) -> bool:
        return self.files > self.budget.max_files

    def over_bytes(self) -> bool:
        return self.bytes > self.budget.max_bytes

    def over_names(self) -> list[str]:
        names = []
        if self.over_files():
            names.append("files")
        if self.over_bytes():
            names.append("bytes")
        return names

    def as_json(self) -> dict:
        return self.budget.as_json(self.files, self.bytes, self.over_names())


@dataclass
class Report:
    """The measurement of one project: both tallies, the ignored paths, and the refusal if any."""

    tallies: dict[str, Tally]
    ignored: list[str] = field(default_factory=list)
    refusal: Refusal | None = None

    def __getitem__(self, name: str) -> Tally:
        return self.tallies[name]

    @property
    def importable(self) -> bool:
        return self.refusal is None

    def as_json(self) -> dict:
        return {name: tally.as_json() for name, tally in self.tallies.items()}


def defaults() -> dict[str, Budget]:
    """The deployment defaults, which are also what the CLI has no way to override."""
    return {
        layout.ARTIFACTS: Budget(layout.ARTIFACTS, **ARTIFACTS_DEFAULT),
        layout.ASSETS: Budget(layout.ASSETS, **ASSETS_DEFAULT),
    }


def as_budget(name: str, values: dict) -> Budget:
    """A budget from stored or configured values, clamped to something a project can live with."""
    fallback = defaults()[name]
    return Budget(
        name,
        max_files=int(values.get("max_files") or fallback.max_files),
        max_kb=int(values.get("max_kb") or fallback.max_kb),
        max_mb=int(values.get("max_mb") or fallback.max_mb),
    )


def looks_executable(data: bytes | None) -> bool:
    """True when the bytes start like a program. Extension alone cannot tell."""
    return bool(data) and any(data.startswith(magic) for magic in EXECUTABLE_MAGIC)


def disallowed(path: str, data: bytes | None = None) -> bool:
    """True when *path* is content the product never imports, by name or by bytes."""
    lowered = path.lower()
    if any(lowered.endswith(ext) for ext in DISALLOWED_EXTENSIONS):
        return True
    return looks_executable(data)


def tally(entries: Iterable[tuple[str, int, bytes | None]],
          budgets: dict[str, Budget] | None = None) -> Report:
    """Measure (path, size, head bytes) entries against both allowances.

    Every entry is looked at, even after something is already wrong, so the report always carries
    complete counts — an author who is told "one image is too big" also wants to see how many there
    are. The refusal that comes back is the most serious one, chosen in a fixed order rather than by
    the order the archive happened to list its files:

        disallowed content  →  a file over its own limit  →  artifacts  →  assets

    Artifacts come before assets because artifacts are what the project *is*: when both allowances
    are exceeded, the author needs to hear about the specs, not the logos.
    """
    limits = budgets or defaults()
    report = Report({name: Tally(budget) for name, budget in limits.items()})
    found: list[tuple[int, Refusal]] = []
    for path, size, data in entries:
        name = layout.budget_of(path)
        if disallowed(path, data):
            found.append((0, Refusal("zip_disallowed", {"path": path})))
        if name is None:
            if not disallowed(path, data):
                report.ignored.append(path)
            continue
        budget = limits[name]
        if size > budget.max_file_bytes:
            code = ("artifacts_file_too_large" if name == layout.ARTIFACTS
                    else "assets_file_too_large")
            found.append((1, Refusal(code, {"path": path, "max_kb": budget.max_kb})))
            continue
        report.tallies[name].add(path, size)
    report.ignored.sort()
    for order, name in ((2, layout.ARTIFACTS), (3, layout.ASSETS)):
        over = _over(report.tallies[name])
        if over is not None:
            found.append((order, over))
    if found:
        report.refusal = min(found, key=lambda item: item[0])[1]
    return report


def _over(tally_: Tally) -> Refusal | None:
    budget = tally_.budget
    prefix = "artifacts" if budget.name == layout.ARTIFACTS else "assets"
    if tally_.over_files():
        return Refusal(f"{prefix}_over_files",
                       {"files": tally_.files, "max_files": budget.max_files,
                        "label": budget.label})
    if tally_.over_bytes():
        return Refusal(f"{prefix}_over_bytes",
                       {"max_mb": budget.max_mb, "label": budget.label,
                        "size_mb": _round_mb(tally_.bytes)})
    return None


def _round_mb(size: int) -> int:
    return max(1, round(size / (1024 * 1024)))
