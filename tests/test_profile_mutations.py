from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.db.models import TeacherList
from backend.repositories.profile import ProfileRepository
from backend.services.profile_mutations import (
    InvalidWishlistUrl,
    InvalidTeacherImage,
    InvalidTeacherUrlId,
    ProfileMutationService,
    TeacherImageTooLarge,
    TeacherUrlIdConflict,
)


class RecordingRepository:
    @contextmanager
    def transaction(self):
        yield object()

    def update_teacher_school(self, user_id, **values):
        self.user_id = user_id
        self.values = values

    def update_teacher_name(self, user_id, name):
        self.name_update = (user_id, name)

    def update_teacher_about_me(self, user_id, about_me):
        self.about_me_update = (user_id, about_me)

    def update_teacher_wishlist(self, user_id, wishlist_url):
        self.wishlist_update = (user_id, wishlist_url)

    def get_teacher_by_url_id(self, url_id, **_values):
        self.url_id_lookup = url_id
        return getattr(self, "existing_teacher", None)

    def update_teacher_url_id(self, user_id, url_id):
        self.url_id_update = (user_id, url_id)

    def update_teacher_image(self, user_id, image_bytes):
        self.image_update = (user_id, image_bytes)

    def get_profile_create_count(self, user_id, **_values):
        self.create_count_user_id = user_id
        return getattr(self, "create_count", 0)

    def create_teacher_profile(self, user_id, **values):
        values.pop("db", None)
        self.profile_create = (user_id, values)


def test_profile_mutation_service_passes_school_update_as_one_use_case():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    service.update_teacher_school(
        42,
        state="IL",
        county="Cook",
        district="District 1",
        school="Example School",
    )

    assert repository.user_id == 42
    assert repository.values == {
        "state": "IL",
        "county": "Cook",
        "district": "District 1",
        "school": "Example School",
    }


def test_profile_mutation_service_preserves_name_and_wishlist_updates():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    service.update_teacher_name(42, "Updated Teacher")
    service.update_teacher_wishlist(42, "https://example.test/list")

    assert repository.name_update == (42, "Updated Teacher")
    assert repository.wishlist_update == (
        42,
        "https://example.test/list",
    )


def test_profile_mutation_service_strips_wishlist_query_before_storage():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    service.update_teacher_wishlist(
        42,
        "www.amazon.com/hz/wishlist/ls/ABC?ref_=wl_share",
    )

    assert repository.wishlist_update == (
        42,
        "https://www.amazon.com/hz/wishlist/ls/ABC",
    )


def test_profile_mutation_service_rejects_invalid_wishlist_url():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    with pytest.raises(InvalidWishlistUrl):
        service.update_teacher_wishlist(42, "not a URL")


def test_profile_mutation_service_preserves_about_me_update():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    service.update_teacher_about_me(42, "Updated classroom information")

    assert repository.about_me_update == (
        42,
        "Updated classroom information",
    )


def test_profile_mutation_service_validates_and_updates_teacher_url_id():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    service.update_teacher_url_id(42, "new-teacher_42")

    assert repository.url_id_lookup == "new-teacher_42"
    assert repository.url_id_update == (42, "new-teacher_42")


@pytest.mark.parametrize("url_id", ["no", "bad value", "bad/value", "a" * 51])
def test_profile_mutation_service_rejects_invalid_teacher_url_id(url_id):
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    with pytest.raises(InvalidTeacherUrlId):
        service.update_teacher_url_id(42, url_id)

    assert not hasattr(repository, "url_id_lookup")
    assert not hasattr(repository, "url_id_update")


def test_profile_mutation_service_rejects_teacher_url_id_collision():
    repository = RecordingRepository()
    repository.existing_teacher = object()
    service = ProfileMutationService(repository)

    with pytest.raises(TeacherUrlIdConflict):
        service.update_teacher_url_id(42, "existing-teacher")

    assert repository.url_id_lookup == "existing-teacher"
    assert not hasattr(repository, "url_id_update")


