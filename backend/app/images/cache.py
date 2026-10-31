"""The image cache: fetch a URL once, serve it from disk for ever (044, US2).

A report may declare `images: {logos: {column: l.logo_url, key: symbol}}`. After an integration
loads, the worker collects the distinct values of that column, fetches the ones it does not know
and stores the bytes under `IMAGE_CACHE_DIR`, named by their SHA-256. The dataset value is then
rewritten to `<sha256>.<ext>`, so a viewer asks Bizview for the picture and never the third party.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.i18n import M
from app.models import ImageCache
from app.projects import assets as asset_rules
from app.security import netguard

log = logging.getLogger("app.images")

MAX_KB = 300
TIMEOUT_S = 10.0
RETRY_AFTER = timedelta(hours=24)
MAX_PER_RUN = 500
#: SVG is refused from a URL: it would need sanitising on every fetch, and the PDF cannot embed it.
REFUSED_KINDS = ("svg",)
SCHEMES = ("http", "https")


class ImageRefused(Exception):
    """The URL cannot be cached; `reason` is the message the run log records."""

    def __init__(self, reason: "M | str") -> None:
        super().__init__(str(reason))
        self.reason = reason


def cache_dir() -> Path:
    path = Path(get_settings().image_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def name_of(row: ImageCache) -> str | None:
    """The file name of a cached image: the hash and the extension, nothing else."""
    if row.status != "ok" or not row.sha256 or not row.ext:
        return None
    return f"{row.sha256}.{row.ext}"


def check_url(url: str) -> str:
    """The URL to fetch, or `ImageRefused` when it cannot be one.

    Only absolute http(s) addresses travel: a relative path would be resolved against the worker's
    own host, which is exactly the request this cache exists to prevent.
    """
    candidate = (url or "").strip()
    parts = urlsplit(candidate)
    if parts.scheme.lower() not in SCHEMES or not parts.hostname:
        raise ImageRefused(M("images.bad_url"))
    if len(candidate) > 2048:
        raise ImageRefused(M("images.bad_url"))
    return candidate


def _accept(data: bytes, url: str) -> tuple[str, str]:
    """(kind, content type) of a fetched body, or `ImageRefused`."""
    name = urlsplit(url).path.rsplit("/", 1)[-1] or "image"
    try:
        kind = asset_rules.sniff(data, name, strict=False)
    except asset_rules.AssetRefused as e:
        raise ImageRefused(e.reason) from e
    if kind in REFUSED_KINDS:
        raise ImageRefused("svg_not_allowed")
    if len(data) > MAX_KB * 1024:
        raise ImageRefused("too_large")
    return kind, asset_rules.CONTENT_TYPES[kind]


def download(url: str) -> tuple[bytes, str, str]:
    """Fetch one image under the sources' address guard: (bytes, kind, content type)."""
    settings = get_settings()
    policy = netguard.policy_from_settings(settings)
    try:
        with netguard.guarded_client(policy=policy, timeout=TIMEOUT_S) as client:
            response = client.get(url, headers={"Accept": "image/*"})
    except netguard.BlockedAddress as e:
        raise ImageRefused(e.reason) from e
    except httpx.HTTPError as e:
        raise ImageRefused(M("images.fetch_failed", detail=type(e).__name__)) from e
    if response.status_code != 200:
        raise ImageRefused(M("images.fetch_failed", detail=f"HTTP {response.status_code}"))
    length = response.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_KB * 1024:
        raise ImageRefused("too_large")
    kind, content_type = _accept(response.content, url)
    return response.content, kind, content_type


def store(db: Session, url: str) -> ImageCache:
    """Fetch `url` and record the outcome; never raises for the network, only returns a row."""
    try:
        candidate = check_url(url)
    except ImageRefused as e:
        return _record(db, url, status="failed", error=_reason(e))
    try:
        data, kind, _ = download(candidate)
    except ImageRefused as e:
        return _record(db, url, status="failed", error=_reason(e))
    digest = hashlib.sha256(data).hexdigest()
    target = cache_dir() / f"{digest}.{kind}"
    if not target.exists():
        target.write_bytes(data)          # content-addressed: same bytes, same file
    return _record(db, url, status="ok", sha256=digest, ext=kind, size=len(data))


