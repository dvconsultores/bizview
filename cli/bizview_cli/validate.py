"""Workspace validation — "no spec, no run" (feature 005, FR-001/FR-002/FR-017).

Static checks shared by `bizview validate` and the installation (which adds live checks such as
"the data source exists in the catalogue"). Produces the lock: SHA-256 of every spec file and
artifact, so anything changed after validation is refused at apply time. Every problem carries
the file, the JSON pointer, the expected schema fragment and a suggested fix (feature 017).
"""
import copy
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from importlib import resources
from pathlib import Path

import sqlglot
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError, best_match
from sqlglot import exp

from bizview_cli import __version__, layout, materialize, report_layout, sqlsafety, transform
from bizview_cli.i18n import t

SPEC_FILES = ("spec.md", "plan.md", "tasks.md")
DATE_TYPES = {"date", "timestamptz"}
DIRECT_RESERVED_SCHEMAS = ("pg_catalog", "information_schema")
DIRECT_RESERVED_PREFIXES = ("pg_toast", "app_test_", "preview_")
DIRECT_PRODUCT_MESSAGE = "Tabla del producto: no se puede leer en un reporte directo"
_DIRECT_SPEC_LINES = (
    (re.compile(r"^\s*[-*]?\s*\*\*(?:Modo|Mode)\*\*:[ \t]*(directo|direct)\b",
                re.M | re.I), "**Modo**: directo",
     "validate.spec_line.mode"),
    (re.compile(r"^\s*[-*]?\s*\*\*(?:Fuente|Source)\*\*:[ \t]*\S", re.M | re.I),
     "**Fuente**:",
     "validate.spec_line.source"),
    (re.compile(r"^\s*[-*]?\s*\*\*(?:Tablas|Tables)\*\*:[ \t]*\S", re.M | re.I),
     "**Tablas**:",
     "validate.spec_line.tables"),
    (re.compile(r"^\s*[-*]?\s*\*\*(?:Mantenido por|Maintained by)\*\*:[ \t]*\S",
                re.M | re.I), "**Mantenido por**:",
     "validate.spec_line.maintained_by"),
    (re.compile(r"^\s*[-*]?\s*\*\*(?:Volumen esperado|Expected volume)\*\*:[ \t]*\S",
                re.M | re.I), "**Volumen esperado**:",
     "validate.spec_line.volume"),
)

DIRECT_TYPE_COMPAT: dict[str, tuple[str, ...]] = {
    "text": ("text", "character varying", "character", "uuid", "citext", "name"),
    "integer": ("integer", "smallint"),
    "bigint": ("bigint", "integer", "smallint"),
    "numeric": ("numeric", "integer", "bigint", "smallint", "real", "double precision"),
    "boolean": ("boolean",),
    "date": ("date",),
    "timestamptz": ("timestamp with time zone", "timestamp without time zone"),
}
_PERSONAL_LINE = re.compile(r"^\s*[-*]?\s*\*\*(?:Datos personales|Personal data)\*\*:[ \t]*(.*)$",
                            re.M | re.I)


def direct_reserved(schema: str, table: str) -> bool:
    """True when a schema.table cannot be read by a direct report."""
    schema = schema.lower()
    table = table.lower()
    return (schema in DIRECT_RESERVED_SCHEMAS
            or schema.startswith(DIRECT_RESERVED_PREFIXES)
            or table == "alembic_version")
STATUS_RE = re.compile(r"^\*\*Status\*\*:\s*(.+?)\s*$", re.M | re.I)
TYPE_RE = re.compile(r"^\*\*Spec type\*\*:\s*(integration|report)\b", re.M | re.I)
OPEN_TASK_RE = re.compile(r"^\s*- \[ \]", re.M)
SOURCE_LINE_RE = re.compile(r"^\s*[-*]?\s*\*\*(?:Fuente|Source)\*\*:\s*(\S.*?)\s*$", re.M)
APPROVED = ("approved", "implemented", "aprobado", "aprobada", "implementado", "implementada")
MAX_ISSUES_PER_FILE = 200

TYPE_NAMES = {
    "string": "validate.type.string",
    "integer": "validate.type.integer",
    "number": "validate.type.number",
    "boolean": "validate.type.boolean",
    "object": "validate.type.object",
    "array": "validate.type.array",
    "null": "validate.type.null",
}

# Exact Python string values of the schema patterns.
PATTERN_EXAMPLES = {
    r"^[a-z][a-z0-9-]{1,49}$": "facturas-dia",
    r"^[a-z][a-z0-9_]{0,40}$": "fecha_emision",
    r"^\S+ \S+ \S+ \S+ \S+$": "0 * * * *",
    r"^queries/[A-Za-z0-9_.-]+\.sql$": "queries/facturas.sql",
    r"^requests/[A-Za-z0-9_.-]+\.ya?ml$": "requests/facturas.yaml",
    r"^[a-z][a-z0-9-]{1,49}\.[a-z][a-z0-9_]{0,40}$": "facturas.facturas",
    r"^[A-Z]{3}$": "USD",
    r"^[a-z_][a-z0-9_]{0,62}\.[a-z_][a-z0-9_]{0,62}$": "public.bi_ventas",
}

LIMIT_HINTS = {
    "minItems": lambda n: t("validate.limit.min_items", n=n),
    "maxItems": lambda n: t("validate.limit.max_items", n=n),
    "minProperties": lambda n: t("validate.limit.min_properties", n=n),
    "minLength": lambda n: t("validate.limit.min_length", n=n),
    "maxLength": lambda n: t("validate.limit.max_length", n=n),
    "minimum": lambda n: t("validate.limit.minimum", n=n),
    "maximum": lambda n: t("validate.limit.maximum", n=n),
    "uniqueItems": lambda _: t("validate.limit.unique_items"),
}


def _schema(name: str) -> Draft202012Validator:
    text = resources.files("bizview_cli.schemas").joinpath(f"{name}.schema.json").read_text()
    return Draft202012Validator(json.loads(text))


SCHEMAS = {n: _schema(n) for n in ("integration", "report", "request", "workspace",
                                  "project", "distribution")}


@dataclass
class Issue:
    entry: str
    code: str
    message: str
    level: str = "error"
    file: str | None = None
    path: str | None = None
    expected: dict | None = None
    fix: str | None = None

    def __str__(self) -> str:
        return f"[{self.code}] {self.entry}: {self.message}"

    def as_dict(self) -> dict:
        return {
            "entry": self.entry,
            "code": self.code,
            "message": self.message,
            "level": self.level,
            "file": self.file,
            "path": self.path,
            "expected": self.expected,
            "fix": self.fix,
        }


@dataclass
class Entry:
    kind: str                      # integration | report | distribution
    id: str
    folder: Path                   # integrations/<id> or reports/<id>
    artifact: dict
    files: dict[str, bytes] = field(default_factory=dict)   # relative path → content
    spec: dict = field(default_factory=dict)                 # folder, status, title, sha256
    project: str | None = None     # project slug (legacy workspaces: "principal")
    project_dir: Path | None = None  # projects/<slug> (feature 020); None in legacy workspaces

    @property
    def key(self) -> str:
        return f"{self.kind}s/{self.id}"


@dataclass
class Result:
    issues: list[Issue]
    integrations: dict[str, Entry]
    reports: dict[str, Entry]
    lock: dict | None
    name: str | None
    manifest: dict = field(default_factory=dict)
    layout: str = "legacy"
    projects: dict = field(default_factory=dict)
    distributions: dict[str, Entry] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)


