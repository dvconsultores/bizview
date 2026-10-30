"""Scope gate and untrusted-data delimiting of the chat (feature 021, plan §7 and §8).

The pre-check is deliberately conservative: a message is answered with the fixed refusal only
when an off-topic phrasing matches, no BI term (or source / artifact name of the installation)
occurs and the text is short. Everything else goes to the model, whose prompt carries the
scope rule.
"""
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ScopeDecision:
    out: bool
    rule: str | None
    lang: str | None


def _rule(rule_id: str, lang: str, pattern: str) -> tuple[str, str, re.Pattern]:
    return rule_id, lang, re.compile(pattern, re.IGNORECASE)


# Phrasings, not single business words: "hotel", "demanda", "clima laboral" or "historia de
# usuario" are normal in BI requests.
OUT_RULES: tuple[tuple[str, str, re.Pattern], ...] = (
    _rule("creative_es", "es", r"\b(escr[ií]b\w*|hazme|haz|comp[oó]n\w*|inventa\w*|cu[eé]nt\w*)"
                               r"\s+(me\s+)?(un|una|otro|otra)\s+(poema|poes[ií]a|canci[oó]n|"
                               r"cuento|chiste|verso|rima)s?\b"),
    _rule("creative_en", "en", r"\b(write|compose|tell|make up)\s+(me\s+)?(a|an|another)\s+"
                               r"(poem|song|story|joke|limerick|haiku)\b"),
    _rule("jokes_es", "es", r"\bch[ií]stes?\s+(de|sobre)\b"),
    _rule("cooking_es", "es", r"\b(receta|recetas)\s+(de|para)\b|\bc[oó]mo\s+(se\s+)?cocin\w+"),
    _rule("cooking_en", "en", r"\brecipes?\s+(for|of)\b|\bhow (do i|to) cook\b"),
    _rule("sports_es", "es", r"\bqui[eé]n gan[oó]\b|\bresultado del partido\b|"
                             r"\b(f[uú]tbol|b[eé]isbol|baloncesto|mundial|champions)\b.*\b"
                             r"(ganó|partido|goles|jugador)\b"),
    _rule("sports_en", "en", r"\bwho won\b|\b(match|game) score\b|\b(football|soccer|baseball|"
                             r"basketball|nba|nfl) (match|game|player|scores?)\b"),
    _rule("weather_es", "es", r"\b(qu[eé]|c[oó]mo)\s+(tiempo|clima)\s+(hace|har[aá]|va a hacer)|"
                              r"\bpron[oó]stico del (tiempo|clima)\b|\bva a llover\b"),
    _rule("weather_en", "en", r"\bweather (in|for|today|tomorrow|forecast)\b|\bwill it rain\b"),
    _rule("health_es", "es", r"\b(me duele|dolor de (cabeza|est[oó]mago|muela)|tengo fiebre|"
                             r"s[ií]ntomas de|remedio para)\b"),
    _rule("health_en", "en", r"\b(my (head|stomach|tooth) hurts|i have a (fever|headache)|"
                             r"symptoms of|remedy for|headache)\b"),
    _rule("legal_es", "es", r"\b(consejo|asesor[ií]a) (legal|jur[ií]dic[ao])\b|"
                            r"\bnecesito un abogado\b"),
    _rule("legal_en", "en", r"\blegal advice\b|\bi need a lawyer\b|\bshould i sue\b"),
    _rule("politics_es", "es", r"\b(elecciones|campa[nñ]a pol[ií]tica|partido pol[ií]tico|"
                               r"por qui[eé]n votar)\b"),
    _rule("politics_en", "en", r"\b(the election|political campaign|political party|"
                               r"who (should i|to) vote)\b"),
    _rule("religion_es", "es", r"\b(existe dios|h[aá]blame de dios|la biblia dice|religi[oó]n)\b"),
    _rule("religion_en", "en", r"\b(does god exist|tell me about god|the bible says|religion)\b"),
    _rule("celebrities_es", "es", r"\b(chisme|far[aá]ndula|qu[eé] hace ahora el famoso)\b"),
    _rule("celebrities_en", "en", r"\b(celebrity gossip|what is the celebrity)\b"),
    _rule("news_es", "es", r"\b([uú]ltimas noticias|noticias de hoy)\b"),
    _rule("news_en", "en", r"\b(latest news|news today|news headlines)\b"),
    _rule("travel_es", "es", r"\b(planif[ií]ca\w*|organ[ií]za\w*)\s+(me\s+)?un viaje\b|"
                             r"\bqu[eé] visitar en\b|\bitinerario de viaje\b"),
    _rule("travel_en", "en", r"\bplan (a|my) trip\b|\btravel itinerary\b|\bthings to do in\b"),
    _rule("homework_es", "es", r"\bresuelve la ecuaci[oó]n\b|\b(calcula|halla) la derivada\b|"
                               r"\bayuda con mi tarea\b"),
    _rule("homework_en", "en", r"\bsolve the equation\b|\b(calculate|find) the derivative\b|"
                               r"\bhomework help\b|\bhelp with my homework\b"),
    _rule("programming_es", "es", r"\b(script|programa) (de|en) python\b|"
                                  r"\bcomponente (de )?react\b"),
    _rule("programming_en", "en", r"\b(write|create) a (python|bash|node) script\b|"
                                  r"\breact component\b"),
    _rule("translation_es", "es", r"\btraduce\w*\s+(al|a|esto|este|la|el)\b"),
    _rule("translation_en", "en", r"\btranslate (this|to|into)\b"),
    _rule("personal_es", "es", r"\bmi (novio|novia|pareja|esposo|esposa) (no|me)\b|"
                               r"\bconsejos? de (pareja|amor)\b"),
    _rule("personal_en", "en", r"\bmy (boyfriend|girlfriend|wife|husband) (is|doesn|won|keeps)\b|"
                               r"\brelationship advice\b"),
    _rule("games_es", "es", r"\b(recomi[eé]nda\w* un|qu[eé]) (video)?juego\b|"
                            r"\b(playstation|xbox|nintendo)\b"),
    _rule("games_en", "en", r"\brecommend (me )?a (video ?game|game)\b|"
                            r"\b(playstation|xbox|nintendo)\b"),
    _rule("crypto_es", "es", r"\b(invierto|invertir|comprar?) (en )?(bitcoin|ethereum|cripto\w*|"
                             r"acciones)\b"),
    _rule("crypto_en", "en", r"\b(invest|buy) (in )?(bitcoin|ethereum|crypto\w*|stocks)\b"),
)

