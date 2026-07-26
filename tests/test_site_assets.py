from xml.etree import ElementTree

from fastapi.testclient import TestClient
from sqlalchemy import delete

from tests.conftest import ROOT_DIR


EXPECTED_SITEMAP_LOCS = {
    "https://www.helpteachers.net/",
    "https://www.helpteachers.net/teachers",
    "https://www.helpteachers.net/about",
    "https://www.helpteachers.net/contact",
    "https://www.helpteachers.net/terms",
    "https://www.helpteachers.net/partners",
}


def read_sitemap_locs(sitemap_path):
    root = ElementTree.parse(sitemap_path).getroot()
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {element.text for element in root.findall(".//sm:loc", namespace)}


def seed_sitemap_teachers(app_module):
    app_module.init_db()
    db = app_module.SessionLocal()
    try:
        db.execute(delete(app_module.TeacherList))
        db.add_all(
            [
                app_module.TeacherList(name="Public Teacher", url_id="public-teacher"),
                app_module.TeacherList(name="Pending Teacher", url_id="pending-teacher"),
                app_module.TeacherList(name=None, url_id="missing-name"),
                app_module.TeacherList(name="Missing URL", url_id=None),
                app_module.TeacherList(name="Empty URL", url_id=""),
            ]
        )
        db.commit()
    finally:
        db.close()


def test_site_router_serves_public_asset_contracts(app_module):
    seed_sitemap_teachers(app_module)
    client = TestClient(app_module.app)

    ads = client.get("/ads.txt")
    sitemap = client.get("/sitemap.xml")

    assert ads.status_code == 200
    assert "text/plain" in ads.headers["content-type"]
    assert sitemap.status_code == 200
    assert "application/xml" in sitemap.headers["content-type"]
    assert sitemap.headers["cache-control"] == (
        "public, max-age=300, stale-while-revalidate=60"
    )
    assert sitemap.headers["etag"]
    assert "last-modified" not in sitemap.headers

    locations = {
        element.text
        for element in ElementTree.fromstring(sitemap.content).findall(
            ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )
    }
    assert locations == EXPECTED_SITEMAP_LOCS | {
        "https://www.helpteachers.net/teacher/public-teacher",
        "https://www.helpteachers.net/teacher/pending-teacher",
    }
    assert b"lastmod" not in sitemap.content

    cached = client.get(
        "/sitemap.xml",
        headers={"If-None-Match": sitemap.headers["etag"]},
    )
    assert cached.status_code == 304
    assert cached.content == b""
    assert cached.headers["cache-control"] == sitemap.headers["cache-control"]
    assert cached.headers["etag"] == sitemap.headers["etag"]


def test_frontend_and_backend_sitemaps_are_canonical_and_match():
    backend_sitemap = ROOT_DIR / "static" / "sitemap.xml"
    frontend_sitemap = ROOT_DIR / "frontend" / "static" / "sitemap.xml"

    assert read_sitemap_locs(backend_sitemap) == EXPECTED_SITEMAP_LOCS
    assert read_sitemap_locs(frontend_sitemap) == EXPECTED_SITEMAP_LOCS


def test_robots_files_reference_the_canonical_sitemap():
    for robots_path in (
        ROOT_DIR / "static" / "robots.txt",
        ROOT_DIR / "frontend" / "static" / "robots.txt",
    ):
        source = robots_path.read_text(encoding="utf-8")

        assert "User-agent: *" in source
        assert "Sitemap: https://www.helpteachers.net/sitemap.xml" in source
        assert "/pages/" not in source
