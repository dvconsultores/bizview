"""Feature 044: project images — sniffing, SVG sanitising, lookup and the write path.

The three rules this file exists for: the bytes decide the type (never the extension), an SVG is
stored already clean, and a project cannot be filled past its limits with pictures.
"""
import pytest

from app.config import get_settings
from app.errors import ApiError  # noqa: F401  (kept for the API siblings to mirror)
from app.models import AppUser
from app.projects import assets, fs
from app.projects import service as project_service
from tests.conftest import sql

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 32
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="4" height="4"/></svg>'


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def project(db, superuser):
    p = project_service.create(db, db.get(AppUser, superuser.id), "Con logos")
    db.commit()
    return p


def _actor(user_id: int) -> dict:
    return {"kind": "user", "user_id": user_id, "session_id": None, "command": "edit"}


# --- sniffing ------------------------------------------------------------------------------------

def test_the_bytes_decide_the_type_and_the_name_must_agree():
    assert assets.prepare(PNG, "BTC.png")[1] == "png"
    assert assets.prepare(JPEG, "a.jpg")[1] == "jpeg"
    assert assets.prepare(WEBP, "a.webp")[1] == "webp"
    assert assets.prepare(SVG, "a.svg")[1] == "svg"

    # A text file called .png, a PNG called .svg, and a JPEG with a .png extension.
    for data, name in ((b"hola", "x.png"), (PNG, "x.svg"), (JPEG, "x.png")):
        with pytest.raises(assets.AssetRefused) as exc:
            assets.prepare(data, name)
        assert exc.value.reason == "not_image", name


def test_an_oversize_image_is_refused_naming_the_limit():
    big = PNG + b"\x00" * (assets.MAX_KB * 1024)
    with pytest.raises(assets.AssetRefused) as exc:
        assets.prepare(big, "big.png")
    assert exc.value.reason == "too_large"
    assert "big.png" in exc.value.detail


# --- SVG ------------------------------------------------------------------------------------------

