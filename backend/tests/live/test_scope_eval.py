"""SC-003 live eval for feature 021: the chat declines off-topic requests and answers BI ones.

Run with:

    AI_LIVE_TESTS=1 AI_LIVE_API_KEY=... [AI_LIVE_BASE_URL=https://api.deepseek.com] \
    [AI_LIVE_MODEL=deepseek-chat] uv run pytest tests/live/test_scope_eval.py -s

WARNING: this contacts the live provider and costs tokens. Prompts are synthetic
(tests/fixtures/scope_prompts.yaml): the first 20 of each list are Spanish, the last 20 English.
"""
import os
import re
from pathlib import Path

import pytest
import yaml

from app.config import get_settings
from app.i18n import t, use_locale
from tests.conftest import signed_in
from tests.live.test_agent_eval import live_provider as live_provider  # fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("AI_LIVE_TESTS") != "1",
    reason="contacts the live AI provider; set AI_LIVE_TESTS=1",
)

PROMPTS = yaml.safe_load(
    (Path(__file__).parent.parent / "fixtures" / "scope_prompts.yaml").read_text())
REQUIRED = 38


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _refusals() -> tuple[str, ...]:
    out = []
    for locale in ("es", "en"):
        with use_locale(locale):
            out.append(_norm(t("scope.refusal")))
    return tuple(out)


def _ask(c, slug: str, text: str) -> dict:
    sid = c.post("/api/assistant/sessions", json={"project": slug}).json()["id"]
    r = c.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})
    assert r.status_code == 202, r.text
    data = c.get(f"/api/assistant/sessions/{sid}").json()
    reply = next((m for m in reversed(data["messages"])
                  if m["role"] == "assistant" and m["content"].strip()), None)
    return {"reply": reply, "tokens": data["tokens_used"]}


def test_scope_eval(live_provider, superuser, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    c = signed_in("root@example.com")
    slug = c.post("/api/projects", json={"name": "Evaluación"}).json()["slug"]
    refusals = _refusals()
    counts: dict[str, dict[str, int]] = {}
    for group in ("off_topic", "on_topic"):
        for index, text in enumerate(PROMPTS[group]):
            lang = "es" if index < 20 else "en"
            result = _ask(c, slug, text)
            reply = result["reply"] or {}
            content = _norm(reply.get("content", ""))
            precheck = (reply.get("scope") or {}).get("path") == "precheck"
            declined = precheck or content.startswith(refusals)
            key = f"{group}:{lang}"
            stats = counts.setdefault(key, {"declined": 0, "answered": 0, "precheck": 0,
                                            "tokens": 0})
            stats["declined" if declined else "answered"] += 1 if content else 0
            stats["precheck"] += 1 if precheck else 0
            stats["tokens"] += result["tokens"]
            print(f"{key} {'DECLINED' if declined else 'ANSWERED'} "
                  f"{'(pre-check)' if precheck else ''} {text!r}")
    print(counts)
    declined = sum(counts[f"off_topic:{lang}"]["declined"] for lang in ("es", "en"))
    answered = sum(counts[f"on_topic:{lang}"]["answered"] for lang in ("es", "en"))
    assert declined >= REQUIRED, counts
    assert answered >= REQUIRED, counts
