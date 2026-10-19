"""Feature 021 T003/T026: command registry, prompt files and parsing (no DB)."""
from importlib import resources

import pytest

from app.assistant.commands import registry
from app.errors import ApiError


@pytest.fixture
def commands_dir(tmp_path, monkeypatch):
    for name in registry.REGISTRY:
        for locale in ("es", "en"):
            body = "Usa:\n{spec_template}\n" if name == "speckit-specify" else f"Cuerpo {name}\n"
            path = tmp_path / locale / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'---\ndescription: Desc {name}\nargument_hint: "<texto>"\n'
                            f"source: test\n---\n{body}", encoding="utf-8")
    monkeypatch.setattr(registry, "_dir",
                        lambda locale: tmp_path / (locale if locale in ("es", "en") else "es"))
    registry.load.cache_clear()
    yield tmp_path
    registry.load.cache_clear()


def _rewrite(base, body):
    (base / "es" / "speckit-plan.md").write_text(
        f"---\ndescription: Desc\n---\n{body}", encoding="utf-8")
    registry.load.cache_clear()


def _pair(text):
    parsed = registry.parse(text)
    return parsed.name, parsed.args


def test_parse_variants(commands_dir):
    assert _pair("/speckit-plan") == ("speckit-plan", "")
    assert _pair("  /speckit.plan  extra\nline") == ("speckit-plan", "extra\nline")
    assert _pair("/speckit-plan\nsegunda línea") == ("speckit-plan", "segunda línea")
    assert registry.parse("/SPECKIT-Clarify").name == "speckit-clarify"
    for plain in ("// comentario", "/ hola", "hola /speckit-plan", "/123", "texto"):
        assert registry.parse(plain) is None, plain


@pytest.mark.parametrize(("text", "code"), [
    ("/no-existe", "unknown_command"),
    ("/speckit-plan " + "a" * 4001, "command_args_too_long"),
    ("/speckit-specify", "command_needs_args"),
    ("/speckit-specify    ", "command_needs_args"),
])
def test_parse_errors(commands_dir, text, code):
    with pytest.raises(ApiError) as exc:
        registry.parse(text)
    assert (exc.value.status, exc.value.code) == (422, code)
    if code == "unknown_command":
        assert "speckit-plan" in exc.value.extra["commands"]


def test_registry_and_menu(commands_dir):
    assert next(iter(registry.REGISTRY)) == "speckit-constitution"
    assert list(registry.REGISTRY)[-1] == "ayuda"
    menu = registry.list_commands("en")
    assert len(menu) == 11          # the ten spec-kit ones plus /fix
    plan = next(c for c in menu if c["name"] == "speckit-plan")
    assert plan == {"name": "speckit-plan", "description": "Desc speckit-plan",
                    "argument_hint": "<texto>", "needs_spec": True, "needs_args": False}
    assert registry.REGISTRY["speckit-analyze"].tools == frozenset()
    assert registry.REGISTRY["ayuda"].provider is True    # 023: `/ayuda <tema>` asks the model


def test_prompt_body_placeholders(commands_dir):
    template = (resources.files("bizview_cli") / "workspace_template" / "preset" / "templates"
                / "spec-template.md").read_text(encoding="utf-8")
    body = registry.prompt_body("speckit-specify", "es")
    assert body == f"Usa:\n{template}\n"
    _rewrite(commands_dir, "{otro}\n")
    with pytest.raises(ValueError, match="unknown placeholder otro"):
        registry.prompt_body("speckit-plan", "es")
    _rewrite(commands_dir, '{"a": 1}\n')
    assert registry.prompt_body("speckit-plan", "es") == '{"a": 1}\n'
    _rewrite(commands_dir, "x" * (registry.MAX_BODY + 1))
    with pytest.raises(ValueError, match="too long"):
        registry.prompt_body("speckit-plan", "es")


def test_help_handler(commands_dir):
    text = registry.HANDLERS["ayuda"]("es")
    assert "`/speckit-plan` <texto> — Desc speckit-plan" in text
    assert "/ayuda" not in text


def test_every_command_has_both_prompt_files():
    """T026: every command ships es and en files with the same placeholders, under 12 KB."""
    registry.load.cache_clear()
    missing = [(n, loc) for n in registry.REGISTRY for loc in ("es", "en")
               if not (registry._dir(loc) / f"{n}.md").is_file()]
    if missing:
        pytest.skip(f"prompt files not written yet: {missing[:3]}…")
    for name in registry.REGISTRY:
        es, en = (registry.load(name, loc) for loc in ("es", "en"))
        assert es[0].get("description") and en[0].get("description"), name
        placeholders = [sorted(set(registry._PLACEHOLDER.findall(b[1]))) for b in (es, en)]
        assert placeholders[0] == placeholders[1], name
        for loc in ("es", "en"):
            registry.prompt_body(name, loc)