IN_TERMS = re.compile(
    r"\b(reportes?|reports?|tableros?|dashboards?|m[eé]tricas?|metrics?|kpis?|indicador\w*|"
    r"integraci[oó]n\w*|integrations?|etl|fuentes?|sources?|tablas?|tables?|consultas?|"
    r"quer(y|ies)|sql|columnas?|columns?|datasets?|specs?|plan|tareas|tasks|proyectos?|"
    r"projects?|bizview|ventas|sales|facturas?|invoices?|programaci[oó]n|schedule\w*|"
    r"compart\w+|share\w*|correos?|e-?mails?|pdf|filtros?|filters?|periodos?|periods?|"
    r"gr[aá]ficos?|charts?|base de datos|databases?|supabase|postgres\w*|inventario|inventory|"
    r"clientes|customers|distribuci[oó]n\w*|distributions?|specify|clarify|analyze|implement|"
    r"converge|checklists?|constituci[oó]n|constitution)\b",
    re.IGNORECASE)

MAX_LEN = 600


def _fold(text: str) -> str:
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", text)
                    if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", plain).strip().casefold()


@lru_cache(maxsize=1)
def guide_terms() -> re.Pattern | None:
    """Titles and aliases of the app guide (023) as whole words: help questions are in scope."""
    try:
        from app import guide

        terms = {_fold(term) for term in guide.all_terms()}
    except Exception:          # the guide has its own validation tests
        return None
    words = sorted((term for term in terms if len(term) >= 3), key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(w) for w in words) + r")(?!\w)")


def precheck(text: str, extra_terms: Iterable[str] = ()) -> ScopeDecision:
    """Fixed refusal only for short, clearly off-topic messages with no BI or app term."""
    t = text.strip()
    if len(t) > MAX_LEN or IN_TERMS.search(t):
        return ScopeDecision(False, None, None)
    terms = guide_terms()
    if terms is not None and terms.search(_fold(t)):
        return ScopeDecision(False, None, None)
    lowered = t.lower()
    if any(term and term.lower() in lowered for term in extra_terms):
        return ScopeDecision(False, None, None)
    for rule_id, lang, pattern in OUT_RULES:
        if pattern.search(t):
            return ScopeDecision(True, rule_id, lang)
    return ScopeDecision(False, None, None)


_NESTED = re.compile(r"<(/?)datos", re.IGNORECASE)


def wrap_data(label: str, text: str) -> str:
    """Untrusted content (tool results, project documents) inside a `<datos>` block the
    prompt says never to obey; nested tags are neutralised so the block cannot be closed."""
    safe_label = re.sub(r"[^A-Za-z0-9_./:-]", "", label)
    safe_text = _NESTED.sub(lambda m: "\u2039" + m.group(0)[1:], text)
    return f'<datos origen="{safe_label}" confianza="no">\n{safe_text}\n</datos>'
