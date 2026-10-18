"""BizView's bilingual in-app guide (feature 023): one Markdown body per topic and language,
`index.yaml` with the metadata. Loaded once per process; topics are filtered by role."""

import difflib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings
from app.i18n import t, use_locale

GUIDE_DIR = Path(__file__).parent
LANGS = ("es", "en")
ROLES = ("public", "user", "admin", "superuser")
TOPIC_ID = re.compile(r"^[a-z][a-z0-9-]{1,48}$")
MAX_BODY = 6000
MAX_SUMMARY = 140
# The system-prompt index grows with the guide (one short line per topic; the Spanish summaries
# are the longest). It was 8000 with 52 topics; feature 024 added the 53rd.
INDEX_MAX = 8400


class GuideError(Exception):
    """The guide content is invalid: the file and the reason."""

    def __init__(self, file: str, reason: str) -> None:
        self.file = file
        self.reason = reason
        super().__init__(f"{file}: {reason}")


@dataclass(frozen=True)
class Section:
    id: str
    title: dict[str, str]


@dataclass(frozen=True)
class TopicMeta:
    id: str
    section: str
    title: dict[str, str]
    summary: dict[str, str]
    roles: tuple[str, ...]
    routes: tuple[str, ...]
    tiles: tuple[str, ...]
    commands: tuple[str, ...]
    aliases: dict[str, tuple[str, ...]]
    related: tuple[str, ...]


@dataclass(frozen=True)
class Topic:
    meta: TopicMeta
    lang: str
    body: str


@dataclass(frozen=True)
class Guide:
    version: int
    sections: tuple[Section, ...]
    topics: tuple[TopicMeta, ...]
    bodies: dict[tuple[str, str], str]
    ayuda: dict[str, str]

    def meta(self, topic_id: str) -> TopicMeta | None:
        return next((topic for topic in self.topics if topic.id == topic_id), None)


def _texts(value: Any, file: str, what: str, limit: int | None = None) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
            isinstance(value.get(lang), str) and value[lang].strip() for lang in LANGS):
        raise GuideError(file, f"{what}: falta es o en")
    if limit is not None and any(len(value[lang]) > limit for lang in LANGS):
        raise GuideError(file, f"{what}: más de {limit} caracteres")
    return {lang: value[lang] for lang in LANGS}


