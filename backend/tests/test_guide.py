"""Feature 023 T041 (and T010): the app guide is complete, consistent and safe (no DB).

Each failure names the file or the item and how to fix it."""
import re

import pytest

from app import guide
from app.assistant import service
from app.assistant.commands import scope
from app.assistant.commands.registry import REGISTRY

HEADINGS = {
    "es": ["Para qué sirve", "Quién puede usarlo", "Cómo se hace", "Opciones",
           "Problemas frecuentes"],
    "en": ["What it is for", "Who can use it", "How to", "Options", "Common problems"],
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
    # 045 removed the nine topics of the in-app assistant (2026-10-31).
    assert len(ids) == len(set(ids)) == 47
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


def test_registry_commands_and_topic_commands_match(loaded):
    documented = {c.lstrip("/") for topic in loaded.topics for c in topic.commands}
    assert set(REGISTRY) <= documented, (
        f"comandos sin tema: {sorted(set(REGISTRY) - documented)}; agrégalos a `commands` de un "
        "tema en index.yaml")
    extra = sorted(documented - set(REGISTRY))
    assert not extra, f"comandos inexistentes en index.yaml: {extra}"


def test_index_is_deterministic_bounded_and_in_the_system_prefix():
    for lang in guide.LANGS:
        text = guide.index_text(lang)
        assert text == guide.index_text(lang)
        assert len(text) <= guide.INDEX_MAX, f"índice {lang}: {len(text)} > {guide.INDEX_MAX}"
        assert guide.prompt_block(lang) in service.system_prefix(lang)
    assert service.system_prefix("es") == service.system_prefix("es")


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
    assert guide.get("seguridad", "es", None) is not None      # the agent (superuser chat)


HELP_QUESTIONS = [
    "¿cómo activo el tema oscuro?", "¿cómo cambio mi contraseña?",
    "¿cómo comparto un tablero por correo cada lunes?", "¿qué es un reporte directo?",
    "¿cómo restablezco la contraseña de un usuario?", "¿dónde veo la auditoría?",
    "¿cómo activo la verificación en dos pasos?", "¿cómo vinculo telegram?",
    "¿cómo exporto a csv?", "¿qué hace /speckit-plan?",
    "how do I turn on the dark theme?", "how do I reset a user's password?",
    "how do I share a dashboard with a link?", "what is a direct report?",
    "how do I change the language?", "where is the audit log?",
    "how do I set up two-step verification?", "how do I link telegram?",
    "how do I export to pdf?", "what does /speckit-implement do?",
]


@pytest.mark.parametrize("question", HELP_QUESTIONS)
def test_help_questions_are_never_refused(question):
    assert scope.precheck(question).out is False, question
