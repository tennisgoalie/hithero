import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.repositories.admin import AdminRepository
from backend.services.admin import AdminService, PendingUserNotFound, UserAccountNotFound


class RecordingRepository:
    def __init__(self, deleted=True):
        self.deleted = deleted
        self.target_email = None

    def delete_user_account(self, target_email):
        self.target_email = target_email
        return self.deleted

    def delete_pending_user(self, user_email):
        self.pending_email = user_email
        return self.deleted

    def validate_pending_user(self, user_email, **values):
        self.validated_email = user_email
        self.validation_values = values
        return (user_email if self.deleted else None, None if self.deleted else "missing")

    def update_pending_flag(self, user_email, **values):
        self.flag_email = user_email
        self.flag_values = values
        return self.deleted


def test_admin_service_deletes_account_and_preserves_message():
    repository = RecordingRepository()
    service = AdminService(repository)

    message = service.delete_user_account("target@example.test")

    assert repository.target_email == "target@example.test"
    assert message == (
        "Successfully deleted account and associated data for target user: "
        "target@example.test."
    )


def test_admin_service_maps_missing_account_to_domain_error():
    service = AdminService(RecordingRepository(deleted=False))

    with pytest.raises(UserAccountNotFound, match="target@example.test"):
        service.delete_user_account("target@example.test")


def test_admin_service_deletes_pending_user_and_maps_missing_user():
    repository = RecordingRepository()
    service = AdminService(repository)
    service.delete_pending_user("pending@example.test")
    assert repository.pending_email == "pending@example.test"

    with pytest.raises(PendingUserNotFound):
        AdminService(RecordingRepository(deleted=False)).delete_pending_user(
            "missing@example.test"
        )


class FailingSession:
    def __init__(self):
        self.rollback_called = False
        self.closed = False

    def execute(self, _query):
        raise RuntimeError("delete failed")

    def rollback(self):
        self.rollback_called = True

    def close(self):
        self.closed = True


def test_admin_repository_rolls_back_and_closes_failed_account_deletion(
    app_module,
):
    session = FailingSession()
    repository = AdminRepository(
        session_factory=lambda: session,
        registered_user_model=app_module.RegisteredUsers,
        teacher_model=app_module.TeacherList,
    )

    with pytest.raises(RuntimeError, match="delete failed"):
        repository.delete_user_account("target@example.test")

    assert session.rollback_called is True
    assert session.closed is True


def test_admin_repository_rolls_back_and_closes_failed_pending_deletion(
    app_module,
):
    session = FailingSession()
    repository = AdminRepository(
        session_factory=lambda: session,
        registered_user_model=app_module.RegisteredUsers,
        teacher_model=app_module.TeacherList,
        pending_user_model=app_module.NewUsers,
    )

    with pytest.raises(RuntimeError, match="delete failed"):
        repository.delete_pending_user("pending@example.test")

    assert session.rollback_called is True
    assert session.closed is True


def test_admin_service_validates_pending_user_with_scope_inputs():
    repository = RecordingRepository()
    service = AdminService(repository)

    assert service.validate_pending_user(
        "pending@example.test",
        role="teacher",
        current_user_id=42,
    ) == "pending@example.test"
    assert repository.validated_email == "pending@example.test"
    assert repository.validation_values == {
        "role": "teacher",
        "current_user_id": 42,
    }


def test_admin_service_updates_report_and_emailed_flags():
    repository = RecordingRepository()
    service = AdminService(repository)

    service.report_pending_user(
        "pending@example.test", role="teacher", current_user_id=42
    )
    assert repository.flag_email == "pending@example.test"
    assert repository.flag_values == {
        "flag_name": "report",
        "flag_value": 1,
        "role": "teacher",
        "current_user_id": 42,
    }

    service.mark_pending_user_emailed(
        "pending@example.test", role="admin", current_user_id=None
    )
    assert repository.flag_values == {
        "flag_name": "emailed",
        "flag_value": 1,
        "role": "admin",
        "current_user_id": None,
    }


