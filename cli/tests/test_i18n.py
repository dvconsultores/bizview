"""Feature 022 T038: CLI language resolution and catalogue parity."""

from __future__ import annotations

import string

import pytest

from bizview_cli.i18n import DEFAULT, current, normalize, set_resolver, t, use_lang
from bizview_cli.i18n import en as en_catalogue
from bizview_cli.i18n import es as es_catalogue


@pytest.fixture(autouse=True)
def _clean_language_env(monkeypatch):
    """Remove locale variables and the resolver around every test."""

    for var in ("BIZVIEW_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    set_resolver(None)
    yield
    for var in ("BIZVIEW_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    set_resolver(None)


def test_default_is_spanish_with_no_env():
    assert current() == DEFAULT
    assert current() == "es"


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("en_US.UTF-8", "en"),
        ("es-VE", "es"),
        ("en.UTF-8", "en"),
        ("C.UTF-8", None),
        ("", None),
        (None, None),
        (" en ", "en"),
        ("En_GB@euro", "en"),
        ("fr_FR.UTF-8", None),
    ],
)
def test_normalize(tag, expected):
    assert normalize(tag) == expected


def test_lang_env_selects_english(monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert current() == "en"


def test_lc_all_decides_alone(monkeypatch):
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert current() == "es"


def test_bizview_lang_wins_over_lc_all(monkeypatch):
    monkeypatch.setenv("BIZVIEW_LANG", "en")
    monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
    assert current() == "en"


def test_resolver_wins_over_bizview_lang(monkeypatch):
    monkeypatch.setenv("BIZVIEW_LANG", "es")
    set_resolver(lambda: "en")
    assert current() == "en"


def test_resolver_exception_is_ignored(monkeypatch):
    monkeypatch.setenv("BIZVIEW_LANG", "es")

    def broken_resolver():
        raise RuntimeError("boom")

    set_resolver(broken_resolver)
    assert current() == "es"


def test_use_lang_overrides_resolver_and_restores(monkeypatch):
    monkeypatch.setenv("BIZVIEW_LANG", "es")
    set_resolver(lambda: "es")
    with use_lang("en"):
        assert current() == "en"
    assert current() == "es"


def test_t_renders_params_and_keeps_unknown_placeholder():
    template = "Hello {name}, welcome to {site}"
    key = "cli.lang_help"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("BIZVIEW_LANG", "en")
        mp.setattr(en_catalogue, "MESSAGES", {key: template})
        assert t(key, name="Ada") == "Hello Ada, welcome to {site}"


def test_t_missing_key_returns_key():
    assert t("missing.key.example") == "missing.key.example"


def test_catalogue_key_parity():
    assert set(es_catalogue.MESSAGES) == set(en_catalogue.MESSAGES)


def test_placeholder_parity_for_every_key():
    for key in es_catalogue.MESSAGES:
        es_fields = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(es_catalogue.MESSAGES[key])
            if field_name is not None
        }
        en_fields = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(en_catalogue.MESSAGES[key])
            if field_name is not None
        }
        assert es_fields == en_fields, key


def test_no_empty_values():
    for messages in (es_catalogue.MESSAGES, en_catalogue.MESSAGES):
        for key, value in messages.items():
            assert value, key


def test_validate_messages_follow_language(tmp_path):
    from bizview_cli.validate import validate

    result = validate(tmp_path)
    issue = next(i for i in result.issues if i.code == "schema_error")
    assert issue.message == "falta bizview.yaml en la raíz"

    with use_lang("en"):
        result_en = validate(tmp_path)
    issue_en = next(i for i in result_en.issues if i.code == "schema_error")
    assert issue_en.message == "missing bizview.yaml at the root"


def test_every_literal_cli_id_exists():
    import ast
    import re
    from pathlib import Path

    import bizview_cli

    pkg = Path(bizview_cli.__file__).parent
    id_pattern = re.compile(r"^validate\.(type|spec_line)\.[a-z_]+$")
    failures = []

    for path in sorted(pkg.rglob("*.py")):
        if path.is_relative_to(pkg / "i18n"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        required_keys = {}

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
            ):
                if (
                    node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    key = node.args[0].value
                    required_keys.setdefault(key, node.lineno)
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id_pattern.match(node.value)
            ):
                key = node.value
                required_keys.setdefault(key, node.lineno)

        for key, lineno in sorted(required_keys.items()):
            if key not in es_catalogue.MESSAGES or key not in en_catalogue.MESSAGES:
                failures.append(f"{path.name}:{lineno}: {key}")

    assert failures == []
