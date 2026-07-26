import pytest
from sqlalchemy import func, select

from backend.db.models import School, TeacherList
from backend.local_demo import (
    FIXTURE_DIR,
    SCHOOL_HEADERS,
    SCHOOLS_FIXTURE,
    bootstrap_local_database,
)


def test_local_demo_bootstrap_creates_schema_and_seed_data_idempotently(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'local-demo.sqlite'}"

    first = bootstrap_local_database(database_url)
    second = bootstrap_local_database(database_url)

    assert first.schools_added == 100
    assert first.teachers_added == 50
    assert second.schools_added == 0
    assert second.teachers_added == 0

    from backend.db.session import create_database_resources

    resources = create_database_resources("test", database_url=database_url)
    try:
        db = resources.session_factory()
        try:
            assert db.execute(select(func.count()).select_from(School)).scalar_one() >= 100
            assert db.execute(select(func.count()).select_from(TeacherList)).scalar_one() == 50
        finally:
            db.close()
    finally:
        resources.engine.dispose()


def test_local_demo_bootstrap_rejects_non_sqlite_urls():
    with pytest.raises(ValueError, match="only accepts SQLite"):
        bootstrap_local_database("mssql+pyodbc://example/database")


def test_local_demo_fixtures_have_expected_headers_and_counts():
    schools_header = (FIXTURE_DIR / SCHOOLS_FIXTURE).read_text(encoding="utf-8").splitlines()[0]

    assert tuple(schools_header.split(",")) == SCHOOL_HEADERS
    assert len((FIXTURE_DIR / SCHOOLS_FIXTURE).read_text(encoding="utf-8").splitlines()) == 101


def test_local_demo_bootstrap_rejects_invalid_fixture_headers(tmp_path):
    (tmp_path / "schools.csv").write_text("wrong,headers\nvalue,value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must have headers"):
        bootstrap_local_database(
            f"sqlite:///{tmp_path / 'local-demo.sqlite'}",
            fixture_dir=tmp_path,
        )