def test_profile_mutation_service_allocates_url_id_and_preserves_affiliate_link(
    monkeypatch,
):
    repository = RecordingRepository()
    monkeypatch.setattr(
        "backend.services.profile_mutations.secrets.randbelow",
        lambda _limit: 1234,
    )
    service = ProfileMutationService(repository)

    created = service.create_teacher_profile(
        42,
        "teacher",
        "teacher@example.test",
        name="Example Teacher",
        state="WA",
        county="King",
        district="Seattle Public Schools",
        school="Lincoln High School",
        about_me="Science supplies",
        wishlist="https://example.test/list",
    )

    assert created is True
    assert repository.create_count_user_id == 42
    assert repository.profile_create == (
        42,
        {
            "name": "Example Teacher",
            "state": "WA",
            "county": "King",
            "district": "Seattle Public Schools",
            "school": "Lincoln High School",
            "about_me": "Science supplies",
            "wishlist_url": "https://example.test/list",
            "url_id": "teacher1234",
        },
    )


def test_profile_mutation_service_retries_colliding_allocated_url_id(monkeypatch):
    repository = RecordingRepository()
    existing_url_ids = {"teacher1234"}
    repository.get_teacher_by_url_id = lambda url_id, **_values: (
        object() if url_id in existing_url_ids else None
    )
    random_values = iter([1234, 5678])
    monkeypatch.setattr(
        "backend.services.profile_mutations.secrets.randbelow",
        lambda _limit: next(random_values),
    )
    service = ProfileMutationService(repository)

    created = service.create_teacher_profile(
        42,
        "teacher",
        "teacher@example.test",
        name="Example Teacher",
        state="WA",
        county="King",
        district="Seattle Public Schools",
        school="Lincoln High School",
        about_me="Science supplies",
        wishlist="https://example.test/list",
    )

    assert created is True
    assert repository.profile_create[1]["url_id"] == "teacher5678"


def test_profile_mutation_service_preserves_existing_profile_guard():
    repository = RecordingRepository()
    repository.create_count = 1
    service = ProfileMutationService(repository)

    created = service.create_teacher_profile(
        42,
        "teacher",
        "teacher@example.test",
        name="Example Teacher",
        state="WA",
        county="King",
        district="Seattle Public Schools",
        school="Lincoln High School",
        about_me="Science supplies",
        wishlist="https://example.test/list",
    )

    assert created is False
    assert not hasattr(repository, "profile_create")



class MimeResult:
    def __init__(self, mime=None, mime_type=None):
        self.mime = mime
        self.mime_type = mime_type


def test_profile_mutation_service_validates_and_persists_teacher_image():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    updated = service.update_teacher_image(
        42,
        "teacher",
        b"image-bytes",
        image_size=11,
        max_file_size=100,
        detect_file_type=lambda _bytes: [MimeResult(mime="image/png")],
    )

    assert updated is True
    assert repository.image_update == (42, b"image-bytes")


def test_profile_mutation_service_preserves_image_validation_order_and_errors():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)
    detector_called = False

    def detector(_bytes):
        nonlocal detector_called
        detector_called = True
        return [MimeResult(mime="image/png")]

    with pytest.raises(TeacherImageTooLarge):
        service.update_teacher_image(
            42,
            "teacher",
            b"large",
            image_size=101,
            max_file_size=100,
            detect_file_type=detector,
        )
    assert detector_called is False

    with pytest.raises(InvalidTeacherImage):
        service.update_teacher_image(
            42,
            "teacher",
            b"text",
            image_size=4,
            max_file_size=100,
            detect_file_type=lambda _bytes: [MimeResult(mime="text/plain")],
        )
    assert not hasattr(repository, "image_update")


def test_profile_mutation_service_returns_permission_message_without_persisting_image():
    repository = RecordingRepository()
    service = ProfileMutationService(repository)

    updated = service.update_teacher_image(
        42,
        None,
        b"image-bytes",
        image_size=11,
        max_file_size=100,
        detect_file_type=lambda _bytes: [MimeResult(mime_type="image/jpeg")],
    )

    assert updated is False
    assert not hasattr(repository, "image_update")


class FailingSession:
    def __init__(self):
        self.rollback_called = False
        self.closed = False

    def execute(self, _query):
        raise RuntimeError("write failed")

    def rollback(self):
        self.rollback_called = True

    def close(self):
        self.closed = True


class ProfileCreateResult:
    def scalar(self):
        return 0

    def fetchone(self):
        return None


