"""SC-002 live eval for feature 023: the chat answers questions about the app from the guide.

Run with:

    AI_LIVE_TESTS=1 AI_LIVE_API_KEY=... [AI_LIVE_BASE_URL=https://api.deepseek.com] \
    [AI_LIVE_MODEL=deepseek-chat] uv run pytest tests/live/test_guide_eval.py -s

WARNING: this contacts the live provider and costs tokens. Questions are synthetic
(tests/live/guide_eval.yaml); the overview questions use the synthetic project `facturas-demo`.
Scoring is deterministic (plan §12): topic fetched, must_include / must_not_include, valid and
required `app:` links. Pass: ≥ 45/50.
"""
import os
import re
import unicodedata
from pathlib import Path

import pytest
import yaml

from app import guide
from app.config import get_settings
from app.i18n import t, use_locale
from tests.conftest import signed_in, write_project
from tests.live.test_agent_eval import live_provider as live_provider  # fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("AI_LIVE_TESTS") != "1",
    reason="contacts the live AI provider; set AI_LIVE_TESTS=1",
)

QUESTIONS = yaml.safe_load((Path(__file__).parent / "guide_eval.yaml").read_text())
REQUIRED = 45
LINK = re.compile(r"\]\(app:([^)\s]+)\)")
STEP = re.compile(r"^\s*1[.)]\s", re.M)
UNKNOWN = {"es": ("no lo se", "no se ", "no lo encuentro", "no esta en la guia"),
           "en": ("don't know", "do not know", "not in the guide", "couldn't find")}

FACTURAS_DEMO = {
    "specs/001-fuente-origen-facturas/spec.md":
        "# Origen facturas\n\n**Tipo**: fuente\n**Status**: Implemented\n\n"
        "**Fuente**: Origen facturas\n",
    "specs/001-fuente-origen-facturas/plan.md": "# Plan\n",
    "specs/001-fuente-origen-facturas/tasks.md": "- [X] T001 Probar la conexión\n",
    "specs/002-reporte-facturas-directo/spec.md":
        "# Facturas directo\n\n**Tipo**: reporte\n**Status**: Draft\n\n**Modo**: directo\n\n"
        "**Fuente**: bi\n\nSe lee la tabla facturas en vivo; el volumen es pequeño.\n",
    "specs/002-reporte-facturas-directo/plan.md": "# Plan\n\nTarjetas por día y estado.\n",
    "specs/003-envio-semanal/spec.md": "# Envío semanal\n\n**Tipo**: distribucion\n",
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("\u2019", "'"))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _patterns() -> list[re.Pattern]:
    routes = {r for topic in guide.load().topics for r in topic.routes if r != "*"}
    return [re.compile("^" + re.sub(r":[a-z_]+", "[^/]+", route) + "$") for route in routes]


def _refusals() -> tuple[str, ...]:
    out = []
    for locale in ("es", "en"):
        with use_locale(locale):
            out.append(_fold(t("scope.refusal")).strip())
    return tuple(out)


def _ask(c, slug: str, text: str) -> dict:
    sid = c.post("/api/assistant/sessions", json={"project": slug}).json()["id"]
    r = c.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})
    assert r.status_code == 202, r.text
    data = c.get(f"/api/assistant/sessions/{sid}").json()
    tools = [m for m in data["messages"] if m["role"] == "tool"]
    reply = next((m["content"] for m in reversed(data["messages"])
                  if m["role"] == "assistant" and m["content"].strip()), "")
    return {"reply": reply, "tools": tools, "tokens": data["tokens_used"]}


def _score(q: dict, result: dict, patterns, refusals) -> list[str]:
    """The failed checks of one question (empty = correct)."""
    problems = []
    reply = _fold(result["reply"])
    tools = result["tools"]
    if q["kind"] == "overview":
        if not any(m.get("tool_name") == "get_project_overview" for m in tools):
            problems.append("get_project_overview not called")
    elif q["topics"]:
        fetched = " ".join(m["content"] for m in tools if m.get("tool_name") == "get_app_guide")
        if not any(f"({topic})" in fetched for topic in q["topics"]):
            problems.append(f"topic not fetched ({fetched or 'no get_app_guide'})")
    if q["kind"] == "unknown" and not (reply.strip().startswith(refusals)
                                       or any(p in reply for p in UNKNOWN[q["lang"]])):
        problems.append("does not say it does not know")
    if q["kind"] == "restricted" and STEP.search(result["reply"]):
        problems.append("gives steps")
    problems += [f"missing {x!r}" for x in q["must_include"] if _fold(x) not in reply]
    problems += [f"contains {x!r}" for x in q["must_not_include"] if _fold(x) in reply]
    links = [link.split("?")[0].split("#")[0] for link in LINK.findall(result["reply"])]
    problems += [f"invalid link {link}" for link in links
                 if not any(p.match(link) for p in patterns)]
    if q["link"] and not any(link.startswith(q["link"]) for link in links):
        problems.append(f"no link to {q['link']}")
    return problems


def test_guide_eval(live_provider, superuser, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    c = signed_in("root@example.com")
    general = c.post("/api/projects", json={"name": "Evaluación guía"}).json()
    demo = c.post("/api/projects", json={"name": "Facturas demo"}).json()
    assert demo["slug"] == "facturas-demo", demo
    write_project(demo["id"], FACTURAS_DEMO, superuser.id)
    patterns, refusals = _patterns(), _refusals()
    correct, tokens, rows = 0, 0, []
    for q in QUESTIONS:
        assert c.patch("/api/me/preferences", json={"locale": q["lang"]}).status_code == 200
        slug = demo["slug"] if q.get("project") else general["slug"]
        result = _ask(c, slug, q["question"])
        problems = _score(q, result, patterns, refusals)
        correct += not problems
        tokens += result["tokens"]
        rows.append(f"{q['id']:6} {q['kind']:10} {'OK  ' if not problems else 'FAIL'} "
                    f"{result['tokens']:6} {'; '.join(problems)}")
    print("\n".join(rows))
    print(f"correct {correct}/{len(QUESTIONS)}, tokens {tokens}")
    assert correct >= REQUIRED, "\n".join(r for r in rows if "FAIL" in r)
