"""The app guide for every signed-in user (feature 023, plan §9): the index and the topics the
viewer's role may read, in the request language."""
from fastapi import APIRouter, Depends, Response

from app import guide
from app.auth.deps import current_user
from app.errors import ApiError
from app.i18n import M, current
from app.models import AppUser

router = APIRouter(prefix="/api/guide")
CACHE = "private, max-age=300"


def _related(meta: guide.TopicMeta, lang: str, user: AppUser) -> list[dict]:
    loaded = guide.load()
    out = []
    for topic_id in meta.related:
        other = loaded.meta(topic_id)
        if other is not None and guide.visible(other, user):
            out.append({"id": other.id, "title": other.title[lang]})
    return out


@router.get("")
def guide_index(response: Response, user: AppUser = Depends(current_user)):
    lang = guide.lang_of(current())
    topics = guide.topics_for(user, lang)
    sections = {topic.section for topic in topics}
    response.headers["Cache-Control"] = CACHE
    return {
        "version": guide.load().version,
        "sections": [{"id": s.id, "title": s.title[lang]} for s in guide.load().sections
                     if s.id in sections],
        "topics": [{"id": m.id, "section": m.section, "title": m.title[lang],
                    "summary": m.summary[lang], "roles": list(m.roles),
                    "related": [r["id"] for r in _related(m, lang, user)]} for m in topics],
    }


@router.get("/topics/{topic_id}")
def guide_topic(topic_id: str, response: Response, user: AppUser = Depends(current_user)):
    lang = guide.lang_of(current())
    topic = guide.get(topic_id, lang, user)
    if topic is None:     # unknown or not visible: the same answer
        raise ApiError(404, "guide_topic_not_found", M("guide.topic_not_found"))
    response.headers["Cache-Control"] = CACHE
    meta = topic.meta
    return {"id": meta.id, "title": meta.title[lang], "body": topic.body,
            "roles": list(meta.roles), "routes": list(meta.routes),
            "related": _related(meta, lang, user)}
