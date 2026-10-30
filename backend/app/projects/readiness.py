"""Readiness gate (feature 017, FR-005/FR-009): what is still pending before "Listo para aplicar".

Readiness imports only the dependency-free personal module from app.assistant to avoid a cycle
with preview/origin.
"""
import hashlib
import re
from collections.abc import Iterable

import yaml
from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.i18n import t
from app.models import AssistantMessage
from app.projects.personal import personal_kind, query_columns, request_columns

INTEGRATION_FILE = re.compile(r"^integrations/([^/]+)/integration\.yaml$")
REPORT_FILE = re.compile(r"^reports/([^/]+)/report\.yaml$")
# A project's own metadata: a project holding only these has no draft yet (feature 020).
PROJECT_META = frozenset({"project.yaml", ".specify/memory/constitution.md"})
QUERY_FILE = re.compile(r"^integrations/([^/]+)/queries/[^/]+\.sql$")
REQUEST_FILE = re.compile(r"^integrations/([^/]+)/requests/[^/]+\.yaml$")
# English specs (feature 022) use "Personal data".
_PERSONAL_LINE = re.compile(
    r"^\s*[-*]?\s*\*\*(?:Datos personales|Personal data)\*\*:\s*(.*)$", re.MULTILINE
)

_AFFIRMATIVE = (
    "sí", "si", "confirmo", "confirmado", "incluye", "inclúyela", "inclúyelo",
    "inclúyelas", "inclúyelos", "incluir", "de acuerdo", "ok", "vale",
    "yes", "confirm", "confirmed", "include", "include it", "agreed",
)
_NEGATION = (
    "no", "excluye", "exclúyela", "exclúyelo", "excluir", "sin", "quita",
    "quítala", "quítalo", "omite", "omítela",
    "exclude", "without", "remove", "omit", "drop",
)