def _record(db: Session, url: str, *, status: str, sha256: str | None = None,
            ext: str | None = None, size: int | None = None,
            error: str | None = None) -> ImageCache:
    now = datetime.now(UTC)
    db.execute(pg_insert(ImageCache).values(
        url=url[:2048], sha256=sha256, ext=ext, bytes=size, fetched_at=now, status=status,
        error=error).on_conflict_do_update(
            index_elements=[ImageCache.url],
            set_={"sha256": sha256, "ext": ext, "bytes": size, "fetched_at": now,
                  "status": status, "error": error}))
    db.commit()
    # The write went through the Core, so the session's identity map still holds the old values
    # (`expire_on_commit=False`): drop it, or the caller reads the previous outcome.
    db.expire_all()
    return db.scalar(select(ImageCache).where(ImageCache.url == url[:2048]))


def _reason(e: ImageRefused) -> str:
    return str(e.reason)[:500]


def pending(db: Session, urls: list[str]) -> list[str]:
    """The URLs worth fetching now: unknown ones, and failures older than the retry window."""
    wanted = [u for u in dict.fromkeys(urls) if u]
    if not wanted:
        return []
    rows = {row.url: row for row in db.scalars(
        select(ImageCache).where(ImageCache.url.in_([u[:2048] for u in wanted])))}
    cutoff = datetime.now(UTC) - RETRY_AFTER
    out = []
    for url in wanted:
        row = rows.get(url[:2048])
        if row is None:
            out.append(url)
        elif row.status == "failed" and _naive(row.fetched_at) < cutoff:
            out.append(url)
    return out


def _naive(moment: datetime | None) -> datetime:
    if moment is None:
        return datetime.min.replace(tzinfo=UTC)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def refresh(db: Session, urls: list[str]) -> dict[str, str]:
    """Fetch what `pending` allows, at most `MAX_PER_RUN` new images: {url: file name}.

    A failure is recorded and skipped, never raised: an image that cannot be fetched may not fail
    a load, and the run log names it.
    """
    out: dict[str, str] = {}
    budget = MAX_PER_RUN
    for url in pending(db, urls):
        if budget <= 0:
            log.warning("image cache: %s was more than %d new images; the rest waits for the next "
                        "run", len(urls), MAX_PER_RUN)
            break
        row = store(db, url)
        budget -= 1
        name = name_of(row)
        if name is not None:
            out[url] = name
        else:
            log.info("image cache: %s not cached (%s)", url, row.error)
    return out


def read(name: str) -> tuple[bytes, str, str]:
    """The bytes of a cached image by file name: (bytes, content type, sha256).

    The name is `<sha256>.<ext>` and nothing else, so a caller cannot reach a file it did not name
    and the hash it carries is verifiable.
    """
    stem, _, ext = name.partition(".")
    if len(stem) != 64 or any(c not in "0123456789abcdef" for c in stem) or ext not in (
            "png", "jpeg", "jpg", "webp"):
        raise FileNotFoundError(name)
    target = cache_dir() / f"{stem}.{ext}"
    data = target.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != stem:
        raise FileNotFoundError(name)     # a file whose bytes no longer match its name
    kind = "png" if ext == "png" else ("webp" if ext == "webp" else "jpeg")
    return data, asset_rules.CONTENT_TYPES[kind], digest


def sweep(db: Session) -> int:
    """Drop the files no `ok` row points at, and the rows past the retention window."""
    days = get_settings().image_cache_days
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stale = db.scalars(select(ImageCache).where(ImageCache.fetched_at < cutoff)).all()
    keep = {name_of(row) for row in db.scalars(
        select(ImageCache).where(ImageCache.status == "ok", ImageCache.fetched_at >= cutoff))}
    keep.discard(None)
    removed = 0
    for row in stale:
        db.delete(row)
        removed += 1
    db.commit()
    folder = cache_dir()
    for entry in folder.iterdir():
        if entry.is_file() and entry.name not in keep:
            entry.unlink(missing_ok=True)
    return removed


def forget(db: Session, url: str) -> None:
    """Drop one URL (tests and the operator's repair path)."""
    db.execute(delete(ImageCache).where(ImageCache.url == url[:2048]))
    db.commit()



