from sqlalchemy import String, cast, delete, insert, select, update


class AdminRepository:
    """Persistence operations for administrator account workflows."""

    def __init__(
        self,
        *,
        session_factory,
        registered_user_model,
        teacher_model,
        pending_user_model=None,
    ):
        self._session_factory = session_factory
        self._registered_user_model = registered_user_model
        self._teacher_model = teacher_model
        self._pending_user_model = pending_user_model

    def delete_user_account(self, target_email):
        db = self._session_factory()
        try:
            user_id_result = db.execute(
                select(self._registered_user_model.id).where(
                    cast(self._registered_user_model.email, String)
                    == cast(target_email, String)
                )
            ).fetchone()
            if not user_id_result:
                return False

            target_user_id = user_id_result[0]
            db.execute(
                delete(self._teacher_model).where(
                    self._teacher_model.regUserID == target_user_id
                )
            )
            db.execute(
                delete(self._registered_user_model).where(
                    cast(self._registered_user_model.email, String)
                    == cast(target_email, String)
                )
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_pending_user(self, user_email):
        db = self._session_factory()
        try:
            user = db.execute(
                select(self._pending_user_model).where(
                    cast(self._pending_user_model.email, String)
                    == cast(user_email, String)
                )
            ).fetchone()
            if not user:
                db.rollback()
                return False
            db.execute(
                delete(self._pending_user_model).where(
                    cast(self._pending_user_model.email, String)
                    == cast(user_email, String)
                )
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def validate_pending_user(self, user_email, *, role, current_user_id):
        db = self._session_factory()
        try:
            user_result = db.execute(
                select(self._pending_user_model).where(
                    cast(self._pending_user_model.email, String)
                    == cast(user_email, String)
                )
            ).fetchone()
            if not user_result:
                db.rollback()
                return None, "missing"

            user = user_result[0]
            if role == "teacher":
                teacher_result = db.execute(
                    select(self._teacher_model).where(
                        self._teacher_model.regUserID == current_user_id
                    )
                ).fetchone()
                if (
                    not teacher_result
                    or user.state != teacher_result[0].state
                    or user.county != teacher_result[0].county
                    or user.district != teacher_result[0].district
                ):
                    db.rollback()
                    return None, "forbidden"

            db.execute(
                insert(self._registered_user_model).values(
                    email=user.email,
                    password=user.password,
                    role=user.role,
                    phone_number=user.phone_number,
                    createCount=0,
                )
            )
            db.execute(
                delete(self._pending_user_model).where(
                    cast(self._pending_user_model.email, String)
                    == cast(user_email, String)
                )
            )
            db.commit()
            return user.email, None
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_pending_flag(
        self,
        user_email,
        *,
        flag_name,
        flag_value,
        role,
        current_user_id,
    ):
        db = self._session_factory()
        try:
            pending_result = db.execute(
                select(self._pending_user_model).where(
                    cast(self._pending_user_model.email, String)
                    == cast(user_email, String)
                )
            ).fetchone()
            pending_user = pending_result[0] if pending_result else None

            if role == "teacher":
                teacher_result = db.execute(
                    select(self._teacher_model).where(
                        self._teacher_model.regUserID == current_user_id
                    )
                ).fetchone()
                if (
                    not pending_user
                    or not teacher_result
                    or pending_user.state != teacher_result[0].state
                    or pending_user.county != teacher_result[0].county
                    or pending_user.district != teacher_result[0].district
                ):
                    db.rollback()
                    return False

            if pending_user:
                db.execute(
                    update(self._pending_user_model)
                    .where(
                        cast(self._pending_user_model.email, String)
                        == cast(user_email, String)
                    )
                    .values(**{flag_name: flag_value})
                )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_teacher_by_user_id(self, user_id):
        db = self._session_factory()
        try:
            result = db.execute(
                select(self._teacher_model).where(
                    self._teacher_model.regUserID == user_id
                )
            ).fetchone()
            return result[0] if result else None
        finally:
            db.close()

    def get_pending_users(self, *, scope=None):
        db = self._session_factory()
        try:
            query = select(self._pending_user_model)
            if scope:
                query = query.where(
                    cast(self._pending_user_model.state, String) == scope["state"],
                    cast(self._pending_user_model.county, String) == scope["county"],
                    cast(self._pending_user_model.district, String)
                    == scope["district"],
                )
            return [row[0] for row in db.execute(query).fetchall()]
        finally:
            db.close()

    def get_teacher_report_rows(self, *, state, county=None, district=None, school=None):
        db = self._session_factory()
        try:
            query = select(
                self._teacher_model.name,
                self._teacher_model.school,
                self._teacher_model.regUserID,
            ).where(cast(self._teacher_model.state, String) == state)
            if county:
                query = query.where(
                    cast(self._teacher_model.county, String) == county
                )
            if district:
                query = query.where(
                    cast(self._teacher_model.district, String) == district
                )
            if school:
                query = query.where(
                    cast(self._teacher_model.school, String) == school
                )

            teachers = db.execute(query).fetchall()
            if not teachers:
                return None
            user_ids = [teacher.regUserID for teacher in teachers]
            users = db.execute(
                select(
                    self._registered_user_model.id,
                    self._registered_user_model.email,
                    self._registered_user_model.phone_number,
                ).where(self._registered_user_model.id.in_(user_ids))
            ).fetchall()
            user_dict = {
                user.id: {"email": user.email, "phone": user.phone_number}
                for user in users
            }
            return [
                (
                    teacher.name,
                    teacher.school,
                    user_dict.get(teacher.regUserID, {}).get("email", "N/A"),
                    user_dict.get(teacher.regUserID, {}).get("phone", "N/A"),
                )
                for teacher in teachers
            ]
        finally:
            db.close()