def file_sha(text: str) -> str:
    """SHA-256 of UTF-8 text (same as origin.run_check query_check sha)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint(files: dict[str, str]) -> str:
    """Deterministic hash over sorted draft files: path NUL text NUL."""
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[path].encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _load(text: str) -> dict | None:
    try:
        loaded = yaml.safe_load(text)
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _word_in(word: str, text: str | None) -> bool:
    if not text:
        return False
    return re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", text, re.IGNORECASE
    ) is not None


def confirmed_columns(
    question: str | None, answer: str, flagged: Iterable[str] = ()
) -> list[str]:
    """Return columns the user explicitly confirmed in answer, given the assistant question."""
    if not question:
        return []
    flagged_low = {str(c).lower() for c in flagged}
    candidates: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", question):
        low = token.lower()
        if low in seen:
            continue
        if low in flagged_low or personal_kind(token):
            seen.add(low)
            candidates.append(low)
    if not candidates:
        return []

    def any_pattern(patterns: Iterable[str]) -> bool:
        return any(
            re.search(rf"(?<![\w]){re.escape(p)}(?![\w])", answer, re.IGNORECASE)
            for p in patterns
        )

    if any_pattern(_NEGATION) or not any_pattern(_AFFIRMATIVE):
        return []
    return [c for c in candidates if _word_in(c, answer)]


def record_personal_confirmations(session, answer: str) -> list[str]:
    """Record newly confirmed personal columns in working_state["personal_confirmed"].

    Uses top-level working_state["personal_confirmed"] (list[str]); working_state["decisions"]
    is already used by another tool.
    """
    db = object_session(session)
    question: str | None = None
    if db is not None:
        question = db.execute(
            select(AssistantMessage.content)
            .where(
                AssistantMessage.session_id == session.id,
                AssistantMessage.role == "assistant",
                AssistantMessage.content != "",
            )
            .order_by(AssistantMessage.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    personal = (session.working_state or {}).get("personal") or {}
    flagged: list[str] = []
    if isinstance(personal, dict):
        for cols in personal.values():
            if isinstance(cols, dict):
                flagged.extend(str(c) for c in cols.keys())

    new = confirmed_columns(question, answer, flagged)
    if not new:
        return []
    state = dict(session.working_state or {})
    current = state.get("personal_confirmed") or []
    if not isinstance(current, list):
        current = []
    current_low = {str(c).lower() for c in current}
    added: list[str] = []
    for col in new:
        low = col.lower()
        if low not in current_low:
            added.append(low)
            current_low.add(low)
    if not added:
        return []
    state["personal_confirmed"] = (current + added)[-100:]
    session.working_state = state
    return added


def _report_pending(path: str, doc: dict, files: dict[str, str]) -> list[dict]:
    pending: list[dict] = []

    def proposal_no_dimensions(uses: dict) -> str:
        if not isinstance(uses, dict):
            return (
                t("readiness.no_dimensions")
            )
        for alias, target in uses.items():
            if not isinstance(target, str) or target.count(".") != 1:
                continue
            integration, dataset = target.split(".", 1)
            integration_text = files.get(f"integrations/{integration}/integration.yaml")
            if not integration_text:
                continue
            integration_doc = _load(integration_text)
            if not integration_doc:
                continue
            datasets = integration_doc.get("datasets") or {}
            if not isinstance(datasets, dict):
                continue
            ds = datasets.get(dataset)
            if not isinstance(ds, dict):
                continue
            pk = ds.get("primary_key") or []
            if not isinstance(pk, list):
                pk = []
            columns = ds.get("columns") or {}
            if not isinstance(columns, dict):
                continue

            eligible: list[str] = []
            for col, meta in columns.items():
                col_str = str(col)
                if (
                    re.fullmatch(r"[a-z][a-z0-9_]{0,40}", col_str)
                    and isinstance(meta, dict)
                    and meta.get("type") == "text"
                    and col_str not in pk
                    and not personal_kind(col_str)
                ):
                    eligible.append(col_str)
            if not eligible:
                continue

            chosen = None
            for col in eligible:
                meta = columns.get(col)
                if isinstance(meta, dict) and isinstance(meta.get("enum"), list) and meta["enum"]:
                    chosen = col
                    break
            if chosen is None:
                for col in eligible:
                    low = col.lower()
                    if low != "id" and not low.endswith("_id"):
                        chosen = col
                        break
            if chosen is None:
                continue

            label = chosen.replace("_", " ").capitalize()
            return (
                t("readiness.no_dimensions_proposal",
                  proposal=f"dimensions: {{{chosen}: {{label: {label}, sql: {alias}.{chosen}}}}}")
            )
        return (
            t("readiness.no_dimensions")
        )

    dimensions = doc.get("dimensions")
    has_dimensions = isinstance(dimensions, dict) and bool(dimensions)
    if not has_dimensions:
        pending.append({
            "code": "report_dimensions",
            "file": path,
            "message": proposal_no_dimensions(doc.get("uses") or {}),
        })

    filters = doc.get("filters")
    has_filters = isinstance(filters, list) and bool(filters)
    if not has_filters:
        if has_dimensions and isinstance(dimensions, dict):
            dims = list(dimensions.keys())[:3]
            pending.append({
                "code": "report_dimensions",
                "file": path,
                "message": t("readiness.no_filters_proposal",
                             filters=', '.join(str(d) for d in dims)),
            })
        else:
            pending.append({
                "code": "report_dimensions",
                "file": path,
                "message": t("readiness.no_filters"),
            })

    return pending


def _direct_pending(
    session,
    path: str,
    text: str,
    doc: dict,
    files: dict,
    personal_by_src: dict[str, dict[str, str]],
    confirmed_set: set[str],
) -> list[dict]:
    pending: list[dict] = []
    direct = doc.get("direct")
    if not isinstance(direct, dict):
        return pending
    source = str(direct.get("source") or "").strip()
    rid = REPORT_FILE.match(path).group(1)
    chk = (session.query_checks or {}).get(path)
    sha = file_sha(text)
    if not isinstance(chk, dict) or chk.get("sha256") != sha:
        pending.append({
            "code": "query_check",
            "file": path,
            "message": (
                t("readiness.direct_check", source=source, path=path)
            ),
        })
    elif not chk.get("ok"):
        pending.append({
            "code": "query_check",
            "file": path,
            "message": (
                t("readiness.direct_check_failed",
                  error=chk.get('error') or t("readiness.unknown_error"))
            ),
        })

    warnings = (session.validation or {}).get("warnings") or []
    for warning in warnings:
        if (isinstance(warning, dict)
                and warning.get("code") == "direct_structure_unchecked"
                and warning.get("file") == path):
            pending.append({
                "code": "direct_structure",
                "file": path,
                "message": (
                    t("readiness.direct_structure")
                ),
            })
            break

    preview = session.preview or {}
    if (preview.get("status") == "succeeded"
            and preview.get("fingerprint") == fingerprint(files)
            and (preview.get("reports") or {}).get(rid, {}).get("status") != "succeeded"):
        pending.append({
            "code": "preview",
            "file": path,
            "message": (
                t("readiness.direct_preview")
            ),
        })

    flagged = personal_by_src.get(source.lower()) or {}
    declared = ""
    spec_key = doc.get("spec")
    if isinstance(spec_key, str):
        spec_text = files.get(f"{spec_key}/spec.md")
        if isinstance(spec_text, str):
            declared = " ".join(_PERSONAL_LINE.findall(spec_text))
    seen: set[str] = set()
    tables = direct.get("tables")
    if isinstance(tables, dict):
        for table_def in tables.values():
            if not isinstance(table_def, dict):
                continue
            columns = table_def.get("columns")
            if not isinstance(columns, dict):
                continue
            for col in columns:
                col_name = str(col)
                key = col_name.lower()
                if key in seen:
                    continue
                seen.add(key)
                kind = flagged.get(key) or personal_kind(col_name)
                if not kind:
                    continue
                if key in confirmed_set and _word_in(col_name, declared):
                    continue
                pending.append({
                    "code": "personal_data",
                    "file": path,
                    "message": (
                        t("readiness.personal", column=col_name, kind=kind)
                    ),
                })
    return pending


def compute(session, user_texts: list[str] | None = None) -> dict:
    """Return ready + pending issues for the session's current draft.

    `user_texts` is unused (kept for call sites): personal-data confirmations come from
    working_state["personal_confirmed"] (see record_personal_confirmations).
    """
    pending: list[dict] = []
    files = (session.draft or {}).get("files") or {}
    if not any(path not in PROJECT_META for path in files):
        return {"ready": False, "pending": [{"code": "draft", "file": None,
                                              "message": t("readiness.no_draft")}]}
    valid = (session.validation or {}).get("valid") is True
    # Feature 037: the composition (this project + the applied snapshot of the others) must also be
    # valid; a project that is itself fine is blocked by the ones it shares the workspace with, and
    # the pending entry names them instead of hiding the problem or blaming this project.
    validation = session.validation or {}
    composed = validation.get("composed_valid", valid) is True
    blockers = sorted(slug for slug, counts in (validation.get("other_projects") or {}).items()
                      if (counts or {}).get("errors"))
    workspace_errors = int(validation.get("workspace_errors") or 0)

    personal_by_src: dict[str, dict[str, str]] = {}
    for src, flags in ((session.working_state or {}).get("personal") or {}).items():
        personal_by_src[str(src).strip().lower()] = {
            str(c).lower(): str(k) for c, k in (flags or {}).items()
        }
    confirmed = (session.working_state or {}).get("personal_confirmed") or []
    confirmed_set = {str(c).lower() for c in confirmed} if isinstance(confirmed, list) else set()

    for path in sorted(files):
        text = files[path]
        if INTEGRATION_FILE.match(path):
            doc = _load(text)
            if not doc:
                continue
            datasets = doc.get("datasets") or {}
            if isinstance(datasets, dict):
                src = str(doc.get("source") or "").strip().lower()
                flagged = personal_by_src.get(src) or {}
                declared = ""
                spec = doc.get("spec")
                if isinstance(spec, str):
                    spec_text = files.get(f"{spec}/spec.md") or ""
                    declared = " ".join(_PERSONAL_LINE.findall(spec_text))
                for name, ds in datasets.items():
                    if not isinstance(ds, dict):
                        continue
                    pk = ds.get("primary_key")
                    if not isinstance(pk, list) or not pk:
                        pending.append({
                            "code": "primary_key", "file": path,
                            "message": f"El dataset «{name}» no declara primary_key.",
                        })
                    inc = ds.get("incremental")
                    if not (isinstance(inc, dict)
                            and (inc.get("mode") == "full" or "window_days" in inc)):
                        pending.append({
                            "code": "incremental", "file": path,
                            "message": f"El dataset «{name}» no declara incremental "
                                      "(mode: full o window_days).",
                        })
                    checks = ds.get("checks")
                    if not isinstance(checks, list) or not checks:
                        pending.append({
                            "code": "checks", "file": path,
                            "message": f"El dataset «{name}» no declara checks.",
                        })
                    columns = ds.get("columns") or {}
                    candidate_names: list[str] = []
                    seen: set[str] = set()
                    if isinstance(columns, dict):
                        for col in columns.keys():
                            low = str(col).lower()
                            if low not in seen:
                                seen.add(low)
                                candidate_names.append(str(col))
                    extract = ds.get("extract") or {}
                    if isinstance(extract, dict):
                        query_ref = extract.get("query")
                        if isinstance(query_ref, str):
                            query_path = f"integrations/{path.split('/')[1]}/{query_ref}"
                            query_text = files.get(query_path)
                            if query_text:
                                for col in sorted(query_columns(query_text)):
                                    low = col.lower()
                                    if low not in seen:
                                        seen.add(low)
                                        candidate_names.append(col)
                        request_ref = extract.get("request")
                        if isinstance(request_ref, str):
                            request_path = f"integrations/{path.split('/')[1]}/{request_ref}"
                            request_text = files.get(request_path)
                            if request_text:
                                request_doc = _load(request_text)
                                if request_doc:
                                    for col in sorted(request_columns(request_doc)):
                                        low = col.lower()
                                        if low not in seen:
                                            seen.add(low)
                                            candidate_names.append(col)
                    for col in candidate_names:
                        kind = flagged.get(str(col).lower()) or personal_kind(str(col))
                        if kind and not (
                            str(col).lower() in confirmed_set
                            and _word_in(str(col), declared)
                        ):
                            pending.append({
                                "code": "personal_data", "file": path,
                                "message": t("readiness.personal", column=col, kind=kind),
                            })
        elif REPORT_FILE.match(path):
            doc = _load(text)
            if not doc:
                continue
            pdf = doc.get("pdf")
            if not (isinstance(pdf, dict) and pdf.get("enabled") is True):
                pending.append({
                    "code": "pdf", "file": path,
                    "message": t("readiness.no_pdf"),
                })
            pending.extend(_report_pending(path, doc, files))
            if isinstance(doc.get("direct"), dict):
                pending.extend(_direct_pending(
                    session, path, text, doc, files, personal_by_src, confirmed_set
                ))
        elif QUERY_FILE.match(path) or REQUEST_FILE.match(path):
            chk = (session.query_checks or {}).get(path)
            sha = file_sha(text)
            if not chk or chk.get("sha256") != sha:
                pending.append({
                    "code": "query_check", "file": path,
                    "message": t("readiness.query_check"),
                })
            elif not chk.get("ok"):
                pending.append({
                    "code": "query_check", "file": path,
                    "message": t("readiness.query_check_failed",
                                 error=chk.get('error') or t("readiness.columns_mismatch")),
                })

    preview = session.preview or {}
    fp = fingerprint(files)
    status = preview.get("status")
    # Feature 038: applying a project retires its preview (`replaced`) because the schemas are
    # gone. It ran on exactly these files, so it still counts as «previewed»: the gate asks for a
    # preview before an apply, and re-applying identical files needs none.
    if status in ("succeeded", "replaced") and preview.get("fingerprint") == fp:
        pass
    elif status in ("succeeded", "replaced"):
        pending.append({
            "code": "preview", "file": None,
            "message": t("readiness.preview_stale"),
        })
    elif status == "failed":
        pending.append({
            "code": "preview", "file": None,
            "message": t("readiness.preview_failed"),
        })
    elif status == "pending":
        pending.append({"code": "preview", "file": None,
                        "message": t("readiness.preview_running")})
    else:
        pending.append({
            "code": "preview", "file": None,
            "message": t("readiness.preview_needed"),
        })

    if valid and blockers:
        pending.append({
            "code": "other_projects", "file": None,
            "message": t("projects.other_projects_block", projects=", ".join(blockers)),
        })
    if valid and workspace_errors:
        pending.append({
            "code": "workspace", "file": None,
            "message": t("projects.workspace_block", count=workspace_errors),
        })

    ready = valid and composed and not pending
    return {"ready": ready, "pending": pending}