def columns_for(version, integration_id: str) -> list[tuple[str, str]]:
    """(dataset, column) pairs the applied reports ask this integration for images from.

    The report is the declaration: `images: {logos: {column: l.logo_url}}` together with
    `uses: {l: <integration>.<dataset>}` says exactly which column of which dataset holds URLs, so
    the worker needs no second list that could drift from it.
    """
    out: list[tuple[str, str]] = []
    reports = (getattr(version, "artifacts", None) or {}).get("reports") or {}
    for entry in reports.values():
        definition = (entry or {}).get("definition") or {}
        uses = definition.get("uses") or {}
        for spec in (definition.get("images") or {}).values():
            column = spec.get("column") if isinstance(spec, dict) else None
            if not isinstance(column, str) or "." not in column:
                continue
            alias, name = column.split(".", 1)
            target = uses.get(alias)
            if not isinstance(target, str) or "." not in target:
                continue
            iid, dataset = target.split(".", 1)
            if iid == integration_id and (dataset, name) not in out:
                out.append((dataset, name))
    return out


def _values(schema: str, dataset: str, column: str) -> list[str]:
    """The distinct non-empty values of one column, as psycopg sees them."""
    from psycopg import sql

    query = sql.SQL("SELECT DISTINCT {col} FROM {schema}.{table} WHERE {col} IS NOT NULL").format(
        col=sql.Identifier(column), schema=sql.Identifier(schema),
        table=sql.Identifier(dataset))
    # psycopg's own connection: `Composed` is not a SQLAlchemy statement, and handing it to
    # `Session.execute` raised inside the pass, which swallowed the whole rewrite.
    with get_engine().connect() as conn:
        rows = conn.connection.driver_connection.execute(query).fetchall()
    return [row[0] for row in rows if isinstance(row[0], str) and row[0]]


def _rewrite(schema: str, dataset: str, column: str, urls: list[str],
             cached: dict[str, str]) -> None:
    """Point the loaded rows at the cache: the third-party address becomes `<sha256>.<ext>`."""
    if not cached:
        return
    from psycopg import sql

    query = sql.SQL("UPDATE {schema}.{table} SET {col} = %s WHERE {col} = %s").format(
        col=sql.Identifier(column), schema=sql.Identifier(schema),
        table=sql.Identifier(dataset))
    with get_engine().begin() as conn:
        pg = conn.connection.driver_connection
        for url in urls:
            name = cached.get(url)
            if name is not None:
                pg.execute(query, (name, url))


def names(db: Session, urls: list[str]) -> dict[str, str]:
    """Every URL of the list that already has bytes on disk: {url: file name}.

    The rewrite is a property of "this URL is cached", not of "we cached it just now". Reading the
    rows is what makes a second load point at the file too — without it, the steady state (every
    address already known) kept the declared address in the column and the browser went on asking
    the third party, which is the one case SC-003 cares about.
    """
    wanted = [u[:2048] for u in dict.fromkeys(urls) if u]
    if not wanted:
        return {}
    out: dict[str, str] = {}
    for row in db.scalars(select(ImageCache).where(
            ImageCache.url.in_(wanted), ImageCache.status == "ok")):
        name = name_of(row)
        if name is not None:
            out[row.url] = name
    return out


def refresh_reports(db: Session, version, integration_id: str) -> dict[str, int]:
    """Cache what the applied reports ask of one integration after its load.

    Returns the counts of what happened (`fetched`, `failed`) for the run log. Anything that goes
    wrong here is reported and swallowed: an image may never fail a data load.
    """
    from app.engine import datasets

    counts = {"fetched": 0, "failed": 0}
    if version is None:
        return counts
    schema = datasets.schema_name(integration_id)
    for dataset, column in columns_for(version, integration_id):
        try:
            urls = _values(schema, dataset, column)
        except Exception:      # a missing table is the loader's business, not ours
            log.warning("image cache: cannot read %s.%s", dataset, column, exc_info=True)
            continue
        fetched = refresh(db, urls)
        counts["fetched"] += len(fetched)
        counts["failed"] += len(urls) - len(names(db, urls))
        # Rewrite everything that is cached, whether it was fetched now or by an earlier run.
        cached = names(db, urls)
        try:
            _rewrite(schema, dataset, column, urls, cached)
        except Exception:
            log.warning("image cache: cannot rewrite %s.%s", dataset, column, exc_info=True)
    return counts
