import base64


class ProfileReadService:
    """Read-only identity/profile use cases."""

    def __init__(self, repository):
        self._repository = repository

    def get_teacher_info(self, context):
        teacher = self._repository.get_teacher_by_context(context)
        if teacher is None:
            return None

        image_data = (
            base64.b64encode(teacher.image_data).decode("utf-8")
            if teacher.image_data
            else None
        )
        return {
            "state": teacher.state,
            "county": teacher.county,
            "district": teacher.district,
            "school": teacher.school,
            "name": teacher.name,
            "wishlist_url": teacher.wishlist_url,
            "about_me": teacher.about_me,
            "image_data": image_data,
        }

    def get_myinfo(self, user_id):
        teacher = self._repository.get_teacher_by_user_id(user_id)
        if teacher is None:
            return None
        return teacher, {
            "state": teacher.state,
            "county": teacher.county,
            "district": teacher.district,
            "school": teacher.school,
            "teacher": teacher.name,
        }

    def get_current_teacher(self, user_id):
        teacher = self._repository.get_teacher_by_user_id(user_id)
        if teacher is None:
            return None
        image_data = (
            base64.b64encode(teacher.image_data).decode("utf-8")
            if teacher.image_data
            else None
        )
        return {
            "name": teacher.name,
            "url_id": teacher.url_id,
            "state": teacher.state,
            "county": teacher.county,
            "district": teacher.district,
            "school": teacher.school,
            "wishlist_url": teacher.wishlist_url,
            "about_me": teacher.about_me,
            "image_data": image_data,
        }

    def has_teacher_access(self, context, user_id, role):
        if role != "teacher":
            return False
        teacher = self._repository.get_teacher_by_context(context)
        return teacher is not None and teacher.regUserID == user_id

    def get_teacher_url(self, context):
        teacher = self._repository.get_teacher_by_context(context)
        if teacher is None:
            return None
        return "/teacher/" + teacher.url_id