def test_admin_repository_rolls_back_and_closes_failed_validation(app_module):
    session = FailingSession()
    repository = AdminRepository(
        session_factory=lambda: session,
        registered_user_model=app_module.RegisteredUsers,
        teacher_model=app_module.TeacherList,
        pending_user_model=app_module.NewUsers,
    )

    with pytest.raises(RuntimeError, match="delete failed"):
        repository.validate_pending_user(
            "pending@example.test",
            role="admin",
            current_user_id=None,
        )

    assert session.rollback_called is True
    assert session.closed is True


def test_admin_delete_account_api_preserves_auth_secret_and_success_contract(
    app_module,
    monkeypatch,
):
    app_module.init_db()
    db = app_module.SessionLocal()
    try:
        db.execute(delete(app_module.TeacherList))
        db.execute(delete(app_module.RegisteredUsers))
        admin = app_module.RegisteredUsers(
            email="admin-delete@example.test",
            phone_number="555-0190",
            password=app_module.sha256_crypt.hash("admin-password"),
            role="admin",
            createCount=0,
        )
        target = app_module.RegisteredUsers(
            email="target-delete@example.test",
            phone_number="555-0191",
            password=app_module.sha256_crypt.hash("target-password"),
            role="teacher",
            createCount=1,
        )
        db.add_all([admin, target])
        db.flush()
        db.add(
            app_module.TeacherList(
                name="Target Teacher",
                state="WA",
                county="King",
                district="Seattle Public Schools",
                school="Lincoln High School",
                regUserID=target.id,
                url_id="target-delete",
            )
        )
        db.commit()
    finally:
        db.close()

    app_module.app.state.limiter._storage.reset()
    monkeypatch.setenv("admin_secret", "test-admin-secret")
    client = TestClient(app_module.app)
    login = client.post(
        "/profile/login/",
        data={
            "email": "admin-delete@example.test",
            "password": "admin-password",
        },
    )
    assert login.status_code == 200

    response = client.post(
        "/profile/delete/",
        data={
            "target_email": "target-delete@example.test",
            "admin_secret_input": "test-admin-secret",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "message": (
            "Successfully deleted account and associated data for target user: "
            "target-delete@example.test."
        )
    }

    db = app_module.SessionLocal()
    try:
        assert db.query(app_module.RegisteredUsers).filter_by(
            email="target-delete@example.test"
        ).first() is None
        assert db.query(app_module.TeacherList).filter_by(
            url_id="target-delete"
        ).first() is None
    finally:
        db.close()


def test_validate_user_api_preserves_scope_and_promotion_contract(app_module):
    app_module.init_db()
    db = app_module.SessionLocal()
    try:
        db.execute(delete(app_module.TeacherList))
        db.execute(delete(app_module.RegisteredUsers))
        db.execute(delete(app_module.NewUsers))
        teacher = app_module.RegisteredUsers(
            email="validator@example.test",
            phone_number="555-0194",
            password=app_module.sha256_crypt.hash("validator-password"),
            role="teacher",
            createCount=1,
        )
        db.add(teacher)
        db.flush()
        db.add(
            app_module.TeacherList(
                name="Validator Teacher",
                state="WA",
                county="King",
                district="Seattle Public Schools",
                school="Lincoln High School",
                regUserID=teacher.id,
                url_id="validator-teacher",
            )
        )
        db.add(
            app_module.NewUsers(
                name="Pending Teacher",
                email="pending-validation@example.test",
                state="WA",
                county="King",
                district="Seattle Public Schools",
                school="Roosevelt High School",
                phone_number="555-0195",
                password=app_module.sha256_crypt.hash("pending-password"),
                role="teacher",
                report=0,
                emailed=0,
            )
        )
        db.commit()
    finally:
        db.close()
    app_module.app.state.limiter._storage.reset()
    client = TestClient(app_module.app)
    login = client.post(
        "/profile/login/",
        data={
            "email": "validator@example.test",
            "password": "validator-password",
        },
    )
    assert login.status_code == 200

    response = client.post(
        "/validation/validate_user/pending-validation@example.test"
    )
    assert response.status_code == 200
    assert response.json() == {"message": "User validated."}

    db = app_module.SessionLocal()
    try:
        assert db.query(app_module.NewUsers).filter_by(
            email="pending-validation@example.test"
        ).first() is None
        registered = db.query(app_module.RegisteredUsers).filter_by(
            email="pending-validation@example.test"
        ).one()
        assert registered.createCount == 0
    finally:
        db.close()


def test_admin_validation_list_serializes_pending_model_rows(app_module):
    app_module.init_db()
    db = app_module.SessionLocal()
    try:
        db.execute(delete(app_module.TeacherList))
        db.execute(delete(app_module.RegisteredUsers))
        db.execute(delete(app_module.NewUsers))
        db.add(
            app_module.RegisteredUsers(
                email="validation-admin@example.test",
                phone_number="555-0198",
                password=app_module.sha256_crypt.hash("admin-password"),
                role="admin",
                createCount=0,
            )
        )
        db.add(
            app_module.NewUsers(
                name="Pending Admin List Teacher",
                email="pending-admin-list@example.test",
                state="WA",
                county="King",
                district="Seattle Public Schools",
                school="Roosevelt High School",
                phone_number="555-0199",
                password=app_module.sha256_crypt.hash("pending-password"),
                role="teacher",
                report=0,
                emailed=0,
            )
        )
        db.commit()
    finally:
        db.close()

    app_module.app.state.limiter._storage.reset()
    client = TestClient(app_module.app)
    assert client.post(
        "/profile/login/",
        data={
            "email": "validation-admin@example.test",
            "password": "admin-password",
        },
    ).status_code == 200

    response = client.get("/api/validation_list/")

    assert response.status_code == 200
    assert response.json() == {
        "new_users": [
            {
                "name": "Pending Admin List Teacher",
                "email": "pending-admin-list@example.test",
                "state": "WA",
                "district": "Seattle Public Schools",
                "school": "Roosevelt High School",
                "phone_number": "555-0199",
                "report": 0,
                "emailed": 0,
            }
        ],
        "role": "admin",
    }


@pytest.mark.parametrize(
    "path",
    (
        "/validation/validate_user/out-of-district@example.test",
        "/validation/report_user/out-of-district@example.test",
        "/validation/emailed_user/out-of-district@example.test",
    ),
)
def test_teacher_validation_mutations_reject_wrong_district(app_module, path):
    app_module.init_db()
    db = app_module.SessionLocal()
    try:
        db.execute(delete(app_module.TeacherList))
        db.execute(delete(app_module.RegisteredUsers))
        db.execute(delete(app_module.NewUsers))
        validator = app_module.RegisteredUsers(
            email="district-validator@example.test",
            phone_number="555-0196",
            password=app_module.sha256_crypt.hash("validator-password"),
            role="teacher",
            createCount=1,
        )
        db.add(validator)
        db.flush()
        db.add(
            app_module.TeacherList(
                name="District Validator",
                state="WA",
                county="King",
                district="Seattle Public Schools",
                school="Lincoln High School",
                regUserID=validator.id,
                url_id="district-validator",
            )
        )
        db.add(
            app_module.NewUsers(
                name="Out of District Teacher",
                email="out-of-district@example.test",
                state="WA",
                county="Pierce",
                district="Tacoma Public Schools",
                school="Stadium High School",
                phone_number="555-0197",
                password=app_module.sha256_crypt.hash("pending-password"),
                role="teacher",
                report=0,
                emailed=0,
            )
        )
        db.commit()
    finally:
        db.close()

    app_module.app.state.limiter._storage.reset()
    client = TestClient(app_module.app)
    assert client.post(
        "/profile/login/",
        data={
            "email": "district-validator@example.test",
            "password": "validator-password",
        },
    ).status_code == 200

    response = client.post(path)

    assert response.status_code == 403

    db = app_module.SessionLocal()
    try:
        pending = db.query(app_module.NewUsers).filter_by(
            email="out-of-district@example.test"
        ).one()
        assert pending.report == 0
        assert pending.emailed == 0
    finally:
        db.close()
