"""Feature 044 US2: images fetched once from a URL column, cached by content hash."""
from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.images import cache
from app.models import ImageCache
from app.security import netguard


def _png(shade: int = 30) -> bytes:
    import io

    from PIL import Image as Pillow

    buffer = io.BytesIO()
    Pillow.new("RGB", (8, 8), (shade, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()
OTHER = _png(200)


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "image_cache_dir", str(tmp_path / "images"))
    return tmp_path / "images"


@pytest.fixture
def fetched(monkeypatch):
    """Point the module at a fake network: {url: bytes} and a list of what was asked for."""
    asked: list[str] = []
    served: dict[str, bytes] = {}

    def fake_download(url: str) -> tuple[bytes, str, str]:
        asked.append(url)
        data = served.get(url)
        if data is None:
            raise cache.ImageRefused("fetch_failed")
        # The real checks still run: this fake replaces the socket, not the validation.
        kind, content_type = cache._accept(data, url)
        return data, kind, content_type

    monkeypatch.setattr(cache, "download", fake_download)
    return served, asked


def test_one_file_per_distinct_image_and_two_urls_share_it(db, fetched):
    served, _ = fetched
    served["https://cdn.example/a.png"] = PNG
    served["https://cdn.example/a-copy.png"] = PNG
    served["https://cdn.example/b.png"] = OTHER

    first = cache.store(db, "https://cdn.example/a.png")
    second = cache.store(db, "https://cdn.example/a-copy.png")
    third = cache.store(db, "https://cdn.example/b.png")

    assert first.status == "ok" and third.status == "ok"
    assert cache.name_of(first) == cache.name_of(second) != cache.name_of(third)
    names = sorted(p.name for p in (get_settings().image_cache_dir and
                                   __import__("pathlib").Path(
                                       get_settings().image_cache_dir)).iterdir())
    assert len(names) == 2, names
    assert cache.name_of(first) in names


def test_a_failed_fetch_is_recorded_and_not_retried_within_a_day(db, fetched):
    served, asked = fetched
    row = cache.store(db, "https://cdn.example/gone.png")
    assert row.status == "failed" and row.sha256 is None and row.error

    assert cache.pending(db, ["https://cdn.example/gone.png"]) == []
    assert cache.refresh(db, ["https://cdn.example/gone.png"]) == {}
    assert asked == ["https://cdn.example/gone.png"]

    # Past the window it is worth one more attempt.
    row.fetched_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()
    served["https://cdn.example/gone.png"] = PNG
    assert list(cache.refresh(db, ["https://cdn.example/gone.png"])) == [
        "https://cdn.example/gone.png"]
    assert asked.count("https://cdn.example/gone.png") == 2


def test_a_body_that_is_not_an_image_is_refused(db, fetched):
    served, _ = fetched
    served["https://cdn.example/page.html"] = b"<html>not an image</html>"
    row = cache.store(db, "https://cdn.example/page.html")
    assert row.status == "failed"


def test_a_private_address_never_reaches_a_socket(db):
    """The guard is the sources' one: loopback is refused before the connection is opened."""
    with pytest.raises(cache.ImageRefused):
        cache.download("http://127.0.0.1/logo.png")
    row = cache.store(db, "http://127.0.0.1/logo.png")
    assert row.status == "failed" and row.sha256 is None


def test_only_absolute_http_urls_travel(db):
    for bad in ("/assets/coins/BTC.png", "file:///etc/passwd", "", "ftp://example.com/a.png"):
        with pytest.raises(cache.ImageRefused):
            cache.check_url(bad)


def test_svg_from_a_url_is_refused(db, fetched):
    served, _ = fetched
    served["https://cdn.example/logo.svg"] = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    assert cache.store(db, "https://cdn.example/logo.svg").status == "failed"


def test_the_guarded_client_refuses_a_private_destination(monkeypatch):
    """The real transport path: the policy answers before a socket is opened."""
    policy = netguard.Policy(allow_private=False)
    with pytest.raises(netguard.BlockedAddress):
        netguard.resolve_checked("127.0.0.1", 80, policy)


def test_a_run_stops_at_the_budget(db, fetched, monkeypatch):
    served, _ = fetched
    monkeypatch.setattr(cache, "MAX_PER_RUN", 2)
    urls = [f"https://cdn.example/{n}.png" for n in range(5)]
    for n, url in enumerate(urls):
        served[url] = _png(n + 10)
    assert len(cache.refresh(db, urls)) == 2
    assert len(cache.pending(db, urls)) == 3


def test_read_serves_the_bytes_and_refuses_a_name_that_lies(db, fetched):
    served, _ = fetched
    served["https://cdn.example/a.png"] = PNG
    name = cache.name_of(cache.store(db, "https://cdn.example/a.png"))

    data, content_type, digest = cache.read(name)
    assert data == PNG and content_type == "image/png" and digest == name.split(".")[0]

    with pytest.raises(FileNotFoundError):
        cache.read("../../etc/passwd")
    with pytest.raises(FileNotFoundError):
        cache.read("0" * 64 + ".png")          # nothing stored under that hash


def test_the_sweep_drops_stale_rows_and_orphan_files(db, fetched):
    served, _ = fetched
    served["https://cdn.example/a.png"] = PNG
    row = cache.store(db, "https://cdn.example/a.png")
    name = cache.name_of(row)
    folder = __import__("pathlib").Path(get_settings().image_cache_dir)
    assert (folder / name).exists()

    monkeypatch_days = get_settings().image_cache_days
    row.fetched_at = datetime.now(UTC) - timedelta(days=monkeypatch_days + 1)
    db.commit()
    assert cache.sweep(db) == 1
    assert not (folder / name).exists()
    assert db.query(ImageCache).count() == 0


def test_the_columns_come_from_the_reports_that_ask_for_them():
    version = type("V", (), {"artifacts": {"reports": {
        "cripto": {"definition": {
            "uses": {"l": "cripto.logos", "p": "precios.dia"},
            "images": {"coins": {"folder": "assets/coins", "key": "symbol"},
                       "logos": {"column": "l.logo_url", "key": "symbol"},
                       "otos": {"column": "p.foto", "key": "symbol"}},
        }},
    }}})()
    assert cache.columns_for(version, "cripto") == [("logos", "logo_url")]
    assert cache.columns_for(version, "precios") == [("dia", "foto")]

def test_a_url_without_an_extension_is_judged_by_its_bytes(db, fetched):
    """`/logos/1234` and `/logo.png?v=2` carry no usable extension: the magic bytes decide."""
    served, _ = fetched
    served["https://cdn.example/logos/1234"] = PNG
    served["https://cdn.example/logo.png?v=2"] = OTHER
    assert cache.store(db, "https://cdn.example/logos/1234").status == "ok"
    assert cache.store(db, "https://cdn.example/logo.png?v=2").status == "ok"
