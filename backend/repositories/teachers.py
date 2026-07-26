from sqlalchemy import String, cast, func, select


class TeacherDirectoryRepository:
    """Read-only persistence operations for public teacher-directory data."""

    def __init__(self, *, session_factory, school_model, teacher_model):
        self._session_factory = session_factory
        self._school_model = school_model
        self._teacher_model = teacher_model

    def _public_teacher_conditions(self, *, state=None, county=None, district=None, school=None):
        conditions = [
            self._teacher_model.name.is_not(None),
            self._teacher_model.url_id.is_not(None),
            cast(self._teacher_model.url_id, String) != "",
        ]
        if state:
            conditions.append(cast(self._teacher_model.state, String) == state)
        if county:
            conditions.append(cast(self._teacher_model.county, String) == county)
        if district:
            conditions.append(cast(self._teacher_model.district, String) == district)
        if school:
            conditions.append(cast(self._teacher_model.school, String) == school)
        return conditions

    def count_public_teachers(self, *, state=None, county=None, district=None, school=None):
        db = self._session_factory()
        try:
            return db.execute(
                select(func.count())
                .select_from(self._teacher_model)
                .where(
                    *self._public_teacher_conditions(
                        state=state,
                        county=county,
                        district=district,
                        school=school,
                    )
                )
            ).scalar_one()
        finally:
            db.close()

    def list_public_teachers(
        self,
        *,
        state=None,
        county=None,
        district=None,
        school=None,
        offset=0,
        limit=24,
    ):
        db = self._session_factory()
        try:
            query = (
                select(self._teacher_model)
                .where(
                    *self._public_teacher_conditions(
                        state=state,
                        county=county,
                        district=district,
                        school=school,
                    )
                )
                .order_by(cast(self._teacher_model.name, String))
                .offset(offset)
                .limit(limit)
            )
            return db.execute(query).scalars().all()
        finally:
            db.close()

    def list_public_teacher_url_ids(self):
        """Return stable, shareable URL IDs for all public teacher profiles."""
        db = self._session_factory()
        try:
            url_id = cast(self._teacher_model.url_id, String)
            query = (
                select(url_id)
                .where(*self._public_teacher_conditions())
                .distinct()
                .order_by(url_id)
            )
            return db.execute(query).scalars().all()
        finally:
            db.close()

    def directory_filters(self, *, state=None, county=None, district=None):
        db = self._session_factory()
        try:
            def values(column, *conditions):
                query = select(cast(column, String)).distinct()
                for condition in conditions:
                    if condition is not None:
                        query = query.where(condition)
                result = db.execute(query).scalars().all()
                return sorted({value for value in result if value})

            county_conditions = [
                cast(self._teacher_model.state, String) == state
            ] if state else []
            district_conditions = county_conditions + (
                [cast(self._teacher_model.county, String) == county]
                if county else []
            )
            school_conditions = district_conditions + (
                [cast(self._teacher_model.district, String) == district]
                if district else []
            )

            return {
                "states": values(self._teacher_model.state),
                "counties": values(self._teacher_model.county, *county_conditions),
                "districts": values(
                    self._teacher_model.district, *district_conditions
                ),
                "schools": values(self._teacher_model.school, *school_conditions),
            }
        finally:
            db.close()

    def get_public_teacher(self, url_id: str):
        db = self._session_factory()
        try:
            return db.execute(
                select(self._teacher_model).where(
                    *self._public_teacher_conditions(),
                    cast(self._teacher_model.url_id, String) == url_id,
                )
            ).scalar_one_or_none()
        finally:
            db.close()

    def get_school_states(self):
        db = self._session_factory()
        try:
            values = db.query(self._school_model.state).distinct().all()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def get_school_counties(self, state: str):
        db = self._session_factory()
        try:
            values = db.execute(
                select(self._school_model.county)
                .distinct()
                .where(self._school_model.state == state)
            ).fetchall()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def get_school_districts(self, state: str, county: str):
        db = self._session_factory()
        try:
            values = db.execute(
                select(self._school_model.district)
                .distinct()
                .where(
                    (self._school_model.state == state)
                    & (self._school_model.county == county)
                )
            ).fetchall()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def get_school_names(self, state: str, county: str, district: str):
        db = self._session_factory()
        try:
            values = db.execute(
                select(self._school_model.school_name)
                .distinct()
                .where(
                    (self._school_model.state == state)
                    & (self._school_model.county == county)
                    & (self._school_model.district == district)
                )
            ).fetchall()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def get_index_states(self):
        db = self._session_factory()
        try:
            values = db.query(cast(self._teacher_model.state, String)).distinct().all()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def get_index_counties(self, state: str):
        db = self._session_factory()
        try:
            values = db.execute(
                select(cast(self._teacher_model.county, String))
                .distinct()
                .where(cast(self._teacher_model.state, String) == state)
            ).fetchall()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def get_index_districts(self, state: str, county: str):
        db = self._session_factory()
        try:
            values = db.execute(
                select(cast(self._teacher_model.district, String))
                .distinct()
                .where(
                    (cast(self._teacher_model.state, String) == state)
                    & (cast(self._teacher_model.county, String) == county)
                )
            ).fetchall()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def get_index_schools(self, state: str, county: str, district: str):
        db = self._session_factory()
        try:
            values = db.execute(
                select(cast(self._teacher_model.school, String))
                .distinct()
                .where(
                    (cast(self._teacher_model.state, String) == state)
                    & (cast(self._teacher_model.county, String) == county)
                    & (cast(self._teacher_model.district, String) == district)
                )
            ).fetchall()
            return sorted([value[0] for value in values])
        finally:
            db.close()

    def find_index_teachers(self, *, state, county=None, district=None, school=None):
        db = self._session_factory()
        try:
            query = select(self._teacher_model.name, self._teacher_model.url_id).where(
                *self._public_teacher_conditions(
                    state=state,
                    county=county,
                    district=district,
                    school=school,
                )
            )
            return db.execute(query).fetchall()
        finally:
            db.close()