@dataclass
class DirectContext:
    sources: dict[str, dict] | None = None
    bi_enabled: bool | None = None
    product_tables: frozenset[str] = frozenset()
    structure: Callable[[str, list[str]], dict] | None = None
    personal_kind: Callable[[str], str | None] | None = None
    warn_rows: int | None = None
    dataset_rows: Callable[[str, str], int | None] | None = None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer(parts: list[str | int]) -> str:
    """RFC 6901 JSON pointer."""

    if not parts:
        return ""
    out = []
    for p in parts:
        out.append(str(p).replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(out)


def _shallow(node) -> dict | list | None:
    """Keep scalar values, lists of scalars, and a one-level schema skeleton."""

    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in ("type", "enum", "const", "pattern", "required", "format", "minimum",
                     "maximum", "minItems", "maxItems", "minLength", "maxLength",
                     "minProperties", "uniqueItems"):
                if isinstance(v, (str, int, float, bool, type(None))):
                    out[k] = v
                elif isinstance(v, list) and all(
                        isinstance(x, (str, int, float, bool, type(None))) for x in v):
                    out[k] = v
            elif k == "properties" and isinstance(v, dict):
                out[k] = {name: _shallow(sub) for name, sub in v.items()}
            elif k in ("additionalProperties", "items", "propertyNames") and isinstance(v, dict):
                out[k] = _shallow(v)
            elif k == "oneOf" and isinstance(v, list):
                branches = []
                for b in v:
                    if isinstance(b, dict):
                        branch = _shallow(b)
                        if "properties" in b and isinstance(b["properties"], dict):
                            props = b["properties"]
                            if "type" in props and isinstance(props["type"], dict) \
                                    and isinstance(props["type"].get("const"),
                                                    (str, int, float, bool, type(None))):
                                branch = branch or {}
                                branch["type"] = {"const": props["type"]["const"]}
                        branches.append(branch)
                out[k] = branches
        return out
    if isinstance(node, list):
        if all(isinstance(x, (str, int, float, bool, type(None))) for x in node):
            return list(node)
        return None
    if isinstance(node, (str, int, float, bool, type(None))):
        return node
    return None


def _compact(fragment, limit: int = 1024) -> dict:
    """Compact schema fragment guaranteed to fit in `limit` UTF-8 bytes."""

    if fragment is None:
        fragment = {}
    try:
        if len(json.dumps(fragment, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) \
                <= limit:
            return copy.deepcopy(fragment)
    except (TypeError, ValueError):
        pass
    shallow = _shallow(fragment)
    if shallow is not None:
        try:
            if len(json.dumps(shallow, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) \
                    <= limit:
                return shallow
        except (TypeError, ValueError):
            pass
    if isinstance(fragment, dict):
        summary = {}
        if "type" in fragment:
            summary["type"] = fragment["type"]
        if "required" in fragment:
            summary["required"] = fragment["required"]
        props = fragment.get("properties")
        if isinstance(props, dict):
            summary["properties"] = sorted(props)
        if summary:
            try:
                data = json.dumps(summary, ensure_ascii=False, separators=(",", ":")).encode()
                if len(data) <= limit:
                    return summary
            except (TypeError, ValueError):
                pass
        if "type" in fragment:
            return {"type": fragment["type"]}
    return {}


def _variants(branches: list[dict]) -> tuple[list, list[set[str]]]:
    """Return type consts (or None) and distinguishing required keys per oneOf branch."""

    type_consts = []
    req_sets = [set(branch.get("required", [])) for branch in branches]
    if req_sets:
        common = set.intersection(*req_sets)
    else:
        common = set()
    for branch in branches:
        props = branch.get("properties", {})
        if isinstance(props, dict) and isinstance(props.get("type"), dict) \
                and "const" in props["type"]:
            type_consts.append(props["type"]["const"])
        else:
            type_consts.append(None)
    distinguishing = [req - common for req in req_sets]
    return type_consts, distinguishing


def _pick_branch(branches: list[dict], instance) -> int | None:
    if not isinstance(instance, dict):
        return None
    type_consts, distinguishing = _variants(branches)
    type_hits = []
    for i, const in enumerate(type_consts):
        if const is not None and instance.get("type") == const:
            type_hits.append(i)
    if len(type_hits) == 1:
        return type_hits[0]
    if type_hits:
        return None
    hits = []
    for i, keys in enumerate(distinguishing):
        if keys and all(k in instance for k in keys):
            hits.append(i)
    return hits[0] if len(hits) == 1 else None


def _expand(err: ValidationError) -> list[tuple[ValidationError, dict | None]]:
    """Expand a oneOf error into its most useful branch errors.

    Returns (error, override). For normal errors ``override`` is ``None``. For unresolved
    oneOf cases the override carries suffix/message/expected/fix already resolved.
    """

    if err.validator != "oneOf":
        return [(err, None)]
    idx = _pick_branch(err.validator_value, err.instance)
    if idx is not None:
        sub = [e for e in err.context
               if e.relative_schema_path and e.relative_schema_path[0] == idx]
        if sub:
            out = []
            for e in sub:
                out.extend(_expand(e))
            return out
    branches = err.validator_value
    type_consts, distinguishing = _variants(branches)
    if isinstance(err.instance, dict):
        inst_type = err.instance.get("type")
        consts = [c for c in type_consts if c is not None]
        if consts and inst_type not in consts:
            where = "/".join(str(p) for p in err.absolute_path) or t("validate.root")
            return [(err, {
                "suffix": "/type",
                "message": t("validate.invalid_type", where=where, inst_type=repr(inst_type)),
                "expected": _compact({"oneOf": branches}),
                "fix": t("validate.use_type", types=" | ".join(str(c) for c in consts)),
            })]
        present = []
        all_keys = sorted({k for keys in distinguishing for k in keys})
        for k in all_keys:
            if k in err.instance:
                present.append(k)
        if present:
            where = "/".join(str(p) for p in err.absolute_path) or t("validate.root")
            message = f"{where}: {err.message[:200]}"
            return [(err, {
                "suffix": "",
                "message": message,
                "expected": _compact({"oneOf": branches}),
                "fix": t("validate.use_only_one", keys=", ".join(sorted(present))),
            })]
        if all_keys:
            where = "/".join(str(p) for p in err.absolute_path) or t("validate.root")
            return [(err, {
                "suffix": "",
                "message": f"{where}: {err.message[:200]}",
                "expected": _compact({"oneOf": branches}),
                "fix": t("validate.add_one", keys=", ".join(all_keys)),
            })]
    if err.context:
        return [(best_match(err.context), None)]
    expected = _compact({"oneOf": branches})
    if expected:
        return [(err, {"suffix": "", "message": None, "expected": expected, "fix": None})]
    return [(err, None)]


def _schema_message(err: ValidationError, where: str) -> str:
    return f"{where}: {err.message[:200]}"


def _hint(err: ValidationError) -> tuple[dict | None, str | None]:
    validator = err.validator
    value = err.validator_value
    schema = err.schema
    instance = err.instance

    if validator == "required":
        if isinstance(value, list) and isinstance(instance, dict):
            missing = [k for k in value if k not in instance]
            k = None
            for cand in missing:
                if repr(cand) in err.message:
                    k = cand
                    break
            if k is None and missing:
                k = missing[0]
            if k is not None:
                props = schema.get("properties", {}) if isinstance(schema, dict) else {}
                return _compact({"required": value, "properties": {k: props.get(k, {})}}), \
                    t("validate.add_key", key=k)
    if validator == "additionalProperties" and value is False and isinstance(instance, dict):
        props = set(schema.get("properties", {})) if isinstance(schema, dict) else set()
        extras = sorted(k for k in instance if k not in props)
        if extras:
            return _compact({"additionalProperties": False, "properties": sorted(props)}), \
                t("validate.remove_keys", keys=", ".join(f"`{x}`" for x in extras),
                  allowed=", ".join(sorted(props)))
        return None, None
    if validator == "enum":
        fix = t("validate.use_one_of", values=", ".join(str(v) for v in value))
        return _compact({"enum": value}), fix
    if validator == "const":
        return _compact({"const": value}), t("validate.use_value", value=value)
    if validator == "pattern":
        example = PATTERN_EXAMPLES.get(value)
        fix = t("validate.pattern", pattern=value)
        if example:
            fix += t("validate.pattern_example", example=example)
        return _compact({"type": "string", "pattern": value}), fix
    if validator == "type":
        names = [t(TYPE_NAMES[v]) if v in TYPE_NAMES else v
                 for v in (value if isinstance(value, list) else [value])]
        return _compact({"type": value}), t("validate.expected_type",
                                            types=t("validate.or_sep").join(names))
    if validator in LIMIT_HINTS:
        return _compact({validator: value}), LIMIT_HINTS[validator](value)
    expected = _compact(err.schema) if isinstance(err.schema, dict) else None
    return expected if expected else None, None


def _read_yaml(path: Path, entry: str, issues: list[Issue], raw: bytes | None = None,
               file: str | None = None) -> dict | None:
    try:
        data = yaml.safe_load(raw.decode("utf-8") if raw is not None
                              else path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        issues.append(Issue(entry, "schema_error", f"{path.name}: {e}", file=file))
        return None
    if not isinstance(data, dict):
        issues.append(Issue(entry, "schema_error", t("validate.yaml_object", path=path.name),
                            file=file))
        return None
    return data


def _schema_errors(kind: str, data: dict, entry: str, issues: list[Issue],
                   file: str | None = None) -> bool:
    errors = list(SCHEMAS[kind].iter_errors(data))
    if not errors:
        return True
    collected: dict[tuple[str, str], tuple[ValidationError, dict | None]] = {}
    for e in errors:
        for leaf, override in _expand(e):
            suffix = override.get("suffix", "") if override else ""
            message_key = override.get("message") if override else None
            if message_key is None:
                message_key = leaf.message
            key = (_pointer(list(leaf.absolute_path)) + suffix, message_key)
            collected.setdefault(key, (leaf, override))
    sorted_items = sorted(
        collected.values(),
        key=lambda item: (
            _sort_key(item[0].absolute_path),
            (item[1].get("message") if item[1] and item[1].get("message")
             else item[0].message) + (item[1].get("suffix", "") if item[1] else ""),
        ),
    )
    limited = sorted_items[:MAX_ISSUES_PER_FILE]
    for err, override in limited:
        where = "/".join(str(p) for p in err.absolute_path) or t("validate.root")
        pointer = _pointer(list(err.absolute_path))
        if override:
            pointer += override.get("suffix", "")
            msg = override.get("message") or _schema_message(err, where)
            expected = override.get("expected")
            fix = override.get("fix")
        else:
            expected, fix = _hint(err)
            msg = _schema_message(err, where)
        issues.append(Issue(entry, "schema_error", msg, file=file, path=pointer,
                            expected=expected, fix=fix))
    if len(sorted_items) > MAX_ISSUES_PER_FILE:
        omitted = len(sorted_items) - MAX_ISSUES_PER_FILE
        issues.append(Issue(entry, "schema_error",
                            t("validate.omitted_errors", count=omitted), file=file))
    return False


def _sort_key(path_parts):
    """Key safe for mixed int/str JSON pointer parts."""

    return [(0, p) if isinstance(p, int) else (1, p) for p in path_parts]


def _layout(root: Path) -> str:
    """Classify workspace layout as legacy, v2, or mixed based on top-level folders."""
    projects = root / "projects"
    has_v2 = projects.is_dir() and any(
        p.is_dir() and not p.name.startswith(".") for p in projects.iterdir()
    )
    has_legacy = any((root / name).is_dir() for name in ("integrations", "reports", "specs"))
    if has_v2 and has_legacy:
        return "mixed"
    if has_v2:
        return "v2"
    return "legacy"


def spec_path(entry: Entry, name: str) -> str:
    """Workspace-relative path of a spec document of `entry` (key of `entry.files`)."""
    folder = entry.spec.get("folder")
    if entry.project_dir is not None:
        return f"{entry.project_dir.as_posix()}/{folder}/{name}"
    return f"{folder}/{name}"


def _check_spec(root: Path, entry: Entry, issues: list[Issue]) -> None:
    rel = str(entry.artifact.get("spec", "")).strip().rstrip("/")
    v2 = entry.project_dir is not None
    if entry.kind == "distribution":
        artifact_file = f"{entry.folder.as_posix()}/{entry.id}.yaml"
    else:
        artifact_file = f"{entry.folder.as_posix()}/{entry.kind}.yaml"
    segments = rel.split("/")
    if ".." in segments or "\\" in rel:
        issues.append(Issue(entry.key, "missing_spec",
                            t("validate.spec_no_dots_backslashes"),
                            file=artifact_file, path="/spec",
                            fix=t("validate.use_spec", kind=entry.kind)))
        return
    if v2:
        if not (len(segments) == 2 and segments[0] == "specs"
                and layout.SPEC_FOLDER_RE.match(segments[1])):
            issues.append(Issue(entry.key, "missing_spec", t("validate.spec_v2_path"),
                                file=artifact_file, path="/spec",
                                fix=t("validate.use_spec_v2")))
            return
        base = root / entry.project_dir
        shown_prefix_el = entry.project_dir.as_posix()
    else:
        expected_prefix = f"specs/{entry.kind}s/"
        if not rel.startswith(expected_prefix):
            issues.append(Issue(entry.key, "missing_spec",
                                t("validate.spec_prefix", expected_prefix=expected_prefix),
                                file=artifact_file, path="/spec",
                                fix=t("validate.use_spec", kind=entry.kind)))
            return
        base = root
        shown_prefix_el = ""
    folder = (base / rel).resolve()
    if base.resolve() not in folder.parents or not folder.is_dir():
        shown = f"{shown_prefix_el}/{rel}" if v2 else rel
        fix = t("validate.use_spec_v2") if v2 else t("validate.use_spec", kind=entry.kind)
        issues.append(Issue(entry.key, "missing_spec", t("validate.missing_spec_folder", rel=shown),
                            file=artifact_file, path="/spec", fix=fix))
        return
    doc_prefix = f"{shown_prefix_el}/{rel}" if v2 else rel
    shas = {}
    texts = {}
    for name in SPEC_FILES:
        f = folder / name
        shown = f"{doc_prefix}/{name}"
        if not f.is_symlink() and not f.exists():
            issues.append(Issue(entry.key, "spec_incomplete",
                                t("validate.missing_file", path=shown),
                                file=shown, fix=t("validate.create_file", path=shown)))
            continue
        if f.is_symlink() or f.resolve().parent != folder or not f.is_file():
            issues.append(Issue(entry.key, "spec_incomplete",
                                t("validate.file_link_outside", path=shown), file=shown,
                                fix=t("validate.create_file", path=shown)))
            continue
        if f.stat().st_size > 512 * 1024:
            issues.append(Issue(entry.key, "spec_incomplete",
                                t("validate.file_too_large", path=shown),
                                file=shown, fix=t("validate.reduce_file", path=shown)))
            continue
        data = f.read_bytes()
        if len(data) > 512 * 1024:
            issues.append(Issue(entry.key, "spec_incomplete",
                                t("validate.file_too_large", path=shown),
                                file=shown, fix=t("validate.reduce_file", path=shown)))
            continue
        if b"\x00" in data:
            issues.append(Issue(entry.key, "spec_incomplete",
                                t("validate.file_null_chars", path=shown), file=shown,
                                fix=t("validate.remove_null_chars", path=shown)))
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(Issue(entry.key, "spec_incomplete",
                                t("validate.file_not_utf8", path=shown),
                                file=shown,
                                fix=t("validate.save_utf8", path=shown)))
            continue
        shas[name] = _sha(data)
        texts[name] = text
        entry.files[shown] = data
    if v2:
        entry.spec = {"folder": rel, "project": entry.project,
                      "sha256": shas, "status": None, "title": None}
    else:
        entry.spec = {"folder": rel, "sha256": shas, "status": None, "title": None}
    spec_text = texts.get("spec.md")
    if spec_text is not None:
        status = STATUS_RE.search(spec_text)
        entry.spec["status"] = status.group(1) if status else None
        title = re.search(r"^#\s+(.+)$", spec_text, re.M)
        entry.spec["title"] = title.group(1).strip() if title else None
        if not status or not status.group(1).lower().startswith(APPROVED):
            issues.append(Issue(entry.key, "spec_not_approved",
                                t("validate.spec_status"),
                                file=f"{doc_prefix}/spec.md",
                                fix=t("validate.fix_status_approved")))
        if v2:
            expected = {"integration": "integracion", "report": "reporte",
                        "distribution": "distribucion"}[entry.kind]
            found = layout.spec_kind(spec_text)
            kind_file = f"{shown_prefix_el}/{rel}/spec.md"
            if found is None:
                issues.append(Issue(entry.key, "spec_kind_missing",
                                    t("validate.spec_kind_missing"),
                                    file=kind_file,
                                    fix=t("validate.fix_spec_kind", kind=expected)))
            elif found != expected:
                issues.append(Issue(entry.key, "spec_incomplete",
                                    t("validate.spec_kind_mismatch", kind=expected, found=found),
                                    file=kind_file,
                                    fix=t("validate.fix_spec_kind", kind=expected)))
        else:
            kind = TYPE_RE.search(spec_text)
            if not kind or kind.group(1).lower() != entry.kind:
                issues.append(Issue(entry.key, "spec_incomplete",
                                    t("validate.spec_type_declare", kind=entry.kind),
                                    file=f"{rel}/spec.md",
                                    fix=t("validate.fix_spec_type", kind=entry.kind)))
    tasks_text = texts.get("tasks.md")
    if tasks_text is not None:
        open_tasks = len(OPEN_TASK_RE.findall(tasks_text))
        if open_tasks:
            issues.append(Issue(entry.key, "open_tasks", t("validate.open_tasks", count=open_tasks),
                                file=f"{doc_prefix}/tasks.md",
                                fix=t("validate.fix_tasks")))


def _read_artifact_file(root: Path, entry: Entry, rel: str, issues: list[Issue]) -> str | None:
    path = (root / entry.folder / rel).resolve()
    file = f"{entry.folder.as_posix()}/{rel}"
    if (root / entry.folder).resolve() not in path.parents or not path.is_file():
        issues.append(Issue(entry.key, "schema_error",
                            t("validate.missing_rel", path=f"{entry.folder}/{rel}"),
                            file=file))
        return None
    data = path.read_bytes()
    if len(data) > 512 * 1024:
        issues.append(Issue(entry.key, "schema_error",
                            t("validate.file_too_large", path=f"{entry.folder}/{rel}"),
                            file=file))
        return None
    if b"\x00" in data:
        issues.append(Issue(entry.key, "schema_error",
                            t("validate.file_null_chars", path=f"{entry.folder}/{rel}"), file=file))
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(Issue(entry.key, "schema_error",
                            t("validate.file_not_utf8", path=f"{entry.folder}/{rel}"),
                            file=file))
        return None
    entry.files[f"{entry.folder}/{rel}"] = data
    return text


def _bad_text(obj) -> bool:
    if isinstance(obj, str):
        if "\x00" in obj:
            return True
        try:
            obj.encode("utf-8")
        except UnicodeEncodeError:
            return True
        return False
    if isinstance(obj, dict):
        return any(_bad_text(k) or _bad_text(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_bad_text(item) for item in obj)
    return False


TIMEZONE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+){0,2}")


def _valid_timezone(name: str) -> bool:
    from zoneinfo import ZoneInfo
    if len(name) > 64 or not TIMEZONE_RE.fullmatch(name):
        return False
    try:
        ZoneInfo(name)
    except Exception:
        return False
    return True


def _names(values, limit: int = 30) -> str:
    """Sorted, de-duplicated names for fix hints, truncated after `limit`."""
    values = sorted(set(values))
    if not values:
        return "(ninguno)"
    if len(values) <= limit:
        return ", ".join(values)
    shown = values[:limit]
    return t("validate.names_more", shown=", ".join(shown), n=len(values) - limit)


def _check_integration(root: Path, entry: Entry, issues: list[Issue],
                       known_sources: dict[str, str] | None) -> None:
    a = entry.artifact
    iy = f"{entry.folder.as_posix()}/integration.yaml"
    if "timezone" in a and not _valid_timezone(a["timezone"]):
        issues.append(Issue(entry.key, "schema_error",
                            t("validate.timezone_not_iana",
                              timezone=a['timezone']), file=iy, path="/timezone",
                            fix=t("validate.fix_use_iana_zone")))
    if known_sources is not None and a["source"].strip().lower() not in known_sources:
        fix = (t("validate.fix_use_existing_source", sources=_names(known_sources.values()))
               if known_sources else t("validate.fix_register_source_first"))
        issues.append(Issue(entry.key, "unknown_source",
                            t("validate.source_not_in_installation", source=a['source']),
                            file=iy, path="/source", fix=fix))
    for name, ds in a["datasets"].items():
        where = f"{entry.key}.{name}"
        path = _pointer(["datasets", name])
        cols = ds["columns"]
        tr = ds.get("transform")
        extracted = tr["input"] if tr else cols
        for key in ds.get("primary_key", []):
            if key not in cols:
                issues.append(Issue(where, "invalid_reference",
                                    t("validate.primary_key_not_exists", key=key),
                                    file=iy, path=path + "/primary_key",
                                    fix=t("validate.use_declared_columns", columns=_names(cols))))
        date_col = ds.get("date_column")
        date_cols = {c for c, d in cols.items() if d.get("type") in DATE_TYPES}
        if date_col and cols.get(date_col, {}).get("type") not in DATE_TYPES:
            fix = (t("validate.fix_use_date_or_timestamptz", columns=_names(date_cols))
                   if date_cols else t("validate.fix_declare_date_or_timestamptz"))
            issues.append(Issue(where, "invalid_reference",
                                t("validate.date_column_must_be_date_or_timestamptz",
                                  column=date_col),
                                file=iy, path=path + "/date_column", fix=fix))
        inc = ds.get("incremental", {"mode": "full"})
        if "window_days" in inc and not date_col:
            issues.append(Issue(where, "invalid_reference",
                                t("validate.incremental_requires_date_column"),
                                file=iy, path=path + "/incremental",
                                fix=t("validate.fix_add_date_column")))
        extract = ds["extract"]
        if "query" in extract:
            qfile = f"{entry.folder.as_posix()}/{extract['query']}"
            sql = _read_artifact_file(root, entry, extract["query"], issues)
            if sql is not None:
                for p in sqlsafety.check_query(sql):
                    issues.append(Issue(f"{where} ({extract['query']})", p.code, p.message,
                                        file=qfile))
                if not any(i.entry.startswith(where) and i.code == "unsafe_sql" for i in issues):
                    used = sqlsafety.query_params(sql)
                    declared = set(extract.get("params", []))
                    if used - declared:
                        issues.append(Issue(where, "invalid_reference",
                                            t("validate.undeclared_params",
                                              params=sorted(used - declared)),
                                            file=iy, path=path + "/extract/params",
                                            fix=t("validate.fix_declare_params")))
                    if "window_days" in inc and not {"window_start", "window_end"} <= used:
                        issues.append(Issue(where, "invalid_reference",
                                            t("validate.incremental_load_must_filter_by_window_start_and_end"),
                                            file=qfile,
                                            fix=t("validate.fix_filter_window_start_end")))
        else:
            rfile = f"{entry.folder.as_posix()}/{extract['request']}"
            text = _read_artifact_file(root, entry, extract["request"], issues)
            if text is not None:
                try:
                    req = yaml.safe_load(text)
                except yaml.YAMLError as e:
                    issues.append(Issue(where, "schema_error", f"{extract['request']}: {e}",
                                        file=rfile))
                else:
                    if isinstance(req, dict):
                        _schema_errors("request", req, f"{where} ({extract['request']})",
                                       issues, file=rfile)
                        reqpath = str(req.get("path") or "")
                        if "://" in reqpath or reqpath.startswith("//") or "\\" in reqpath:
                            issues.append(Issue(where, "unsafe_sql",
                                                t("validate.path_must_be_relative"),
                                                file=rfile, path="/path"))
                        for col in (req.get("fields") or {}):
                            if col not in extracted:
                                if tr:
                                    issues.append(Issue(
                                        where, "invalid_reference",
                                        t("validate.field_not_in_transform_input", field=col),
                                        file=rfile,
                                        path=_pointer(["fields", col]),
                                        fix=t("validate.fix_declare_in_transform_input_or_use",
                                              field=col,
                                              fields=_names(extracted))))
                                else:
                                    issues.append(Issue(
                                        where, "invalid_reference",
                                        t("validate.field_not_in_columns", field=col),
                                        file=rfile,
                                        path=_pointer(["fields", col]),
                                        fix=t("validate.fix_declare_in_columns_or_use", field=col,
                                              fields=_names(cols))))
        if tr:
            _check_transform(where, iy, path, ds, a.get("timezone") or "UTC", issues)
        for i, check in enumerate(ds.get("checks", [])):
            for col in check.get("columns", []) + check.get("compare", []):
                if col not in cols:
                    issues.append(Issue(where, "invalid_reference",
                                        t("validate.check_not_exists", column=col),
                                        file=iy,
                                        path=path + f"/checks/{i}",
                                        fix=t("validate.use_declared_columns",
                                              columns=_names(cols))))
            if check["type"] == "reconcile":
                qfile = f"{entry.folder.as_posix()}/{check['query']}"
                sql = _read_artifact_file(root, entry, check["query"], issues)
                if sql is not None:
                    for p in sqlsafety.check_query(sql):
                        issues.append(Issue(f"{where} ({check['query']})", p.code, p.message,
                                            file=qfile))


def _check_transform(where: str, iy: str, path: str, ds: dict, tz: str,
                     issues: list[Issue]) -> None:
    spath = path + "/transform/sql"
    check = sqlsafety.check_transform(
        ds["transform"]["sql"],
        {c: d["type"] for c, d in ds["transform"]["input"].items()},
    )
    for p in check.problems:
        issues.append(Issue(
            where, p.code, p.message, file=iy, path=spath,
            fix=t("validate.fix_single_select_from_input"),
        ))
    if check.problems:
        return
    for q in transform.check_output(
        check, ds["transform"]["input"], ds["columns"], tz
    ):
        issues.append(Issue(
            where, q.code, q.message, level=q.level, file=iy, path=spath,
            expected={"columns": {c: d["type"] for c, d in ds["columns"].items()}}
            if q.code in ("transform_mismatch", "transform_float") else None,
            fix=q.fix,
        ))


def _alias_columns(entry: Entry, integrations: dict[str, Entry],
                   issues: list[Issue],
                   invalid: set[str] | frozenset[str] = frozenset()) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    ry = f"{entry.folder.as_posix()}/report.yaml"
    for alias, ref in entry.artifact["uses"].items():
        integ_id, dataset = ref.split(".", 1)
        integ = integrations.get(integ_id)
        if integ is None:
            code = "unknown_dataset"
            if integ_id in invalid:
                issues.append(Issue(entry.key, code,
                                    t("validate.uses_integration_schema_errors", alias=alias,
                                      integration_id=integ_id),
                                    file=ry, path=_pointer(["uses", alias]),
                                    fix=t("validate.fix_correct_integration_errors",
                                          path=f"integrations/{integ_id}/integration.yaml")))
            elif integrations:
                issues.append(Issue(entry.key, code,
                                    t("validate.uses_integration_not_exists", alias=alias,
                                      integration_id=integ_id),
                                    file=ry, path=_pointer(["uses", alias]),
                                    fix=t("validate.fix_use_existing_integration",
                                          integrations=_names(integrations))))
            else:
                issues.append(Issue(entry.key, code,
                                    t("validate.uses_integration_not_exists", alias=alias,
                                      integration_id=integ_id),
                                    file=ry, path=_pointer(["uses", alias]),
                                    fix=t("validate.fix_create_integration_first",
                                          integration_id=integ_id)))
            continue
        ds = integ.artifact.get("datasets", {}).get(dataset)
        if ds is None:
            issues.append(Issue(entry.key, "unknown_dataset",
                                t("validate.uses_integration_no_dataset", alias=alias,
                                  integration_id=integ_id, dataset=dataset),
                                file=ry, path=_pointer(["uses", alias]),
                                fix=t("validate.fix_use_dataset_of_integration",
                                      integration_id=integ_id,
                                      datasets=_names(integ.artifact.get('datasets', {})))))
            continue
        out[alias] = ds["columns"]
    return out


def _ref(ref: str, aliases: dict[str, dict[str, dict]]) -> dict | None:
    if "." not in ref:
        return None
    alias, col = ref.split(".", 1)
    return aliases.get(alias, {}).get(col)


def _check_pdf_views(entry: Entry, ry: str, issues: list[Issue]) -> None:
    """Comprueba que los índices de pdf.views existan en views."""
    a = entry.artifact
    pdf = a.get("pdf") or {}
    pdf_views = pdf.get("views")
    if not pdf_views:
        return
    n = len(a["views"])
    fix = (t("validate.fix_use_valid_view_index", indices=", ".join(str(k) for k in range(n)))
           if n else t("validate.fix_add_views"))
    for i, idx in enumerate(pdf_views):
        if isinstance(idx, int) and not isinstance(idx, bool) and idx >= n:
            issues.append(Issue(
                entry.key, "invalid_reference",
                t("validate.pdf_view_not_exists", i=i, idx=idx, n=n),
                file=ry, path=_pointer(["pdf", "views", i]),
                fix=fix,
            ))


def _product_table_issue(entry: Entry, ry: str, issues: list[Issue],
                         alias: str) -> None:
    """Append a direct_product_table issue for one alias."""
    issues.append(Issue(entry.key, "direct_product_table", t("validate.direct_product_table"),
                        file=ry, path=_pointer(["direct", "tables", alias, "table"]),
                        fix=t("validate.fix_use_prepared_data_table")))


def _direct_source(entry: Entry, ry: str, direct: dict, ctx: DirectContext | None,
                   issues: list[Issue]) -> bool:
    """Validate direct.source permissions; returns is_bi."""
    src = direct["source"].strip()
    low = src.lower()
    is_bi_builtin = low == "bi"
    ctx_sources = ctx.sources if ctx is not None else None
    if is_bi_builtin:
        if ctx is not None and ctx.bi_enabled is False:
            issues.append(Issue(entry.key, "direct_not_allowed",
                                t("validate.direct_reports_bi_disabled"),
                                file=ry, path="/direct/source",
                                expected={"DIRECT_REPORTS_BI": True},
                                fix=t("validate.direct_source_fix")))
        return True
    info = (ctx_sources or {}).get(low)
    name = (info or {}).get("name") or src
    if ctx is None:
        return False
    if ctx.sources is None:
        return False
    if info is None:
        issues.append(Issue(entry.key, "unknown_source",
                            t("validate.source_not_in_installation", source=src),
                            file=ry, path="/direct/source",
                            expected={"kind": "postgresql", "enabled": True, "direct": True},
                            fix=t("validate.direct_source_fix")))
    elif str(info.get("kind", "")).lower() != "postgresql":
        kind = info.get("kind") or "?"
        issues.append(Issue(entry.key, "direct_not_allowed",
                            t("validate.source_type_not_support_direct_reports",
                              name=name, kind=kind),
                            file=ry, path="/direct/source",
                            expected={"kind": "postgresql", "enabled": True, "direct": True},
                            fix=t("validate.direct_source_fix")))
    elif not info.get("enabled", True):
        issues.append(Issue(entry.key, "direct_not_allowed",
                            t("validate.source_disabled", name=name),
                            file=ry, path="/direct/source",
                            expected={"kind": "postgresql", "enabled": True, "direct": True},
                            fix=t("validate.direct_source_fix")))
    elif not info.get("direct"):
        issues.append(Issue(entry.key, "direct_not_allowed",
                            t("validate.source_not_allow_direct_reports", name=name),
                            file=ry, path="/direct/source",
                            expected={"kind": "postgresql", "enabled": True, "direct": True},
                            fix=t("validate.direct_source_fix")))
    return bool((info or {}).get("bi"))


def _direct_aliases(entry: Entry, direct: dict | None, ctx: DirectContext | None,
                    issues: list[Issue]) -> dict[str, dict[str, dict]]:
    """Alias columns from a direct report contract (T006 adds checks)."""
    out: dict[str, dict[str, dict]] = {}
    if not direct:
        return out
    ry = f"{entry.folder.as_posix()}/report.yaml"
    if entry.artifact.get("materialize", "none") != "none":
        issues.append(Issue(entry.key, "direct_materialize",
                            t("validate.materialize_not_applicable_direct_report"),
                            file=ry, path="/materialize",
                            expected={"enum": ["none"]},
                            fix=t("validate.fix_remove_materialize_or_none")))
    is_bi = _direct_source(entry, ry, direct, ctx, issues)
    for alias, tbl in direct["tables"].items():
        schema, table = tbl["table"].split(".", 1)
        if direct_reserved(schema, table):
            _product_table_issue(entry, ry, issues, alias)
        elif (ctx is not None and is_bi and ctx.product_tables
              and f"{schema.lower()}.{table.lower()}" in ctx.product_tables):
            _product_table_issue(entry, ry, issues, alias)
        out[alias] = tbl["columns"]
    return out


def _check_direct_live(entry: Entry, ctx: DirectContext | None,
                      aliases: dict[str, dict[str, dict]], issues: list[Issue],
                      blocked: bool) -> None:
    """Check live structure and personal-data columns for direct reports."""
    if ctx is None:
        return
    a = entry.artifact
    ry = f"{entry.folder.as_posix()}/report.yaml"
    direct_data = a.get("direct")
    if not direct_data:
        return
    src = direct_data["source"].strip()

    if ctx.structure is not None and not blocked:
        requested: list[str] = []
        for tbl in direct_data["tables"].values():
            schema, table = tbl["table"].split(".", 1)
            if not direct_reserved(schema, table):
                low = f"{schema.lower()}.{table.lower()}"
                if low not in requested:
                    requested.append(low)
        if requested:
            try:
                result = ctx.structure(src, requested)
            except Exception as exc:
                result = {"error": type(exc).__name__}
            if isinstance(result, dict):
                error = result.get("error") if result else None
            else:
                error = t("validate.invalid_response")
            if error:
                issues.append(Issue(entry.key, "direct_structure_unchecked",
                                    t("validate.could_not_check_source_structure",
                                      source=src, error=error),
                                    level="warning", file=ry, path="/direct/source",
                                    fix=t("validate.fix_check_source_and_revalidate")))
            else:
                live = {(str(k)).lower(): v
                        for k, v in (result.get("tables") or {}).items()}
                for alias, tbl in direct_data["tables"].items():
                    schema, table = tbl["table"].split(".", 1)
                    if direct_reserved(schema, table):
                        continue
                    key = f"{schema.lower()}.{table.lower()}"
                    info = live.get(key)
                    if info is None:
                        issues.append(Issue(entry.key, "direct_table_missing",
                                            t("validate.table_not_exists_or_unreadable",
                                              table=table, source=src),
                                            file=ry,
                                            path=_pointer(["direct", "tables", alias,
                                                           "table"]),
                                            expected={"table": table},
                                            fix=t("validate.fix_review_table_with_describe")))
                        continue
                    if info.get("product_dependency"):
                        _product_table_issue(entry, ry, issues, alias)
                        continue
                    date_ref = a.get("date") or ""
                    date_alias, _, date_col = date_ref.partition(".")
                    if ctx.warn_rows is not None and date_col and alias == date_alias:
                        reltuples = int(info.get("reltuples") or 0)
                        if reltuples > ctx.warn_rows:
                            if "date_index_columns" in info:
                                indexed = date_col.lower() in {
                                    c.lower() for c in info["date_index_columns"]
                                }
                            else:
                                indexed = bool(info.get("date_indexed"))
                            if not indexed:
                                issues.append(Issue(
                                    entry.key, "direct_big_table",
                                    t("validate.large_table_without_date_index", date_col=date_col),
                                    file=ry,
                                    path=_pointer(["direct", "tables", alias, "table"]),
                                    expected={"rows": reltuples,
                                              "max_rows": ctx.warn_rows,
                                              "index": date_col},
                                    fix=t("validate.fix_index_date_col",
                                          table=table, date_col=date_col),
                                ))
                    live_cols = {name.lower(): str(dtype).lower()
                                 for name, dtype in (info.get("columns") or {}).items()}
                    for col, d in tbl["columns"].items():
                        if col.lower() not in live_cols:
                            issues.append(Issue(entry.key, "direct_column_missing",
                                                t("validate.column_missing_in_table",
                                                  col=col, table=table),
                                                file=ry,
                                                path=_pointer(["direct", "tables", alias,
                                                               "columns", col]),
                                                expected={"column": col},
                                                fix=t("validate.fix_use_column_of_table",
                                                      table=table, columns=_names(live_cols))))
                            continue
                        live_type = live_cols[col.lower()]
                        if live_type not in DIRECT_TYPE_COMPAT[d["type"]]:
                            fits = [t for t, c in DIRECT_TYPE_COMPAT.items()
                                    if live_type in c]
                            if fits:
                                fix = t("validate.use_type", types=t("validate.or_sep").join(fits))
                            else:
                                fix = (t("validate.type_not_allowed_in_direct", type=live_type))
                            issues.append(Issue(entry.key, "direct_column_type",
                                                t("validate.alias_col_type_mismatch",
                                                  alias_col=f"{alias}.{col}", live_type=live_type,
                                                  reported_type=d['type']),
                                                file=ry,
                                                path=_pointer(["direct", "tables", alias,
                                                               "columns", col]),
                                                expected={"type": d["type"],
                                                          "compatible":
                                                              list(DIRECT_TYPE_COMPAT[
                                                                  d["type"]])},
                                                fix=fix))

    if ctx.personal_kind is not None:
        declared: set[str] = set()
        rel = entry.spec.get("folder")
        if rel:
            raw = entry.files.get(spec_path(entry, "spec.md"))
            if raw is not None:
                text = raw.decode("utf-8")
                for line in _PERSONAL_LINE.finditer(text):
                    for token in re.split(r"[\s,;`*]+", line.group(1) or ""):
                        token = token.strip().strip('"\'')
                        if not token:
                            continue
                        token = token.lower()
                        if "." in token:
                            token = token.split(".", 1)[1]
                        declared.add(token)
        for did, d in a.get("dimensions", {}).items():
            try:
                cols = sqlsafety.expression_columns(d["sql"])
            except Exception:
                continue
            for alias, col in sorted(cols):
                if alias not in aliases or col not in aliases[alias]:
                    continue
                kind = ctx.personal_kind(col)
                if kind and col.lower() not in declared:
                    issues.append(Issue(entry.key, "direct_personal_column",
                                        t("validate.dimension_uses_personal_data",
                                          did=did, alias_col=f"{alias}.{col}", kind=kind),
                                        file=ry,
                                        path=_pointer(["dimensions", did, "sql"]),
                                        expected={"personal": col},
                                        fix=t("validate.fix_list_personal_data",
                                              alias_col=f"{alias}.{col}", col=col)))


def _check_direct_spec(entry: Entry, issues: list[Issue]) -> None:
    """Validate mandatory spec lines for direct reports."""
    rel = entry.spec.get("folder")
    if not rel:
        return
    rel_spec = spec_path(entry, "spec.md")
    raw = entry.files.get(rel_spec)
    if raw is None:
        return
    text = raw.decode("utf-8")
    if "uses" in entry.artifact:
        if _DIRECT_SPEC_LINES[0][0].search(text):
            issues.append(Issue(entry.key, "direct_mode_mismatch",
                                t("validate.spec_mode_direct_but_uses_datasets"),
                                file=rel_spec,
                                expected={"direct": {"source": "...", "tables": "..."}},
                                fix=t("validate.fix_declare_direct_or_remove_mode")))
        return
    for regex, line, fix in _DIRECT_SPEC_LINES:
        if not regex.search(text):
            issues.append(Issue(entry.key, "direct_spec_line",
                                t("validate.direct_spec_line", line=line),
                                file=rel_spec, expected={"line": line}, fix=t(fix)))


def _check_joined(entry: Entry, a: dict, aliases: dict[str, dict[str, dict]], ry: str,
                  issues: list[Issue]) -> None:
    """Every alias of `uses` has to be reachable from the date's alias through `joins`.

    The engine builds one FROM for the whole report and answered 409 «Conjuntos sin unión» at render
    time — after the report had validated, been applied and reached the dashboard (reported
    2026-10-25: «Panorama cripto» showed «Conjuntos sin unión: altseason»). The same walk the engine
    does decides it here, where the author can still declare the join.
    """
    base = a["date"].split(".", 1)[0]
    if base not in aliases:
        return                                   # a bad `date` is already its own issue
    joined = {base}
    pending = [j for j in (a.get("joins") or [])
               if isinstance(j, dict) and isinstance(j.get("left"), str)
               and isinstance(j.get("right"), str)]
    while pending:
        progressed = False
        for j in list(pending):
            left, right = j["left"].split(".", 1)[0], j["right"].split(".", 1)[0]
            new = right if left in joined and right not in joined else (
                left if right in joined and left not in joined else None)
            if new is None:
                if left in joined and right in joined:
                    pending.remove(j)            # the engine calls this a repeated join
                    progressed = True
                continue
            joined.add(new)
            pending.remove(j)
            progressed = True
        if not progressed:
            break
    missing = sorted(set(aliases) - joined)
    if not missing:
        return
    where = "direct.tables" if "direct" in a else "uses"
    issues.append(Issue(entry.key, "unjoined_sets",
                        t("validate.unjoined_sets", aliases=", ".join(missing)),
                        file=ry, path=_pointer(where.split(".")),
                        expected={"alias": missing[0], "base": base},
                        fix=t("validate.fix_unjoined_sets",
                              join=_join_hint(aliases, missing, joined, base))))


def _join_hint(aliases: dict[str, dict[str, dict]], missing: list[str], joined: set[str],
               base: str) -> str:
    """The `joins:` line to write: the first shared column between the aliases to unite."""
    for alias in missing:
        for other in sorted(joined):
            shared = [c for c in aliases[alias] if c in aliases.get(other, {})]
            if not shared:
                continue
            dates = [c for c in shared
                     if aliases[alias][c].get("type") in DATE_TYPES
                     and aliases[other][c].get("type") in DATE_TYPES]
            col = sorted(dates or shared)[0]
            return f"joins: [{{left: {other}.{col}, right: {alias}.{col}}}]"
    return f"joins: [{{left: {base}.<columna>, right: {missing[0]}.<columna>}}]"


def _check_report(entry: Entry, integrations: dict[str, Entry], issues: list[Issue],
                  invalid: set[str] | frozenset[str] = frozenset(),
                  direct: DirectContext | None = None) -> None:
    a = entry.artifact
    ry = f"{entry.folder.as_posix()}/report.yaml"
    # El esquema del informe ya aceptó el layout: ahora las referencias y la idoneidad (FR-014).
    issues.extend(report_layout.check_layout(a, file=ry, entry=entry.key))
    _check_pdf_views(entry, ry, issues)
    _check_direct_spec(entry, issues)
    if "direct" in a:
        before = len(issues)
        aliases = _direct_aliases(entry, a["direct"], direct, issues)
        blocked = any(i.code in ("unknown_source", "direct_not_allowed")
                      for i in issues[before:])
        _check_direct_live(entry, direct, aliases, issues, blocked)
        if len(aliases) != len(a["direct"]["tables"]):
            return
    else:
        aliases = _alias_columns(entry, integrations, issues, invalid)
        if len(aliases) != len(a["uses"]):
            return
    colsets = {k: set(v) for k, v in aliases.items()}
    date_cols = sorted({f"{alias}.{col}" for alias, cols in aliases.items()
                        for col, d in cols.items() if d.get("type") in DATE_TYPES})
    for i, j in enumerate(a.get("joins", [])):
        for side in ("left", "right"):
            if _ref(j[side], aliases) is None:
                issues.append(Issue(entry.key, "invalid_reference",
                                    t("validate.join_missing", side_value=j[side]),
                                    file=ry, path=_pointer(["joins", i, side]),
                                    fix=t("validate.fix_use_existing_alias_column",
                                          aliases=_names(aliases))))
    _check_joined(entry, a, aliases, ry, issues)
    date = _ref(a["date"], aliases)
    if date is None or date.get("type") not in DATE_TYPES:
        where = "direct.tables" if "direct" in a else "uses"
        fix = (t("validate.fix_use_date_or_timestamptz", columns=_names(date_cols))
               if date_cols else t("validate.fix_declare_date_in", where=where))
        issues.append(Issue(entry.key, "invalid_reference",
                            t("validate.date_must_be_timestamptz", date=a['date']),
                            file=ry, path="/date", fix=fix))
    metrics = a["metrics"]
    sql_metrics = {mid for mid, m in metrics.items() if "sql" in m}
    for mid, m in metrics.items():
        mpath = _pointer(["metrics", mid])
        if "sql" in m:
            for p in sqlsafety.check_expression(m["sql"], colsets):
                issues.append(Issue(f"{entry.key}.metrics.{mid}", p.code, p.message,
                                    file=ry, path=mpath))
        else:
            try:
                tree = sqlglot.parse_one(f"SELECT {m['formula']}", read="postgres").expressions[0]
            except Exception:
                issues.append(Issue(f"{entry.key}.metrics.{mid}", "invalid_reference",
                                    t("validate.invalid_formula"), file=ry, path=mpath))
                continue
            for node in tree.walk():
                if isinstance(node, exp.Column):
                    ref = metrics.get(node.name)
                    if node.table or ref is None or "sql" not in ref:
                        issues.append(Issue(f"{entry.key}.metrics.{mid}", "invalid_reference",
                                            t("validate.formula_only_sql_metrics",
                                              sql=node.sql()), file=ry, path=mpath,
                                            fix=t("validate.fix_use_sql_metrics",
                                                  sql_metrics=_names(sql_metrics))))
                elif not isinstance(node, exp.Binary | exp.Paren | exp.Literal | exp.Neg
                                    | exp.Identifier):
                    issues.append(Issue(f"{entry.key}.metrics.{mid}", "unsafe_sql",
                                        t("validate.formula_operators"),
                                        file=ry, path=mpath))
    dims = a.get("dimensions", {})
    for did, d in dims.items():
        dpath = _pointer(["dimensions", did])
        for p in sqlsafety.check_expression(d["sql"], colsets):
            issues.append(Issue(f"{entry.key}.dimensions.{did}", p.code, p.message,
                                file=ry, path=dpath + "/sql"))
    if a.get("materialize") == "daily" and "direct" not in a:
        for p in materialize.check_report(a):
            issues.append(Issue(entry.key, "materialize_ineligible", p.message, file=ry,
                                path=p.path, fix=p.fix))
    if direct is not None and direct.dataset_rows is not None and direct.warn_rows \
            and "uses" in a:
        mat = a.get("materialize")
        big_aliases = set()
        for alias, ref in a["uses"].items():
            iid, ds = ref.split(".", 1)
            n = direct.dataset_rows(iid, ds)
            if n is not None and n > direct.warn_rows:
                big_aliases.add(alias)
        if big_aliases and mat != "daily":
            issues.append(Issue(
                entry.key, "materialize_recommended",
                message=(
                    t("validate.estimated_rows_exceeded",
                      aliases=", ".join(sorted(a['uses'][x] for x in big_aliases)),
                      rows=direct.warn_rows)
                ),
                level="warning", file=ry, path="/materialize",
                fix=t("validate.fix_add_materialize_daily")
            ))
        if big_aliases and mat == "daily":
            for did in materialize.used_dimensions(a):
                sql = a['dimensions'][did]['sql'].strip()
                m = re.match(r'^([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)$', sql)
                if not m:
                    continue
                alias, col = m.groups()
                if alias in big_aliases and \
                        aliases.get(alias, {}).get(col, {}).get('type') == 'text':
                    issues.append(Issue(
                        entry.key, "materialize_large",
                        message=(
                            t("validate.text_dimension_large_summary_warning")
                        ),
                        level="warning", file=ry, path=f"/dimensions/{did}/sql",
                        fix=t("validate.fix_use_lower_cardinality_dimension")
                    ))
    for i, v in enumerate(a["views"]):
        vpath = _pointer(["views", i])
        for m in v.get("metrics", []) + ([v["metric"]] if "metric" in v else []):
            if m not in metrics:
                issues.append(Issue(entry.key, "invalid_reference",
                                    t("validate.views_metric_invalid", i=i, metric=m),
                                    file=ry, path=vpath,
                                    fix=t("validate.fix_use_declared_metric",
                                          metrics=_names(metrics))))
        for d in v.get("dimensions", []) + ([v["dimension"]] if "dimension" in v else []):
            if d not in dims:
                fix = (t("validate.fix_declare_dimension", dimension=d)
                       if not dims else t("validate.fix_use_declared_dimension", dims=_names(dims)))
                issues.append(Issue(entry.key, "invalid_reference",
                                    t("validate.views_dimension_invalid",
                                      i=i, dimension=d), file=ry, path=vpath, fix=fix))
    for i, f in enumerate(a.get("filters", [])):
        if f not in dims:
            fix = (t("validate.fix_declare_dimension", dimension=f)
                   if not dims else t("validate.fix_use_declared_dimension", dims=_names(dims)))
            issues.append(Issue(entry.key, "invalid_reference",
                                t("validate.filters_dimension_invalid", dimension=f),
                                file=ry, path=_pointer(["filters", i]), fix=fix))
    for key in ("periods", "compare"):
        conf = a.get(key) or {}
        if "default" in conf and "allowed" in conf and conf["default"] not in conf["allowed"]:
            issues.append(Issue(entry.key, "invalid_reference",
                                t("validate.default_not_allowed", key=key),
                                file=ry, path=_pointer([key, "default"])))
    ai = a.get("ai_narrative") or {}
    for i, m in enumerate(ai.get("inputs", [])):
        if m not in metrics:
            issues.append(Issue(entry.key, "invalid_reference",
                                t("validate.ai_narrative_metric_invalid", metric=m),
                                file=ry, path=_pointer(["ai_narrative", "inputs", i]),
                                fix=t("validate.fix_use_declared_metric", metrics=_names(metrics))))
    if ai.get("enabled") and not ai.get("inputs"):
        issues.append(Issue(entry.key, "invalid_reference",
                            t("validate.ai_narrative_needs_inputs"),
                            file=ry, path="/ai_narrative/inputs"))


def _load_entries(root: Path, kind: str, issues: list[Issue],
                  invalid: set[str] | None = None, *,
                  prefix: Path | None = None, project: str | None = None) -> dict[str, Entry]:
    out: dict[str, Entry] = {}
    base = (root / prefix if prefix else root) / f"{kind}s"
    rel_base = (prefix / f"{kind}s") if prefix else Path(f"{kind}s")
    if not base.is_dir():
        return out
    for folder in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")):
        artifact_path = folder / f"{kind}.yaml"
        key = f"{kind}s/{folder.name}"
        file = f"{(rel_base / folder.name).as_posix()}/{kind}.yaml"
        if not artifact_path.is_file():
            if invalid is not None:
                invalid.add(folder.name)
            issues.append(Issue(key, "schema_error",
                                t("validate.missing_yaml", name=f"{kind}.yaml"), file=file))
            continue
        resolved = artifact_path.resolve()
        if (artifact_path.is_symlink() or resolved.parent != folder.resolve()
                or root.resolve() not in resolved.parents):
            if invalid is not None:
                invalid.add(folder.name)
            issues.append(Issue(key, "schema_error",
                                t("validate.yaml_not_link_or_inside_folder", name=f"{kind}.yaml"),
                                file=file))
            continue
        raw = artifact_path.read_bytes()   # parsed and hashed from the same bytes
        data = _read_yaml(artifact_path, key, issues, raw, file=file)
        if data is not None and _bad_text(data):
            if invalid is not None:
                invalid.add(folder.name)
            issues.append(Issue(key, "schema_error",
                                t("validate.yaml_contains_invalid_chars", name=f"{kind}.yaml"),
                                file=file))
            continue
        if data is None or not _schema_errors(kind, data, key, issues, file=file):
            if invalid is not None:
                invalid.add(folder.name)
            if data is not None and isinstance(data.get("spec"), str):
                tmp = Entry(kind, folder.name, rel_base / folder.name, data,
                            project=project or "principal", project_dir=prefix)
                _check_spec(root, tmp, issues)
            continue
        if data["id"] != folder.name:
            if invalid is not None:
                invalid.add(folder.name)
            issues.append(Issue(key, "schema_error",
                                t("validate.id_must_match_folder",
                                  id=data['id'], folder=folder.name),
                                file=file, path="/id",
                                fix=t("validate.fix_use_id", folder=folder.name)))
            tmp = Entry(kind, folder.name, rel_base / folder.name, data,
                        project=project or "principal", project_dir=prefix)
            _check_spec(root, tmp, issues)
            continue
        entry = Entry(kind, data["id"], rel_base / folder.name, data,
                      project=project or "principal", project_dir=prefix)
        entry.files[file] = raw
        out[entry.id] = entry
    return out


def _check_project_specs(root: Path, slug: str, issues: list[Issue],
                         known: dict[str, str] | None) -> dict[str, dict]:
    """Validate project spec folders and return spec kind/sha data."""
    base = root / "projects" / slug / "specs"
    if not base.is_dir():
        return {}
    out: dict[str, dict] = {}
    by_number: dict[str, list[str]] = {}
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or folder.is_symlink() or folder.name.startswith("."):
            continue
        name = folder.name
        key = f"projects/{slug}/specs/{name}"
        if not layout.SPEC_FOLDER_RE.match(name):
            issues.append(Issue(key, "spec_folder_invalid",
                                t("validate.spec_folder_invalid", folder=name), file=key,
                                fix=t("validate.fix_spec_folder")))
            continue
        by_number.setdefault(name[:3], []).append(name)
        spec_file = folder / "spec.md"
        if not spec_file.is_file() or spec_file.is_symlink():
            continue
        try:
            stat = spec_file.stat()
        except OSError:
            continue
        if stat.st_size > 512 * 1024:
            continue
        data = spec_file.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        kind = layout.spec_kind(text)
        if kind is None:
            issues.append(Issue(key, "spec_kind_missing", t("validate.spec_kind_missing"),
                                file=f"{key}/spec.md",
                                fix=t("validate.fix_spec_kind", kind="integracion")))
            continue
        if kind == "fuente":
            match = SOURCE_LINE_RE.search(text)
            if not match:
                issues.append(Issue(key, "source_line_missing",
                                    t("validate.source_line_missing"), file=f"{key}/spec.md",
                                    fix=t("validate.fix_source_line")))
            else:
                value = match.group(1).strip()
                lower = value.lower()
                if known is not None and lower != "bi" and lower not in known:
                    fix = (t("validate.fix_use_existing_source", sources=_names(known.values()))
                           if known else t("validate.fix_register_source_first"))
                    issues.append(Issue(key, "unknown_source",
                                        t("validate.source_not_in_installation", source=value),
                                        file=f"{key}/spec.md", fix=fix))
        out[name] = {"kind": kind, "sha256": _sha(data)}
    for number, folders in by_number.items():
        if len(folders) > 1:
            issues.append(Issue(f"projects/{slug}/specs", "spec_number_duplicate",
                                t("validate.spec_number_duplicate", number=number,
                                  folders=", ".join(folders)),
                                file=f"projects/{slug}/specs"))
    return out


def _load_distributions(root: Path, slug: str, issues: list[Issue],
                        seen: dict[str, str]) -> dict[str, Entry]:
    """Load project distribution YAML files into Entry objects."""
    base = root / "projects" / slug / "distributions"
    if not base.is_dir():
        return {}
    out: dict[str, Entry] = {}
    for p in sorted(base.iterdir()):
        if p.name.startswith(".") or p.suffix != ".yaml":
            continue
        rel = f"projects/{slug}/distributions/{p.name}"
        key = f"distributions/{p.stem}"
        if p.is_symlink() or not p.is_file():
            issues.append(Issue(key, "schema_error",
                                t("validate.yaml_not_link_or_inside_folder", name=p.name),
                                file=rel))
            continue
        if not layout.ID_RE.match(p.stem):
            issues.append(Issue(key, "schema_error",
                                t("validate.distribution_id_invalid", name=p.name), file=rel))
            continue
        raw = p.read_bytes()
        data = _read_yaml(p, key, issues, raw, file=rel)
        if data is None:
            continue
        if _bad_text(data):
            issues.append(Issue(key, "schema_error",
                                t("validate.yaml_contains_invalid_chars", name=p.name), file=rel))
            continue
        if not _schema_errors("distribution", data, key, issues, file=rel):
            continue
        if data["id"] != p.stem:
            issues.append(Issue(key, "schema_error",
                                t("validate.id_must_match_folder", id=data["id"], folder=p.stem),
                                file=rel, path="/id", fix=t("validate.fix_use_id", folder=p.stem)))
            continue
        if p.stem in seen:
            issues.append(Issue(key, "duplicate_id",
                                t("validate.duplicate_id", id=p.stem, first=seen[p.stem],
                                  second=slug),
                                file=rel, path="/id"))
            continue
        seen[p.stem] = slug
        entry = Entry("distribution", p.stem, Path(f"projects/{slug}/distributions"), data,
                      project=slug, project_dir=Path(f"projects/{slug}"))
        entry.files[rel] = raw
        out[p.stem] = entry
    return out


def _check_distribution(entry: Entry, reports: dict[str, Entry], issues: list[Issue]) -> None:
    """Validate a distribution entry against its referenced report."""
    data = entry.artifact
    file = f"{entry.folder.as_posix()}/{entry.id}.yaml"
    report = reports.get(data["report"])
    if report is None:
        issues.append(Issue(entry.key, "unknown_report",
                            t("validate.unknown_report", report=data["report"],
                              reports=_names(reports)),
                            file=file, path="/report"))
        return
    art = report.artifact
    allowed = (art.get("periods") or {}).get("allowed")
    pdf_enabled = bool((art.get("pdf") or {}).get("enabled"))
    roles = (art.get("access") or {}).get("roles")
    max_days = (data.get("share") or {}).get("max_days")
    for i, sub in enumerate(data.get("subscriptions") or []):
        base = f"/subscriptions/{i}"
        if allowed is not None and sub["period"] not in allowed:
            issues.append(Issue(entry.key, "invalid_reference",
                                t("validate.distribution_period", period=sub["period"],
                                  allowed=", ".join(allowed)),
                                file=file, path=f"{base}/period"))
        attach = sub.get("attach_pdf", True)
        link_days = sub.get("link_days")
        if attach and not pdf_enabled:
            issues.append(Issue(entry.key, "invalid_reference", t("validate.distribution_pdf"),
                                file=file, path=f"{base}/attach_pdf",
                                fix=t("validate.fix_distribution_pdf")))
        if not attach and link_days is None:
            issues.append(Issue(entry.key, "invalid_reference",
                                t("validate.distribution_nothing"), file=file, path=base))
        if link_days is not None and max_days is not None and link_days > max_days:
            issues.append(Issue(entry.key, "invalid_reference",
                                t("validate.distribution_link_days", days=link_days,
                                  max=max_days),
                                file=file, path=f"{base}/link_days"))
        if roles is not None:
            for role in sub["recipients"]["roles"]:
                if role not in roles:
                    issues.append(Issue(entry.key, "distribution_role",
                                        t("validate.distribution_role", role=role),
                                        level="warning", file=file,
                                        path=f"{base}/recipients/roles"))


def _ignored_files(project_root: Path) -> list[str]:
    """Project-relative files outside the project layout (never follows symlinks)."""
    ignored: list[str] = []
    stack = [project_root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir())
        except OSError:
            continue
        for child in children:
            rel = child.relative_to(project_root).as_posix()
            if child.is_symlink():
                ignored.append(rel)
                continue
            if child.is_dir():
                stack.append(child)
            elif child.is_file() and not layout.is_allowed(rel):
                ignored.append(rel)
    return sorted(ignored)


def _validate_v2(root: Path, issues: list[Issue], known: dict[str, str] | None,
                 direct: DirectContext | None) -> tuple[dict, dict, dict, dict]:
    """Workspace layout v2 (feature 020): artifacts and specs inside projects/<slug>/."""
    integrations: dict[str, Entry] = {}
    reports: dict[str, Entry] = {}
    distributions: dict[str, Entry] = {}
    projects: dict[str, dict] = {}
    invalid_integrations: set[str] = set()
    seen: dict[str, str] = {}
    projects_root = root / "projects"
    if projects_root.is_dir():
        for child in sorted(projects_root.iterdir()):
            if child.name.startswith(".") or not child.is_dir():
                continue
            slug = child.name
            key = f"projects/{slug}"
            if child.is_symlink():
                issues.append(Issue(key, "path_unsafe", t("validate.project_symlink", slug=slug),
                                    file=key))
                continue
            if not layout.ID_RE.match(slug):
                issues.append(Issue(key, "project_slug_invalid",
                                    t("validate.project_slug_invalid", slug=slug), file=key))
                continue
            project_file = child / "project.yaml"
            pfile = f"{key}/project.yaml"
            project_sha = None
            if not project_file.is_file() or project_file.is_symlink():
                issues.append(Issue(key, "schema_error",
                                    t("validate.missing_yaml", name="project.yaml"), file=pfile))
            else:
                raw = project_file.read_bytes()
                data = _read_yaml(project_file, key, issues, raw, file=pfile)
                if data is not None and isinstance(data.get("created"), date):
                    data["created"] = data["created"].isoformat()   # unquoted YAML date
                if data is not None and _bad_text(data):
                    issues.append(Issue(key, "schema_error",
                                        t("validate.yaml_contains_invalid_chars",
                                          name="project.yaml"), file=pfile))
                elif data is not None and _schema_errors("project", data, key, issues,
                                                         file=pfile):
                    if data["slug"] != slug:
                        issues.append(Issue(key, "project_slug_mismatch",
                                            t("validate.project_slug_mismatch", slug=data["slug"],
                                              folder=slug), file=pfile, path="/slug"))
                project_sha = _sha(raw)
            projects[slug] = {
                "project": project_sha,
                "specs": _check_project_specs(root, slug, issues, known),
                "ignored": _ignored_files(child),
            }
            for kind, target in (("integration", integrations), ("report", reports)):
                invalid = invalid_integrations if kind == "integration" else None
                loaded = _load_entries(root, kind, issues, invalid, prefix=Path(key),
                                       project=slug)
                for entry_id, entry in loaded.items():
                    if entry_id in target:
                        first = target[entry_id].project
                        issues.append(Issue(entry.key, "duplicate_id",
                                            t("validate.duplicate_id", id=entry_id, first=first,
                                              second=slug),
                                            file=f"{entry.folder.as_posix()}/{kind}.yaml",
                                            path="/id"))
                    else:
                        target[entry_id] = entry
            distributions.update(_load_distributions(root, slug, issues, seen))
    for entry in integrations.values():
        _check_spec(root, entry, issues)
        _check_integration(root, entry, issues, known)
    for entry in reports.values():
        _check_spec(root, entry, issues)
        _check_report(entry, integrations, issues, invalid_integrations, direct)
    for entry in distributions.values():
        _check_spec(root, entry, issues)
        _check_distribution(entry, reports, issues)
    return integrations, reports, distributions, projects


def validate(root: Path | str, *, known_sources: set[str] | None = None,
             direct: DirectContext | None = None) -> Result:
    root = Path(root)
    issues: list[Issue] = []
    name, manifest_data = None, {}
    manifest = root / "bizview.yaml"
    if manifest.is_file():
        data = _read_yaml(manifest, "bizview.yaml", issues, file="bizview.yaml")
        if data is not None and _bad_text(data):
            issues.append(Issue("bizview.yaml", "schema_error",
                                t("validate.yaml_contains_invalid_chars", name="bizview.yaml"),
                                file="bizview.yaml"))
        elif data is not None and _schema_errors("workspace", data, "bizview.yaml", issues,
                                                file="bizview.yaml"):
            name, manifest_data = data["name"], data
    else:
        issues.append(Issue("bizview.yaml", "schema_error", t("validate.missing_yaml_in_root"),
                            file="bizview.yaml"))
    lay = _layout(root)
    known = ({s.strip().lower(): s.strip() for s in known_sources}
             if known_sources is not None else None)
    if lay == "mixed":
        issues.append(Issue("workspace", "mixed_layout", t("validate.mixed_layout"),
                            fix=t("validate.fix_mixed_layout")))
        return Result(issues, {}, {}, None, name, manifest_data, layout="mixed")
    invalid_integrations: set[str] = set()
    if lay == "v2":
        integrations, reports, distributions, projects = _validate_v2(root, issues, known,
                                                                       direct)
        result = Result(issues, integrations, reports, None, name, manifest_data, layout="v2",
                        projects=projects, distributions=distributions)
    else:
        integrations = _load_entries(root, "integration", issues, invalid_integrations)
        reports = _load_entries(root, "report", issues)
        for entry in integrations.values():
            _check_spec(root, entry, issues)
            _check_integration(root, entry, issues, known)
        for entry in reports.values():
            _check_spec(root, entry, issues)
            _check_report(entry, integrations, issues, invalid_integrations, direct)
        result = Result(issues, integrations, reports, None, name, manifest_data)
    if result.ok:
        result.lock = build_lock(result)
    return result


def build_lock(result: Result) -> dict:
    if result.layout != "v2":
        entries = {}
        for entry in [*result.integrations.values(), *result.reports.values()]:
            entries[entry.key] = {
                "spec": {"folder": entry.spec["folder"], "status": entry.spec["status"],
                         "title": entry.spec["title"], "sha256": entry.spec["sha256"]},
                "artifacts": {path: _sha(data) for path, data in sorted(entry.files.items())
                              if not path.startswith("specs/")},
            }
        return {"generated_by": f"bizview-cli {__version__}",
                "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "workspace": result.name,
                "manifest": _sha(json.dumps(result.manifest, sort_keys=True).encode()),
                "entries": entries}
    entries = {}
    all_entries = [*result.integrations.values(), *result.reports.values(),
                   *result.distributions.values()]
    for entry in all_entries:
        spec_prefix = f"{entry.project_dir.as_posix()}/specs/"
        entries[entry.key] = {
            "project": entry.project,
            "spec": {"folder": entry.spec["folder"], "status": entry.spec["status"],
                     "title": entry.spec["title"], "sha256": entry.spec["sha256"]},
            "artifacts": {path: _sha(data) for path, data in sorted(entry.files.items())
                          if not path.startswith(spec_prefix)},
        }
    return {"generated_by": f"bizview-cli {__version__}",
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "workspace": result.name,
            "manifest": _sha(json.dumps(result.manifest, sort_keys=True).encode()),
            "layout": "v2",
            "projects": {slug: {"project": p["project"], "specs": p["specs"]}
                         for slug, p in sorted(result.projects.items())},
            "entries": entries}


def lock_differences(expected: dict, actual: dict) -> list[str]:
    """Entries whose specs or artifacts differ between two locks (timestamps ignored)."""
    diffs = []
    if expected.get("manifest") != actual.get("manifest"):
        diffs.append("bizview.yaml")
    a, b = expected.get("entries", {}), actual.get("entries", {})
    for key in sorted(set(a) | set(b)):
        ea, eb = a.get(key), b.get(key)
        if ea is None or eb is None:
            diffs.append(key)
        elif ea["spec"]["sha256"] != eb["spec"]["sha256"] or ea["artifacts"] != eb["artifacts"]:
            diffs.append(key)
    if expected.get("layout") != actual.get("layout"):
        diffs.append("layout")
    pa, pb = expected.get("projects") or {}, actual.get("projects") or {}
    for slug in sorted(set(pa) | set(pb)):
        if slug not in pa or slug not in pb or pa[slug] != pb[slug]:
            diffs.append(f"projects/{slug}")
    return diffs


def lock_checksum(lock: dict) -> str:
    stable = {k: v for k, v in lock.items() if k not in ("generated_at", "generated_by")}
    return _sha(json.dumps(stable, sort_keys=True).encode())


def write_lock(root: Path | str, lock: dict) -> Path:
    path = Path(root) / "bizview.lock"
    path.write_text("# Generated by `bizview validate`. Do not edit.\n"
                    + yaml.safe_dump(lock, sort_keys=True, allow_unicode=True), encoding="utf-8")
    return path


def read_lock(root: Path | str) -> dict | None:
    path = Path(root) / "bizview.lock"
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))