class ProfileCreateSession:
    def __init__(self, *, fail_on_execute=None):
        self.execute_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0
        self.fail_on_execute = fail_on_execute

    def execute(self, _query):
        self.execute_count += 1
        if self.execute_count == self.fail_on_execute:
            raise RuntimeError("profile insert failed")
        return ProfileCreateResult()

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.close_count += 1


def test_profile_creation_uses_one_transaction_and_rolls_back_all_writes(
    app_module,
):
    session = ProfileCreateSession(fail_on_execute=4)
    repository = ProfileRepository(
        session_factory=lambda: session,
        teacher_model=TeacherList,
        registered_user_model=app_module.RegisteredUsers,
    )
    service = ProfileMutationService(repository)

    with pytest.raises(RuntimeError, match="profile insert failed"):
        service.create_teacher_profile(
            42,
            "teacher",
            "teacher@example.test",
            name="Example Teacher",
            state="WA",
            county="King",
            district="Seattle Public Schools",
            school="Lincoln High School",
            about_me="Science supplies",
            wishlist="https://example.test/list",
        )

    assert session.execute_count == 4
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.close_count == 1


def test_profile_creation_commits_once_and_closes_on_success(app_module):
    session = ProfileCreateSession()
    repository = ProfileRepository(
        session_factory=lambda: session,
        teacher_model=TeacherList,
        registered_user_model=app_module.RegisteredUsers,
    )
    service = ProfileMutationService(repository)

    created = service.create_teacher_profile(
        42,
        "teacher",
        "teacher@example.test",
        name="Example Teacher",
        state="WA",
        county="King",
        district="Seattle Public Schools",
        school="Lincoln High School",
        about_me="Science supplies",
        wishlist="https://example.test/list",
    )

    assert created is True
    assert session.execute_count == 4
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.close_count == 1


def test_profile_repository_rolls_back_and_closes_failed_school_update():
    session = FailingSession()
    repository = ProfileRepository(
        session_factory=lambda: session,
        teacher_model=TeacherList,
    )

    with pytest.raises(RuntimeError, match="write failed"):
        repository.update_teacher_school(
            42,
            state="IL",
            county="Cook",
            district="District 1",
            school="Example School",
        )

    assert session.rollback_called is True
    assert session.closed is True


def test_profile_repository_rolls_back_and_closes_failed_url_id_update():
    session = FailingSession()
    repository = ProfileRepository(
        session_factory=lambda: session,
        teacher_model=TeacherList,
    )

    with pytest.raises(RuntimeError, match="write failed"):
        repository.update_teacher_url_id(42, "new-teacher")

    assert session.rollback_called is True
    assert session.closed is True


def test_profile_repository_rolls_back_and_closes_failed_profile_creation():
    session = FailingSession()
    repository = ProfileRepository(
        session_factory=lambda: session,
        teacher_model=TeacherList,
        registered_user_model=object(),
    )

    with pytest.raises(RuntimeError, match="write failed"):
        repository.create_teacher_profile(
            42,
            name="Example Teacher",
            state="WA",
            county="King",
            district="Seattle Public Schools",
            school="Lincoln High School",
            about_me="Science supplies",
            wishlist_url="https://example.test/list&tag=h0mer00mher0-20",
            url_id="teacher1234",
        )

    assert session.rollback_called is True
    assert session.closed is True


def test_profile_repository_rolls_back_and_closes_failed_image_update():
    session = FailingSession()
    repository = ProfileRepository(
        session_factory=lambda: session,
        teacher_model=TeacherList,
    )

    with pytest.raises(RuntimeError, match="write failed"):
        repository.update_teacher_image(42, b"image-bytes")

    assert session.rollback_called is True
    assert session.closed is True


def seed_url_id_profiles(app_module):
    app_module.init_db()
    db = app_module.SessionLocal()
    try:
        db.execute(delete(app_module.TeacherList))
        db.execute(delete(app_module.RegisteredUsers))
        user = app_module.RegisteredUsers(
            email="url-id-owner@example.test",
            phone_number="555-0142",
            password=app_module.sha256_crypt.hash("test-password"),
            role="teacher",
            createCount=1,
        )
        db.add(user)
        db.flush()
        db.add(
            app_module.TeacherList(
                name="URL ID Owner",
                state="WA",
                county="King",
                district="Seattle Public Schools",
                school="Lincoln High School",
                regUserID=user.id,
                url_id="owner-teacher",
            )
        )
        db.add(
            app_module.TeacherList(
                name="Other Teacher",
                state="WA",
                county="King",
                district="Seattle Public Schools",
                school="Roosevelt High School",
                regUserID=999,
                url_id="taken-teacher",
            )
        )
        db.commit()
    finally:
        db.close()


