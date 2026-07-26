import logging
import os

from backend.api.register import (
    register_admin_routes,
    register_compatibility_routes,
    register_forum_routes,
    register_job_routes,
    register_profile_routes,
    register_redirect_routes,
    register_site_routes,
    register_teacher_routes,
)
from backend.core.auth import (
    get_current_email,
    get_current_id,
    get_current_role,
    get_index_cookie,
    set_teacher_session,
)
from backend.core.serialization import model_to_dict
from backend.db.models import (
    ForumComment,
    ForumPost,
    NewUsers,
    PasswordResetToken,
    PostVote,
    RegisteredUsers,
    School,
    Spotlight,
    TeacherList,
)
from backend.integrations.file_detection import detect_file_type
from backend.jobs.runner import run_one_shot_job
from backend.schemas.forum import PostUpdate, VoteInput
from backend.schemas.teachers import TeacherDirectoryResponse, TeacherProfileResponse


ALLOWED_TAGS = ["b", "i", "em", "strong", "a", "p", "br"]
ALLOWED_ATTRS = {"a": ["href"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]
MAX_FILE_SIZE = 1 * 1024 * 1024


def register_application_routes(
    application,
    *,
    database_resources,
    legacy_jobs,
    limiter,
    static_dir="static",
):
    """Build the route graph from runtime resources at the composition root."""
    try:
        import bleach

        clean_html = bleach.clean
    except ImportError:
        import html

        def clean_html(value, tags=None, attributes=None, strip=False, protocols=None):
            return html.escape(value or "")

    logger = logging.getLogger(__name__)
    register_redirect_routes(application)
    register_teacher_routes(
        application,
        session_factory=database_resources.session_factory,
        school_model=School,
        teacher_model=TeacherList,
        directory_response_model=TeacherDirectoryResponse,
        profile_response_model=TeacherProfileResponse,
    )
    register_forum_routes(
        application,
        session_factory=database_resources.session_factory,
        post_model=ForumPost,
        comment_model=ForumComment,
        vote_model=PostVote,
        vote_input_model=VoteInput,
        post_update_model=PostUpdate,
        get_current_id=get_current_id,
        get_current_role=get_current_role,
        limiter=limiter,
        clean_html=clean_html,
        allowed_tags=ALLOWED_TAGS,
        allowed_attrs=ALLOWED_ATTRS,
        allowed_protocols=ALLOWED_PROTOCOLS,
        model_to_dict=model_to_dict,
    )
    register_profile_routes(
        application,
        session_factory=database_resources.session_factory,
        pending_user_model=NewUsers,
        registered_user_model=RegisteredUsers,
        teacher_model=TeacherList,
        school_model=School,
        reset_token_model=PasswordResetToken,
        get_current_id=get_current_id,
        get_current_role=get_current_role,
        get_current_email=get_current_email,
        get_index_cookie=get_index_cookie,
        set_teacher_session=set_teacher_session,
        verify_recaptcha=legacy_jobs.verify_recaptcha,
        send_registration_email=legacy_jobs.send_registration_email,
        render_email_template=legacy_jobs.render_email_template,
        send_email=legacy_jobs.send_email,
        limiter=limiter,
        detect_file_type=detect_file_type,
        max_file_size=MAX_FILE_SIZE,
        profile_response_model=TeacherProfileResponse,
        logger=logger,
    )
    register_admin_routes(
        application,
        session_factory=database_resources.session_factory,
        pending_user_model=NewUsers,
        registered_user_model=RegisteredUsers,
        teacher_model=TeacherList,
        get_current_id=get_current_id,
        get_current_role=get_current_role,
        set_teacher_session=set_teacher_session,
        get_index_cookie=get_index_cookie,
        send_validation_email=legacy_jobs.send_validation_email,
        send_attachment=legacy_jobs.send_attachment,
        logger=logger,
        get_admin_secret=os.getenv,
    )
    register_compatibility_routes(
        application,
        fetch_random_teacher=legacy_jobs.fetch_random_teacher,
        set_teacher_session=set_teacher_session,
        verify_recaptcha=legacy_jobs.verify_recaptcha,
        render_email_template=legacy_jobs.render_email_template,
        send_email=legacy_jobs.send_email,
        clean_html=clean_html,
        logger=logger,
    )
    register_job_routes(
        application,
        job_handlers={
            "daily": legacy_jobs.daily_job,
            "tuesday": legacy_jobs.tuesday_job,
            "wednesday": legacy_jobs.wednesday_job,
            "thursday": legacy_jobs.thursday_job,
        },
        verify_cronjob_request=legacy_jobs.verify_cronjob_request,
        run_one_shot_job=run_one_shot_job,
    )
    register_site_routes(
        application,
        session_factory=database_resources.session_factory,
        school_model=School,
        teacher_model=TeacherList,
        spotlight_model=Spotlight,
        set_teacher_session=set_teacher_session,
        logger=logger,
        static_dir=static_dir,
    )
