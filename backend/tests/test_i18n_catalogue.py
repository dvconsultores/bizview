"""Feature 022 T037: backend catalogue guard (FR-010, SC-002)."""
import ast
import string
from pathlib import Path

import app
from app.i18n import en, es

APP_DIR = Path(app.__file__).parent


def _iter_app_python_files():
    for path in sorted(APP_DIR.rglob("*.py")):
        if path.is_relative_to(APP_DIR / "i18n"):
            continue
        yield path


def _fmt_fields(s):
    return {part[1] for part in string.Formatter().parse(s) if part[1] is not None}


def _call_name(call):
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        if func.attr in {"M", "t", "tn"}:
            if isinstance(func.value, ast.Name) and func.value.id == "i18n":
                return func.attr
            return None
        if func.attr in {"ApiError", "ReportError", "forbidden", "not_found", "validation"}:
            return func.attr
    return None


def _is_literal_string_arg(arg):
    if isinstance(arg, ast.JoinedStr):
        return True
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return True
    return False


def _calls():
    for path in _iter_app_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                yield (path.relative_to(APP_DIR), node)


def test_key_parity():
    es_keys = set(es.MESSAGES)
    en_keys = set(en.MESSAGES)
    missing_es = sorted(en_keys - es_keys)
    missing_en = sorted(es_keys - en_keys)
    assert es_keys == en_keys, f"Missing in es: {missing_es}, missing in en: {missing_en}"


def test_placeholder_parity():
    mismatches = []
    common_keys = set(es.MESSAGES) & set(en.MESSAGES)
    for key in common_keys:
        es_fields = _fmt_fields(es.MESSAGES[key])
        en_fields = _fmt_fields(en.MESSAGES[key])
        if es_fields != en_fields:
            mismatches.append((key, es_fields, en_fields))
    assert not mismatches, f"Placeholder mismatches: {mismatches}"


def test_no_empty_values():
    for lang_name, messages in [("es", es.MESSAGES), ("en", en.MESSAGES)]:
        for key, value in messages.items():
            assert value and value.strip(), f"Empty value in {lang_name}: {key}"


def test_every_literal_id_exists():
    missing = []
    for rel_path, node in _calls():
        name = _call_name(node)
        if name not in {"M", "t", "tn"}:
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if not _is_literal_string_arg(first_arg):
            continue
        key = first_arg.value if isinstance(first_arg, ast.Constant) else None
        if key is None:
            continue
        if name == "tn" and key:
            if key + ".one" not in es.MESSAGES or key + ".one" not in en.MESSAGES:
                missing.append(f"{rel_path}:{node.lineno}: {key}.one")
            if key + ".other" not in es.MESSAGES or key + ".other" not in en.MESSAGES:
                missing.append(f"{rel_path}:{node.lineno}: {key}.other")
        elif key not in es.MESSAGES or key not in en.MESSAGES:
            missing.append(f"{rel_path}:{node.lineno}: {key}")
    assert not missing, f"Unknown literal catalogue keys: {missing}"


def test_no_literal_error_messages():
    error_indexes = {
        "ApiError": 2,
        "ReportError": 0,
        "forbidden": 0,
        "not_found": 0,
        "validation": 1,
    }
    violations = []
    for rel_path, node in _calls():
        name = _call_name(node)
        if name in error_indexes:
            index = error_indexes[name]
            if len(node.args) > index:
                arg = node.args[index]
                if _is_literal_string_arg(arg):
                    violations.append(f"{rel_path}:{node.lineno}: {name}")
            for keyword in node.keywords:
                if keyword.arg == "message" and _is_literal_string_arg(keyword.value):
                    violations.append(f"{rel_path}:{node.lineno}: {name}")
    assert not violations, f"Literal error messages found: {violations}"