def _strings(value: Any, file: str, what: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise GuideError(file, f"{what}: debe ser una lista de textos")
    return tuple(value)


def _topic(item: dict, file: str, sections: set[str]) -> TopicMeta:
    topic_id = item.get("id")
    if not isinstance(topic_id, str) or not TOPIC_ID.match(topic_id):
        raise GuideError(file, f"id de tema no válido: {topic_id!r}")
    where = f"tema {topic_id}"
    if item.get("section") not in sections:
        raise GuideError(file, f"{where}: sección desconocida {item.get('section')!r}")
    roles = _strings(item.get("roles"), file, f"{where} roles")
    if not roles or not set(roles) <= set(ROLES):
        raise GuideError(file, f"{where}: roles deben ser de {', '.join(ROLES)}")
    aliases = item.get("aliases")
    if not isinstance(aliases, dict):
        raise GuideError(file, f"{where}: faltan aliases")
    alias_map = {lang: _strings(aliases.get(lang), file, f"{where} aliases {lang}")
                 for lang in LANGS}
    if not all(alias_map.values()):
        raise GuideError(file, f"{where}: aliases vacíos")
    related = _strings(item.get("related"), file, f"{where} related")
    if topic_id in related or len(related) > 5:
        raise GuideError(file, f"{where}: related no puede incluirse a sí mismo ni pasar de 5")
    return TopicMeta(
        id=topic_id, section=item["section"],
        title=_texts(item.get("title"), file, f"{where} title"),
        summary=_texts(item.get("summary"), file, f"{where} summary", MAX_SUMMARY),
        roles=roles,
        routes=_strings(item.get("routes"), file, f"{where} routes"),
        tiles=_strings(item.get("tiles"), file, f"{where} tiles"),
        commands=_strings(item.get("commands"), file, f"{where} commands"),
        aliases=alias_map, related=related)


@lru_cache(maxsize=1)
def load() -> Guide:
    """Parse and validate the guide (GuideError names the file and the reason)."""
    index = GUIDE_DIR / "index.yaml"
    file = str(index)
    raw = yaml.safe_load(index.read_text(encoding="utf-8")) or {}
    if raw.get("version") != 1:
        raise GuideError(file, "version debe ser 1")
    sections: list[Section] = []
    for item in raw.get("sections") or []:
        section_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(section_id, str) or not section_id:
            raise GuideError(file, "sección sin id")
        if any(s.id == section_id for s in sections):
            raise GuideError(file, f"sección repetida {section_id}")
        sections.append(Section(section_id, _texts(item.get("title"), file,
                                                   f"sección {section_id} title")))
    section_ids = [s.id for s in sections]
    topics: list[TopicMeta] = []
    for item in raw.get("topics") or []:
        meta = _topic(item if isinstance(item, dict) else {}, file, set(section_ids))
        if any(other.id == meta.id for other in topics):
            raise GuideError(file, f"tema repetido {meta.id}")
        topics.append(meta)
    ids = {topic.id for topic in topics}
    for topic in topics:
        unknown = [r for r in topic.related if r not in ids]
        if unknown:
            raise GuideError(file, f"tema {topic.id}: related desconocidos {unknown}")
    order = {topic.id: i for i, topic in enumerate(topics)}
    topics.sort(key=lambda topic: (section_ids.index(topic.section), order[topic.id]))

    bodies: dict[tuple[str, str], str] = {}
    for topic in topics:
        for lang in LANGS:
            path = GUIDE_DIR / lang / f"{topic.id}.md"
            if not path.is_file():
                raise GuideError(str(path), "falta el archivo del tema")
            body = path.read_text(encoding="utf-8")
            if len(body) > MAX_BODY:
                raise GuideError(str(path), f"más de {MAX_BODY} caracteres")
            if body.split("\n", 1)[0] != f"# {topic.title[lang]}":
                raise GuideError(str(path), f"la primera línea debe ser «# {topic.title[lang]}»")
            bodies[(lang, topic.id)] = body
    ayuda: dict[str, str] = {}
    for lang in LANGS:
        path = GUIDE_DIR / lang / "_ayuda.md"
        if not path.is_file():
            raise GuideError(str(path), "falta la plantilla de /ayuda")
        ayuda[lang] = path.read_text(encoding="utf-8")
    return Guide(1, tuple(sections), tuple(topics), bodies, ayuda)


def lang_of(lang: str | None) -> str:
    """`lang` when supported, else DEFAULT_LOCALE (022), else Spanish."""
    if lang in LANGS:
        return lang
    default = get_settings().default_locale
    return default if default in LANGS else "es"


def visible_roles(user: Any) -> set[str]:
    """Roles whose topics a viewer may read; None is the agent (superuser chat)."""
    if user is None or getattr(user, "is_superuser", False):
        return set(ROLES)
    if getattr(user, "role", None) == "admin":
        return {"public", "user", "admin"}
    return {"public", "user"}


def visible(meta: TopicMeta, user: Any) -> bool:
    return bool(set(meta.roles) & visible_roles(user))


def topics_for(user: Any, lang: str | None = None) -> list[TopicMeta]:
    """Topics the viewer may read, by section then topic order."""
    return [topic for topic in load().topics if visible(topic, user)]


def get(topic_id: str, lang: str | None, user: Any = None) -> Topic | None:
    """A topic in `lang`; None when unknown or not visible (the same answer either way)."""
    guide = load()
    meta = guide.meta(topic_id)
    if meta is None or not visible(meta, user):
        return None
    language = lang_of(lang)
    return Topic(meta, language, guide.bodies[(language, meta.id)])


def _fold(text: str) -> str:
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", text)
                    if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", plain).strip().casefold()


def resolve(text: str, lang: str | None = None) -> tuple[str | None, list[str]]:
    """Topic id for a user's words: exact id, id with hyphens, title, then alias (accent and
    case insensitive); else (None, up to 3 closest ids)."""
    topics = load().topics
    language = lang_of(lang)
    langs = (language, "en" if language == "es" else "es")
    folded = _fold(text)
    hyphened = folded.replace(" ", "-")
    passes = (
        lambda topic: topic.id == text.strip(),
        lambda topic: topic.id == hyphened,
        lambda topic: any(_fold(topic.title[lg]) == folded for lg in langs),
        lambda topic: any(_fold(a) == folded for lg in langs for a in topic.aliases[lg]),
    )
    for matches in passes:
        found = next((topic.id for topic in topics if matches(topic)), None)
        if found:
            return found, []
    candidates: dict[str, str] = {}
    for topic in topics:
        for lg in langs:
            candidates.setdefault(_fold(topic.title[lg]), topic.id)
            for alias in topic.aliases[lg]:
                candidates.setdefault(_fold(alias), topic.id)
    closest: list[str] = []
    for match in difflib.get_close_matches(folded, list(candidates), n=10, cutoff=0.5):
        if candidates[match] not in closest:
            closest.append(candidates[match])
    return None, closest[:3]


def index_text(lang: str | None = None) -> str:
    """Deterministic index for the system prompt: sections, then `- id — title: summary
    [roles]`."""
    language = lang_of(lang)
    guide = load()
    blocks: list[str] = []
    with use_locale(language):
        for section in guide.sections:
            topics = [topic for topic in guide.topics if topic.section == section.id]
            if not topics:
                continue
            lines = [f"### {section.title[language]}"]
            for topic in topics:
                roles = ", ".join(t(f"guide.role.{role}") for role in topic.roles)
                lines.append(f"- {topic.id} — {topic.title[language]}: "
                             f"{topic.summary[language]} [{roles}]")
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def prompt_block(lang: str | None = None) -> str:
    """The guide rules and the index, for the stable system prefix (plan §5)."""
    language = lang_of(lang)
    with use_locale(language):
        rules = t("guide.prompt_rules")
    return f"{rules}\n\n{index_text(language)}"


def all_terms() -> list[str]:
    """Titles and aliases of every topic in both languages (in-scope terms of 021)."""
    terms: list[str] = []
    for topic in load().topics:
        for lang in LANGS:
            for term in (topic.title[lang], *topic.aliases[lang]):
                if term not in terms:
                    terms.append(term)
    return terms


def ayuda_template(lang: str | None = None) -> str:
    """The fixed `/ayuda` template of that language."""
    return load().ayuda[lang_of(lang)]