def test_an_svg_is_stored_clean_and_a_script_is_refused():
    stored, kind, content_type = assets.prepare(SVG, "e.svg")
    assert kind == "svg" and content_type == "image/svg+xml"
    assert stored.startswith(b"<svg") and b"ns0:" not in stored

    for bad in (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                b'<svg xmlns="http://www.w3.org/2000/svg"><rect onload="x()"/></svg>',
                b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://x/y.png"/></svg>',
                b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>'):
        with pytest.raises(assets.AssetRefused) as exc:
            assets.prepare(bad, "bad.svg")
        assert exc.value.reason == "svg_refused"
        assert "bad.svg" in exc.value.detail


def test_a_broken_svg_is_refused_without_a_traceback():
    with pytest.raises(assets.AssetRefused) as exc:
        assets.prepare(b"<svg><rect></svg>", "broken.svg")
    assert exc.value.reason == "svg_refused"


# --- lookup ---------------------------------------------------------------------------------------

def test_lookup_tries_the_exact_case_then_the_other_extensions(tmp_path):
    folder = tmp_path / "coins"
    folder.mkdir()
    (folder / "BTC.png").write_bytes(PNG)
    (folder / "eth.svg").write_bytes(SVG)
    (folder / "SOL.webp").write_bytes(WEBP)          # only a case-insensitive match exists

    assert assets.lookup(folder, "BTC").name == "BTC.png"
    assert assets.lookup(folder, "btc").name == "BTC.png"
    assert assets.lookup(folder, "ETH").name == "eth.svg"
    assert assets.lookup(folder, "sol").name == "SOL.webp"
    assert assets.lookup(folder, "HYPE") is None
    assert assets.lookup(folder, "") is None


def test_keys_are_normalised_before_looking_for_a_file(tmp_path):
    folder = tmp_path / "coins"
    folder.mkdir()
    (folder / "USD_Coin.png").write_bytes(PNG)
    assert assets.normalise_key("USD/Coin ") == "USD_Coin"
    assert assets.lookup(folder, "USD/Coin ").name == "USD_Coin.png"
    assert assets.normalise_key("..") == ""


# --- the project write path -----------------------------------------------------------------------

def test_an_image_is_written_versioned_and_read_back(db, project, superuser, projects):
    stored = fs.apply_asset(project.id, "assets/coins/BTC.png", PNG, _actor(superuser.id))

    assert stored["sha256"] == fs.read_asset(project.slug, "assets/coins/BTC.png")[2]
    on_disk = projects / project.slug / "assets/coins/BTC.png"
    assert on_disk.read_bytes() == PNG

    data, content_type, _digest = fs.read_asset(project.slug, "assets/coins/BTC.png")
    assert (data, content_type) == (PNG, "image/png")

    row = sql("SELECT path, op, size, sha256 IS NOT NULL, content IS NULL "
              "FROM project_file_revision WHERE path = 'assets/coins/BTC.png'")
    assert row == [("assets/coins/BTC.png", "update", len(PNG), True, True)], row


def test_a_bad_image_never_reaches_the_disk(db, project, superuser, projects):
    with pytest.raises(assets.AssetRefused):
        fs.apply_asset(project.id, "assets/coins/FAKE.png", b"no soy un png",
                       _actor(superuser.id))
    assert not (projects / project.slug / "assets/coins/FAKE.png").exists()
    assert sql("SELECT count(*) FROM project_file_revision WHERE path LIKE 'assets/%'") == [(0,)]


def test_an_svg_is_stored_sanitised(db, project, superuser, projects):
    fs.apply_asset(project.id, "assets/logos/a.svg", SVG, _actor(superuser.id))
    stored = (projects / project.slug / "assets/logos/a.svg").read_bytes()
    assert stored.startswith(b"<svg") and b"ns0:" not in stored


def test_restoring_an_image_says_why_it_cannot(db, project, superuser):
    from app.projects import history
    from app.projects import service as projects_service

    fs.apply_asset(project.id, "assets/coins/BTC.png", PNG, _actor(superuser.id))
    rev = sql("SELECT id FROM project_file_revision WHERE path = 'assets/coins/BTC.png'")[0][0]
    with pytest.raises(fs.ProjectPathError) as exc:
        history.restore(db, projects_service.get(db, project.slug), rev, None,
                        _actor(superuser.id))
    assert exc.value.code == "asset_not_restorable"


def test_the_editor_route_and_the_asset_route_share_the_scope_rules(db, project, superuser):
    """`assets/` is inside the project, so an escape is refused exactly like any other path."""
    for bad in ("../otro/assets/a.png", "/etc/passwd", f"projects/{project.slug}/assets/a.png"):
        with pytest.raises(fs.ProjectPathError):
            fs.read_asset(project.slug, bad)


# --- the zip is the project ----------------------------------------------------------------

def test_a_project_with_images_round_trips_through_the_zip(db, project, superuser, projects):
    import io
    import zipfile

    from app.projects import zip as project_zip

    fs.apply_asset(project.id, "assets/coins/BTC.png", PNG, _actor(superuser.id))
    fs.apply_asset(project.id, "assets/logos/a.svg", SVG, _actor(superuser.id))
    fs.apply_ops(project.id, [{"op": "write", "path": "reports/ventas/report.yaml",
                               "content": "id: ventas\n", "base_sha256": None, "force": True}],
                 _actor(superuser.id))

    data = project_zip.export(db, db.get(AppUser, superuser.id), project)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert f"{project.slug}/assets/coins/BTC.png" in names
    assert f"{project.slug}/assets/logos/a.svg" in names

    imported = project_zip.import_zip(db, db.get(AppUser, superuser.id), data,
                                      name="Copia con logos")
    copy = imported["project"]["slug"]
    # The export also carries the authoring skeleton, which the import reports as ignored; what
    # matters here is that no image was dropped.
    assert not [name for name in imported["ignored"] if name.startswith("assets/")]
    assert (projects / copy / "assets/coins/BTC.png").read_bytes() == PNG


def test_a_bad_image_in_the_zip_is_ignored_not_half_written(db, project, superuser, projects):
    import io
    import zipfile

    from app.projects import zip as project_zip

    fs.apply_ops(project.id, [{"op": "write", "path": "project.yaml",
                               "content": "slug: copia\nname: Copia\n",
                               "base_sha256": None, "force": True}], _actor(superuser.id))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("copia/project.yaml", "slug: copia\nname: Copia\n")
        zf.writestr("copia/assets/coins/FAKE.png", b"no soy un png")
        zf.writestr("copia/assets/coins/OK.png", PNG)

    imported = project_zip.import_zip(db, db.get(AppUser, superuser.id), buffer.getvalue())
    assert any("FAKE.png" in name for name in imported["ignored"]), imported["ignored"]
    slug = imported["project"]["slug"]
    assert (projects / slug / "assets/coins/OK.png").read_bytes() == PNG
    assert not (projects / slug / "assets/coins/FAKE.png").exists()
