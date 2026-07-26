from backend.routers.admin import create_admin_router
from backend.routers.compatibility import create_compatibility_router
from backend.routers.forum import create_forum_router
from backend.routers.jobs import create_jobs_router
from backend.routers.profile import create_profile_router
from backend.routers.redirects import create_redirect_router
from backend.routers.site import create_site_router
from backend.routers.teachers import create_teacher_router


def register_redirect_routes(application):
    application.include_router(create_redirect_router())


def register_site_routes(
    application,
    *,
    session_factory,
    school_model,
    teacher_model,
    spotlight_model,
    set_teacher_session,
    logger,
    static_dir="static",
):
    application.include_router(
        create_site_router(
            session_factory=session_factory,
            school_model=school_model,
            teacher_model=teacher_model,
            spotlight_model=spotlight_model,
            set_teacher_session=set_teacher_session,
            logger=logger,
            static_dir=static_dir,
        )
    )


def register_teacher_routes(
    application,
    *,
    session_factory,
    school_model,
    teacher_model,
    directory_response_model,
    profile_response_model,
):
    application.include_router(
        create_teacher_router(
            session_factory=session_factory,
            school_model=school_model,
            teacher_model=teacher_model,
            directory_response_model=directory_response_model,
            profile_response_model=profile_response_model,
        )
    )


def register_forum_routes(
    application,
    *,
    session_factory,
    post_model,
    comment_model,
    vote_model,
    vote_input_model,
    post_update_model,
    get_current_id,
    get_current_role,
    limiter,
    clean_html,
    allowed_tags,
    allowed_attrs,
    allowed_protocols,
    model_to_dict,
):
    application.include_router(
        create_forum_router(
            session_factory=session_factory,
            post_model=post_model,
            comment_model=comment_model,
            vote_model=vote_model,
            vote_input_model=vote_input_model,
            post_update_model=post_update_model,
            get_current_id=get_current_id,
            get_current_role=get_current_role,
            limiter=limiter,
            clean_html=clean_html,
            allowed_tags=allowed_tags,
            allowed_attrs=allowed_attrs,
            allowed_protocols=allowed_protocols,
            model_to_dict=model_to_dict,
        )
    )


def register_profile_routes(
    application,
    *,
    session_factory,
    pending_user_model,
    registered_user_model,
    teacher_model,
    reset_token_model,
    get_current_id,
    get_current_role,
    get_current_email,
    get_index_cookie,
    set_teacher_session,
    verify_recaptcha,
    send_registration_email,
    render_email_template,
    send_email,
    limiter,
    detect_file_type,
    max_file_size,
    school_model,
    profile_response_model,
    logger,
):
    application.include_router(
        create_profile_router(
            session_factory=session_factory,
            pending_user_model=pending_user_model,
            registered_user_model=registered_user_model,
            teacher_model=teacher_model,
            reset_token_model=reset_token_model,
            get_current_id=get_current_id,
            get_current_role=get_current_role,
            get_current_email=get_current_email,
            get_index_cookie=get_index_cookie,
            set_teacher_session=set_teacher_session,
            verify_recaptcha=verify_recaptcha,
            send_registration_email=send_registration_email,
            render_email_template=render_email_template,
            send_email=send_email,
            limiter=limiter,
            detect_file_type=detect_file_type,
            max_file_size=max_file_size,
            school_model=school_model,
            profile_response_model=profile_response_model,
            logger=logger,
        )
    )


def register_admin_routes(
    application,
    *,
    session_factory,
    pending_user_model,
    registered_user_model,
    teacher_model,
    get_current_id,
    get_current_role,
    set_teacher_session,
    get_index_cookie,
    send_validation_email,
    send_attachment,
    logger,
    get_admin_secret,
):
    application.include_router(
        create_admin_router(
            session_factory=session_factory,
            pending_user_model=pending_user_model,
            registered_user_model=registered_user_model,
            teacher_model=teacher_model,
            get_current_id=get_current_id,
            get_current_role=get_current_role,
            set_teacher_session=set_teacher_session,
            get_index_cookie=get_index_cookie,
            send_validation_email=send_validation_email,
            send_attachment=send_attachment,
            logger=logger,
            get_admin_secret=get_admin_secret,
        )
    )


def register_compatibility_routes(
    application,
    *,
    fetch_random_teacher,
    set_teacher_session,
    verify_recaptcha,
    render_email_template,
    send_email,
    clean_html,
    logger,
):
    application.include_router(
        create_compatibility_router(
            fetch_random_teacher=fetch_random_teacher,
            set_teacher_session=set_teacher_session,
            verify_recaptcha=verify_recaptcha,
            render_email_template=render_email_template,
            send_email=send_email,
            clean_html=clean_html,
            logger=logger,
        )
    )


def register_job_routes(
    application,
    *,
    job_handlers,
    verify_cronjob_request,
    run_one_shot_job,
):
    application.include_router(
        create_jobs_router(
            job_handlers=job_handlers,
            verify_cronjob_request=verify_cronjob_request,
            run_one_shot_job=run_one_shot_job,
        )
    )