def login_url_id_user(client):
    response = client.post(
        "/profile/login/",
        data={
            "email": "url-id-owner@example.test",
            "password": "test-password",
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "teacher"


def test_create_teacher_profile_api_preserves_success_and_allocation_contract(
    app_module,
):
    app_module.init_db()
    db = app_module.SessionLocal()
    try:
        db.execute(delete(app_module.TeacherList))
        db.execute(delete(app_module.RegisteredUsers))
        db.add(
            app_module.RegisteredUsers(
                email="profile-create@example.test",
                phone_number="555-0143",
                password=app_module.sha256_crypt.hash("test-password"),
                role="teacher",
                createCount=0,
            )
        )
        db.commit()
    finally:
        db.close()

    app_module.app.state.limiter._storage.reset()
    client = TestClient(app_module.app)
    response = client.post(
        "/profile/login/",
        data={
            "email": "profile-create@example.test",
            "password": "test-password",
        },
    )
    assert response.status_code == 200

    created = client.post(
        "/profile/create_teacher_profile/",
        data={
            "name": "Created Teacher",
            "state": "WA",
            "county": "King",
            "district": "Seattle Public Schools",
            "school": "Lincoln High School",
            "aboutMe": "Science supplies",
            "wishlist": "https://example.test/list",
        },
    )
    assert created.status_code == 200
    assert created.json() == {
        "message": "Teacher created successfully",
        "role": "teacher",
    }

    db = app_module.SessionLocal()
    try:
        teacher = db.query(app_module.TeacherList).filter_by(
            name="Created Teacher"
        ).one()
        user = db.query(app_module.RegisteredUsers).filter_by(
            email="profile-create@example.test"
        ).one()
        assert teacher.regUserID == user.id
        assert teacher.url_id.startswith("profile-create")
        assert teacher.wishlist_url == "https://example.test/list"
        assert user.createCount == 1
    finally:
        db.close()


def test_update_url_id_api_preserves_validation_collision_and_success_contracts(
    app_module,
):
    seed_url_id_profiles(app_module)
    app_module.app.state.limiter._storage.reset()
    client = TestClient(app_module.app)
    login_url_id_user(client)

    invalid = client.post(
        "/profile/update_url_id/",
        data={"url_id": "bad value"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == (
        "URL ID may only contain letters, numbers, hyphens, and underscores "
        "(3–50 characters)."
    )

    collision = client.post(
        "/profile/update_url_id/",
        data={"url_id": "taken-teacher"},
    )
    assert collision.status_code == 409
    assert collision.json()["detail"] == "URL ID already in use."

    updated = client.post(
        "/profile/update_url_id/",
        data={"url_id": "updated-teacher"},
    )
    assert updated.status_code == 200
    assert updated.json() == {"message": "URL ID updated successfully."}

    db = app_module.SessionLocal()
    try:
        assert db.query(app_module.TeacherList).filter_by(
            name="URL ID Owner", url_id="updated-teacher"
        ).one()
    finally:
        db.close()


def test_teacher_image_api_enforces_size_and_detected_type(app_module):
    seed_url_id_profiles(app_module)
    app_module.app.state.limiter._storage.reset()
    client = TestClient(app_module.app)
    login_url_id_user(client)

    oversized = client.post(
        "/profile/update_teacher_image/",
        files={"image": ("large.png", b"x" * (1024 * 1024 + 1), "image/png")},
    )
    invalid_type = client.post(
        "/profile/update_teacher_image/",
        files={"image": ("teacher.txt", b"plain text", "text/plain")},
    )

    assert oversized.status_code == 400
    assert oversized.json()["detail"] == "File size exceeds the allowed limit"
    assert invalid_type.status_code == 400
    assert invalid_type.json()["detail"] == (
        "Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed."
    )
