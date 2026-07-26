from backend.core.errors import ConflictError, ForbiddenError, NotFoundError
from backend.core.policies import require_teacher_district_scope


class UserAccountNotFound(NotFoundError):
    """Raised when an administrator targets an unknown registered account."""


class PendingUserNotFound(NotFoundError):
    """Raised when an administrator targets an unknown pending user."""


class ValidationScopeForbidden(ForbiddenError):
    """Raised when a teacher validates outside their district scope."""


class AdminService:
    """Administrator use cases that coordinate policy and persistence."""

    def __init__(self, repository):
        self._repository = repository

    def delete_user_account(self, target_email):
        if not self._repository.delete_user_account(target_email):
            raise UserAccountNotFound(target_email)
        return (
            "Successfully deleted account and associated data for target user: "
            f"{target_email}."
        )

    def delete_pending_user(self, user_email):
        if not self._repository.delete_pending_user(user_email):
            raise PendingUserNotFound(user_email)

    def validate_pending_user(self, user_email, *, role, current_user_id):
        email, error = self._repository.validate_pending_user(
            user_email,
            role=role,
            current_user_id=current_user_id,
        )
        if error == "missing":
            raise PendingUserNotFound(user_email)
        if error == "forbidden":
            require_teacher_district_scope(False, detail=user_email)
        return email

    def report_pending_user(self, user_email, *, role, current_user_id):
        return self._update_pending_flag(
            user_email,
            flag_name="report",
            role=role,
            current_user_id=current_user_id,
        )

    def mark_pending_user_emailed(self, user_email, *, role, current_user_id):
        return self._update_pending_flag(
            user_email,
            flag_name="emailed",
            role=role,
            current_user_id=current_user_id,
        )

    def get_validation_users(self, *, role, user_id):
        if role == "admin":
            return None, self._repository.get_pending_users()
        teacher = self._repository.get_teacher_by_user_id(user_id)
        if teacher is None:
            return None, []
        scope = {
            "state": teacher.state,
            "county": teacher.county,
            "district": teacher.district,
        }
        return teacher, self._repository.get_pending_users(scope=scope)

    def build_teacher_report(self, *, state, county=None, district=None, school=None):
        rows = self._repository.get_teacher_report_rows(
            state=state,
            county=county,
            district=district,
            school=school,
        )
        if rows is None:
            return None
        data = ["Name\tSchool\tEmail\tPhone"]
        data.extend(
            f"{name}\t{school_name}\t{email}\t{phone}"
            for name, school_name, email, phone in rows
        )
        return "\n".join(data)

    def _update_pending_flag(self, user_email, *, flag_name, role, current_user_id):
        if not self._repository.update_pending_flag(
            user_email,
            flag_name=flag_name,
            flag_value=1,
            role=role,
            current_user_id=current_user_id,
        ):
            require_teacher_district_scope(False, detail=user_email)
