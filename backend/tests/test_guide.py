"""Feature 023 T041 (and T010): the app guide is complete, consistent and safe (no DB).

Each failure names the file or the item and how to fix it."""
import re

import pytest

from app import guide

HEADINGS = {
    "es": ["Para qué sirve", "Quién puede usarlo", "Cómo se hace", "Opciones",
           "Problemas frecuentes", "Relacionados"],
    "en": ["What it is for", "Who can use it", "How to", "Options", "Common problems",
           "Related"],
}
ENV_ASSIGNMENT = re.compile(r"\b[A-Z][A-Z_]{3,}=")
SECRET_LITERAL = re.compile(r"(password|token|api_key|secret)\s*=\s*\S", re.I)
PLACEHOLDERS = ("{commands}", "{examples}", "{next_steps}", "{help_link}")


@pytest.fixture(scope="module")
def loaded():
    guide.load.cache_clear()
    return guide.load()


def _sections(body: str) -> list[str]:
    return [line[3:].strip() for line in body.splitlines() if line.startswith("## ")]


def test_index_loads_with_valid_ids_sections_and_related(loaded):
    ids = [topic.id for topic in loaded.topics]
    # 045 removed the nine topics of the in-app assistant (2026-10-31); 047 added `temas`;
    # 049 added `importar-un-proyecto`; 052 added the three structure topics; 053 added
    # `parametros-y-filtros-del-reporte`; 054 added `ingreso-con-google`.
    assert len(ids) == len(set(ids)) == 64
    sections = {section.id for section in loaded.sections}
    for topic in loaded.topics:
        assert guide.TOPIC_ID.match(topic.id), topic.id
        assert topic.section in sections, f"{topic.id}: sección desconocida"
        assert set(topic.related) <= set(ids), f"{topic.id}: related desconocidos"
        assert set(topic.roles) <= set(guide.ROLES), f"{topic.id}: roles fuera del vocabulario"


def test_every_topic_has_both_files_and_no_orphans(loaded):
    ids = {topic.id for topic in loaded.topics}
    for lang in guide.LANGS:
        names = {p.stem for p in (guide.GUIDE_DIR / lang).glob("*.md")}
        assert names - ids == {"_ayuda"}, (
            f"{lang}/: archivos sin tema en index.yaml {sorted(names - ids - {'_ayuda'})}; "
            "bórralos o agrégalos al índice")
        assert ids <= names, f"{lang}/: faltan {sorted(ids - names)}"
        template = loaded.ayuda[lang]
        for placeholder in PLACEHOLDERS:
            assert placeholder in template, f"{lang}/_ayuda.md: falta {placeholder}"


def test_headings_match_the_titles_and_mirror_between_languages(loaded):
    for topic in loaded.topics:
        found = {}
        for lang in guide.LANGS:
            body = loaded.bodies[(lang, topic.id)]
            assert body.startswith(f"# {topic.title[lang]}\n"), f"{lang}/{topic.id}.md: título"
            assert len(body) <= guide.MAX_BODY, f"{lang}/{topic.id}.md: más de {guide.MAX_BODY}"
            sections = _sections(body)
            unknown = [s for s in sections if s not in HEADINGS[lang]]
            assert not unknown, f"{lang}/{topic.id}.md: secciones no permitidas {unknown}"
            order = [HEADINGS[lang].index(s) for s in sections]
            assert order == sorted(order) and order[:3] == [0, 1, 2], (
                f"{lang}/{topic.id}.md: el orden debe ser {HEADINGS[lang]}")
            found[lang] = order
        assert found["es"] == found["en"], f"{topic.id}: es y en deben tener las mismas secciones"


def test_environment_names_only_in_superuser_topics_and_no_secrets(loaded):
    for topic in loaded.topics:
        for lang in guide.LANGS:
            body = loaded.bodies[(lang, topic.id)]
            if topic.roles != ("superuser",):
                assert not ENV_ASSIGNMENT.search(body), (
                    f"{lang}/{topic.id}.md: variables de entorno solo en temas de superusuario")
            assert not SECRET_LITERAL.search(body), f"{lang}/{topic.id}.md: parece un secreto"


def test_topic_commands_are_the_ones_the_app_still_has(loaded):
    """Feature 045 removed the in-app authoring agent and its `/speckit-…` commands: a topic that
    still advertises one would send a reader looking for a screen that no longer exists."""
    documented = {c.lstrip("/") for topic in loaded.topics for c in topic.commands}
    assert documented <= {"ayuda"}, f"comandos inexistentes en index.yaml: {sorted(documented)}"


def test_index_is_deterministic_and_bounded():
    for lang in guide.LANGS:
        text = guide.index_text(lang)
        assert text == guide.index_text(lang)
        assert len(text) <= guide.INDEX_MAX, f"índice {lang}: {len(text)} > {guide.INDEX_MAX}"


def test_resolve_ids_titles_aliases_and_closest():
    assert guide.resolve("reportes-directos", "es") == ("reportes-directos", [])
    assert guide.resolve("reportes directos", "es") == ("reportes-directos", [])
    assert guide.resolve("Tema Oscuro", "es") == ("apariencia-e-idioma", [])
    assert guide.resolve("direct report", "en") == ("reportes-directos", [])
    topic_id, closest = guide.resolve("reportes diretos", "es")
    assert topic_id is None and closest and closest[0] == "reportes-directos"


def test_role_filter():
    user = type("U", (), {"is_superuser": False, "role": "user"})()
    admin = type("U", (), {"is_superuser": False, "role": "admin"})()
    user_ids = {t.id for t in guide.topics_for(user)}
    admin_ids = {t.id for t in guide.topics_for(admin)}
    assert "seguridad" not in user_ids and "seguridad" not in admin_ids
    assert "usuarios" in admin_ids and "usuarios" not in user_ids
    assert {"ingreso", "tableros", "ayuda"} <= user_ids
    assert guide.get("seguridad", "es", user) is None
    assert guide.get("seguridad", "es", None) is not None      # no viewer: everything is readable


def test_every_title_and_alias_opens_a_topic(loaded):
    """The help search is the surviving reader-facing surface (feature 023, kept by 045): whatever a
    reader types — the title or any alias, in either language — opens a topic, never nothing. An
    alias two topics share («ia») may open either; the index is the one that owns it."""
    for topic in loaded.topics:
        for lang in guide.LANGS:
            for words in (topic.title[lang], *topic.aliases[lang]):
                assert guide.resolve(words, lang)[0] is not None, (lang, words)
