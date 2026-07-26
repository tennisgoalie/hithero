from contextlib import contextmanager

from sqlalchemy import String, cast, func, insert, select, update


class ProfileRepository:
    """Persistence operations for teacher identity/profile lookups."""

    def __init__(
        self,
        *,
        session_factory,
        teacher_model,
        registered_user_model=None,
        pending_user_model=None,
        reset_token_model=None,
        school_model=None,
    ):
        self._session_factory = session_factory
        self._teacher_model = teacher_model
        self._registered_user_model = registered_user_model
        self._pending_user_model = pending_user_model
        self._reset_token_model = reset_token_model
        self._school_model = school_model

    @contextmanager
    def transaction(self):
        """Yield one session for a multi-step profile use case."""
        db = self._session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _context_conditions(self, context):
        model_fields = {
            "state": "state",
            "county": "county",
            "district": "district",
            "school": "school",
            "teacher": "name",
        }
        return [
            cast(getattr(self._teacher_model, model_field), String)
            == context.get(context_field)
            for context_field, model_field in model_fields.items()
        ]

    def get_teacher_by_context(self, context):
        db = self._session_factory()
        try:
            result = db.execute(
                select(self._teacher_model).where(*self._context_conditions(context))
            ).fetchone()
            return result[0] if result else None
        finally:
            db.close()

    def get_teacher_by_user_id(self, user_id, *, db=None):
        owns_session = db is None
        if owns_session:
            db = self._session_factory()
        try:
            result = db.execute(
                select(self._teacher_model).where(
                    self._teacher_model.regUserID == user_id
                )
            ).fetchone()
            return result[0] if result else None
        finally:
            if owns_session:
                db.close()

    def get_registered_user_by_email(self, email):
        db = self._session_factory()
        try:
            result = db.execute(
                select(self._registered_user_model).where(
                    cast(self._registered_user_model.email, String)
                    == cast(email, String)
                )
            ).fetchone()
            return result[0] if result else None
        finally:
            db.close()

    def get_pending_user_by_email(self, email):
        db = self._session_factory()
        try:
            result = db.execute(
                select(self._pending_user_model).where(
                    cast(self._pending_user_model.email, String)
                    == cast(email, String)
                )
            ).fetchone()
            return result[0] if result else None
        finally:
            db.close()

    def get_password_hash(self, user_id):
        db = self._session_factory()
        try:
            return db.execute(
                select(self._registered_user_model.password).where(
                    self._registered_user_model.id == user_id
                )
            ).scalar()
        finally:
            db.close()

    def update_password(self, user_id, password_hash):
        db = self._session_factory()
        try:
            db.execute(
                update(self._registered_user_model)
                .where(self._registered_user_model.id == user_id)
                .values(password=password_hash)
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_reset_token(self, *, email, token, expires_at):
        db = self._session_factory()
        try:
            db.add(
                self._reset_token_model(
                    email=email,
                    token=token,
                    expires_at=expires_at,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_valid_reset_token(self, token, *, now):
        db = self._session_factory()
        try:
            result = db.execute(
                select(self._reset_token_model).where(
                    self._reset_token_model.token == token,
                    self._reset_token_model.used == 0,
                    self._reset_token_model.expires_at > now,
                )
            ).fetchone()
            return result[0] if result else None
        finally:
            db.close()

    def consume_reset_token(self, token, email, password_hash):
        db = self._session_factory()
        try:
            db.execute(
                update(self._registered_user_model)
                .where(
                    cast(self._registered_user_model.email, String)
                    == cast(email, String)
                )
                .values(password=password_hash)
            )
            db.execute(
                update(self._reset_token_model)
                .where(self._reset_token_model.token == token)
                .values(used=1)
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_pending_user(
        self,
        *,
        name,
        email,
        state,
        county,
        district,
        school,
        phone_number,
        password,
    ):
        db = self._session_factory()
        try:
            db.add(
                self._pending_user_model(
                    name=name,
                    email=email,
                    state=state,
                    county=county,
                    district=district,
                    school=school,
                    phone_number=phone_number,
                    password=password,
                    role="teacher",
                    report=0,
                    emailed=0,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_teacher_school(self, user_id, *, state, county, district, school):
        self._update_teacher(
            user_id,
            state=state,
            county=county,
            district=district,
            school=school,
        )

    def school_exists(self, *, state, county, district, school, db=None):
        if self._school_model is None:
            return False
        owns_session = db is None
        if owns_session:
            db = self._session_factory()
        try:
            return (
                db.execute(
                    select(self._school_model.id).where(
                        cast(self._school_model.state, String) == state,
                        cast(self._school_model.county, String) == county,
                        cast(self._school_model.district, String) == district,
                        cast(self._school_model.school_name, String) == school,
                    )
                ).first()
                is not None
            )
        finally:
            if owns_session:
                db.close()

    def update_teacher_name(self, user_id, name):
        self._update_teacher(user_id, name=name)

    def update_teacher_wishlist(self, user_id, wishlist_url):
        self._update_teacher(user_id, wishlist_url=wishlist_url)

    def update_teacher_about_me(self, user_id, about_me):
        self._update_teacher(user_id, about_me=about_me)

    def get_teacher_by_url_id(self, url_id, *, db=None):
        owns_session = db is None
        if owns_session:
            db = self._session_factory()
        try:
            result = db.execute(
                select(self._teacher_model).where(
                    cast(self._teacher_model.url_id, String) == cast(url_id, String)
                )
            ).fetchone()
            return result[0] if result else None
        finally:
            if owns_session:
                db.close()

    def update_teacher_url_id(self, user_id, url_id):
        self._update_teacher(user_id, url_id=url_id)

    def update_teacher_image(self, user_id, image_bytes):
        self._update_teacher(user_id, image_data=image_bytes)

    def get_profile_create_count(self, user_id, *, db=None):
        owns_session = db is None
        if owns_session:
            db = self._session_factory()
        try:
            count = db.execute(
                select(self._registered_user_model.createCount).where(
                    self._registered_user_model.id == user_id
                )
            ).scalar()
            # Accounts approved before createCount was initialized should be
            # treated as eligible for their first profile.
            return 0 if count is None else count
        finally:
            if owns_session:
                db.close()

    def create_teacher_profile(self, user_id, *, name, state, county, district,
                               school, about_me, wishlist_url, url_id, db=None):
        owns_session = db is None
        if owns_session:
            db = self._session_factory()
        try:
            db.execute(
                insert(self._teacher_model).values(
                    name=name,
                    state=state,
                    county=county,
                    district=district,
                    school=school,
                    regUserID=user_id,
                    about_me=about_me,
                    wishlist_url=wishlist_url,
                    url_id=url_id,
                )
            )
            db.execute(
                update(self._registered_user_model)
                .where(self._registered_user_model.id == user_id)
                .values(
                    createCount=func.coalesce(
                        self._registered_user_model.createCount, 0
                    )
                    + 1
                )
            )
            if owns_session:
                db.commit()
        except Exception:
            if owns_session:
                db.rollback()
            raise
        finally:
            if owns_session:
                db.close()

    def _update_teacher(self, user_id, **values):
        db = self._session_factory()
        try:
            db.execute(
                update(self._teacher_model)
                .where(self._teacher_model.regUserID == user_id)
                .values(**values)
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
