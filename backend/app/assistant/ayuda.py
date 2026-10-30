"""`/ayuda` (feature 023, plan §6): the fixed reply without arguments (no provider call) and the
resolved-topic block of `/ayuda <tema>`."""
from app import guide
from app.assistant.commands import registry
from app.assistant.commands.scope import wrap_data
from app.i18n import t, use_locale


def _commands(lang: str) -> str:
    lines = []
    for cmd in registry.list_commands(lang):
        hint = f" {cmd['argument_hint']}" if cmd["argument_hint"] else ""
        lines.append(f"- `/{cmd['name']}{hint}` — {cmd['description']}")
    return "\n".join(lines)


def fixed_reply(db, project, lang: str) -> str:
    """The `_ayuda.md` template with the commands, examples, next steps and the help link."""
    from app.assistant import overview

    language = guide.lang_of(lang)
    with use_locale(language):
        examples = t("guide.ayuda_examples")
        help_link = t("guide.help_link")
    next_steps = overview.next_steps(db, project, language) if project is not None else ""
    return guide.ayuda_template(language).format(
        commands=_commands(language), examples=examples, next_steps=next_steps,
        help_link=help_link)


def topic_block(args: str, lang: str) -> str:
    """`Tema resuelto: <id>` and the topic as data, or the closest topics."""
    language = guide.lang_of(lang)
    topic_id, closest = guide.resolve(args, language)
    topic = guide.get(topic_id, language) if topic_id else None
    if topic is not None:
        return f"Tema resuelto: {topic_id}\n" + wrap_data(f"guia:{topic_id}", topic.body)
    loaded = guide.load()
    names = ", ".join(f"{c} ({loaded.meta(c).title[language]})" for c in closest) or "-"
    return f"Tema resuelto: ninguno. Temas cercanos: {names}"
