import datetime
import secrets
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from passlib.hash import sha256_crypt
from sqlalchemy import String, cast, insert, select, update

from backend.repositories.profile import ProfileRepository
from backend.core.auth import establish_user_session
from backend.services.profile_mutations import (
    IMAGE_TOO_LARGE_MESSAGE,
    INVALID_URL_ID_MESSAGE,
    INVALID_IMAGE_MESSAGE,
    INVALID_WISHLIST_URL_MESSAGE,
    InvalidWishlistUrl,
    InvalidTeacherImage,
    InvalidTeacherUrlId,
    ProfileMutationService,
    TeacherImageTooLarge,
    TeacherUrlIdConflict,
)
from backend.core.policies import (
    require_authenticated_user,
    require_profile_owner,
    require_teacher_or_admin,
)
from backend.services.profile_auth import ProfileAuthService
from backend.services.profile_password import ProfilePasswordService
from backend.services.profile_password import InvalidResetToken, PasswordMismatch
from backend.services.profile_reads import ProfileReadService


def create_profile_router(
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
    router = APIRouter()
    profile_repository = ProfileRepository(
        session_factory=session_factory,
        teacher_model=teacher_model,
        registered_user_model=registered_user_model,
        pending_user_model=pending_user_model,
        reset_token_model=reset_token_model,
        school_model=school_model,
    )
    profile_auth_service = ProfileAuthService(profile_repository)
    profile_password_service = ProfilePasswordService(profile_repository)
    profile_read_service = ProfileReadService(profile_repository)
    profile_mutation_service = ProfileMutationService(profile_repository)

    @router.post("/profile/register/")
    @limiter.limit("5/minute")
    async def register_user(
        request: Request,
        name: str = Form(...),
        email: str = Form(...),
        phone_number: str = Form(...),
        password: str = Form(...),
        confirm_password: str = Form(...),
        state: str = Form(...),
        county: str = Form(...),
        district: str = Form(...),
        school: str = Form(...),
        recaptcha_response: str = Form(...),
    ):
        if not verify_recaptcha(recaptcha_response):
            raise HTTPException(
                status_code=400,
                detail="reCAPTCHA verification failed. Please try again.",
            )

        try:
            message, send_email = profile_auth_service.register_user(
                name=name,
                email=email,
                phone_number=phone_number,
                password=password,
                confirm_password=confirm_password,
                state=state,
                county=county,
                district=district,
                school=school,
            )
            if send_email:
                if not send_registration_email(email):
                    raise HTTPException(
                        status_code=502,
                        detail="Registration email provider is temporarily unavailable.",
                    )
            return {"message": message}
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Registration error: {str(exc)}")
            return {
                "message": "Registration unsuccessful. Please try again later."
            }
    @router.post("/profile/login/")
    @limiter.limit("5/minute")
    async def login_user(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
    ):
        try:
            user = profile_auth_service.authenticate_user(email, password)
            if user:
                establish_user_session(request, user)
                return JSONResponse(
                    content={
                        "message": f"Login successful as {user.role}",
                        "createCount": user.createCount,
                        "role": user.role,
                    }
                )
            return JSONResponse(content={"message": "Invalid login credentials."})
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/logout/")
    async def logout_user(request: Request):
        if "user_id" in request.session:
            del request.session["user_id"]
            del request.session["user_role"]
            del request.session["user_email"]
        if "application/json" in request.headers.get("accept", ""):
            return {"message": "Logged out successfully."}
        return RedirectResponse(url="/", status_code=303)

    @router.post("/profile/create_teacher_profile/")
    async def create_teacher_profile(
        request: Request,
        name: str = Form(...),
        state: str = Form(...),
        county: str = Form(...),
        district: str = Form(...),
        school: str = Form(...),
        aboutMe: str = Form(...),
        wishlist: str = Form(...),
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        user_id = require_authenticated_user(
            user_id,
            detail="You must be logged in to create a teacher profile.",
        )
        require_teacher_or_admin(role, detail="Permission denied.")
        require_profile_owner(user_id, detail="Permission denied.")
        try:
            created = profile_mutation_service.create_teacher_profile(
                user_id,
                role,
                get_current_email(request),
                name=name,
                state=state,
                county=county,
                district=district,
                school=school,
                about_me=aboutMe,
                wishlist=wishlist,
            )
            if not created:
                return {
                    "message": (
                        "Unable to create new profile. Profile already created."
                    )
                }
            return {"message": "Teacher created successfully", "role": role}
        except InvalidWishlistUrl:
            raise HTTPException(status_code=400, detail=INVALID_WISHLIST_URL_MESSAGE)
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.get("/api/profile/")
    async def get_user_profile(
        email: str = Depends(get_current_email),
        role: str = Depends(get_current_role),
        user_id: str = Depends(get_current_id),
    ):
        if email:
            return JSONResponse(
                content={
                    "user_id": user_id,
                    "user_role": role,
                    "user_email": email,
                }
            )
        raise HTTPException(status_code=404, detail="No user logged in.")

    @router.get("/api/current_teacher/", response_model=profile_response_model)
    async def get_current_teacher(
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Permission denied.")
        require_profile_owner(user_id, detail="Permission denied.")
        teacher = profile_read_service.get_current_teacher(user_id)
        if teacher is None:
            raise HTTPException(status_code=404, detail="Teacher not found")
        return teacher

    @router.get("/api/get_teacher_info/")
    async def get_teacher_info(request: Request):
        try:
            teacher_info = profile_read_service.get_teacher_info(
                {
                    field: get_index_cookie(field, request)
                    for field in ("state", "county", "district", "school", "teacher")
                }
            )
            if teacher_info is None:
                raise HTTPException(status_code=404, detail="Teacher not found")
            return teacher_info
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/update_info/")
    async def update_info(
        request: Request,
        aboutMe: str = Form(...),
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Permission denied.")
        require_profile_owner(user_id, detail="Permission denied.")
        try:
            profile_mutation_service.update_teacher_about_me(user_id, aboutMe)
            return {"message": "Info updated."}
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/update_teacher_school/")
    async def update_teacher_school(
        request: Request,
        state: str = Form(...),
        county: str = Form(...),
        district: str = Form(...),
        school: str = Form(...),
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(
            role,
            detail="Permission denied. Not logged in.",
        )
        require_profile_owner(user_id, detail="Permission denied. Not logged in.")
        try:
            profile_mutation_service.update_teacher_school(
                user_id,
                state=state,
                county=county,
                district=district,
                school=school,
            )
            return JSONResponse(
                content={
                    "message": "School information updated successfully."
                }
            )
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/update_teacher_name/")
    async def update_teacher_name(
        request: Request,
        teacher: str = Form(...),
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Permission denied.")
        require_profile_owner(user_id, detail="Permission denied.")
        try:
            profile_mutation_service.update_teacher_name(user_id, teacher)
            return {"message": "Name updated."}
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/update_wishlist/")
    async def update_wishlist(
        request: Request,
        wishlist: str = Form(...),
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Permission denied.")
        require_profile_owner(user_id, detail="Permission denied.")
        try:
            profile_mutation_service.update_teacher_wishlist(user_id, wishlist)
            return {"message": "Wishlist updated."}
        except InvalidWishlistUrl:
            raise HTTPException(status_code=400, detail=INVALID_WISHLIST_URL_MESSAGE)
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/update_url_id/")
    async def update_url_id(
        request: Request,
        url_id: str = Form(...),
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Permission denied.")
        require_profile_owner(user_id, detail="Permission denied.")
        try:
            profile_mutation_service.update_teacher_url_id(user_id, url_id)
            return {"message": "URL ID updated successfully."}
        except InvalidTeacherUrlId:
            raise HTTPException(status_code=400, detail=INVALID_URL_ID_MESSAGE)
        except TeacherUrlIdConflict:
            raise HTTPException(status_code=409, detail="URL ID already in use.")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/update_teacher_image/")
    async def edit_teacher_image(
        request: Request,
        role: str = Depends(get_current_role),
        image: UploadFile = Form(...),
        user_id: int = Depends(get_current_id),
    ):
        require_teacher_or_admin(role, detail="Permission denied.")
        require_profile_owner(user_id, detail="Permission denied.")
        try:
            image_bytes = await image.read()
            updated = profile_mutation_service.update_teacher_image(
                user_id,
                role,
                image_bytes,
                image_size=image.size,
                max_file_size=max_file_size,
                detect_file_type=detect_file_type,
            )
            if updated:
                return {"message": "Information updated."}
            return {"message": "Permission denied."}
        except TeacherImageTooLarge:
            raise HTTPException(status_code=400, detail=IMAGE_TOO_LARGE_MESSAGE)
        except InvalidTeacherImage:
            raise HTTPException(status_code=400, detail=INVALID_IMAGE_MESSAGE)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.get("/profile/myinfo/")
    async def get_myinfo(
        request: Request,
        user_id: int = Depends(get_current_id),
    ):
        user_id = require_authenticated_user(user_id)
        require_profile_owner(user_id)
        try:
            teacher_data = profile_read_service.get_myinfo(user_id)
            if teacher_data:
                teacher, session_data = teacher_data
                set_teacher_session(request, teacher)
                return session_data
            return {
                "message": "Your account does not have a database listing"
            }
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/update_password/")
    async def update_password(
        request: Request,
        user_id: int = Depends(get_current_id),
        old_password: str = Form(...),
        new_password: str = Form(...),
        new_password_confirmed: str = Form(...),
    ):
        user_id = require_authenticated_user(user_id)
        require_profile_owner(user_id)
        try:
            return profile_password_service.update_password(
                user_id,
                old_password,
                new_password,
                new_password_confirmed,
            )
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.get("/api/check_access_teacher/")
    async def check_access_teacher(
        request: Request,
        user_id: int = Depends(get_current_id),
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="No access")
        try:
            context = {
                field: get_index_cookie(field, request)
                for field in ("state", "county", "district", "school", "teacher")
            }
            if profile_read_service.has_teacher_access(context, user_id, role):
                return {"status": "success", "message": "Access granted"}
            raise HTTPException(status_code=403, detail="No access")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/forgot_password/")
    @limiter.limit("5/minute")
    async def forgot_password(
        request: Request,
        email: str = Form(...),
    ):
        try:
            token = secrets.token_urlsafe(32)
            expires_at = (
                datetime.datetime.utcnow()
                + datetime.timedelta(hours=1)
            )
            user_exists = profile_password_service.create_reset_token(
                email,
                token=token,
                expires_at=expires_at,
            )
            if user_exists:
                reset_link = (
                    "https://www.helpteachers.net/reset-password"
                    f"?token={token}"
                )
                template_data = {
                    "recipient_name": email,
                    "message_body": (
                        "We received a request to reset your password. "
                        "Click the link below to reset it (expires in 1 hour):"
                        f"\n\n{reset_link}\n\n"
                        "If you did not request this, you can ignore this email."
                    ),
                }
                sent = send_email(
                    email,
                    "Password Reset Request",
                    render_email_template(
                        "static/email_template.html",
                        template_data,
                    ),
                    (
                        f"Dear {email},\n\nReset your password here: "
                        f"{reset_link}\n\nExpires in 1 hour."
                    ),
                )
                if not sent:
                    raise HTTPException(
                        status_code=502,
                        detail="Password reset email provider is temporarily unavailable.",
                    )
            else:
                time.sleep(1)
            return JSONResponse(
                content={
                    "message": (
                        "If an account exists, a reset link will be sent "
                        "to your email."
                    )
                }
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/reset_password/")
    async def reset_password(
        token: str = Form(...),
        new_password: str = Form(...),
        confirm_password: str = Form(...),
    ):
        try:
            profile_password_service.reset_password(
                token,
                new_password,
                confirm_password,
                now=datetime.datetime.utcnow(),
            )
            return JSONResponse(
                content={
                    "message": (
                        "Password reset successfully. You can now log in."
                    )
                }
            )
        except PasswordMismatch as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except InvalidResetToken as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.get("/api/teacher_url/")
    async def get_teacher_url(request: Request):
        try:
            url = profile_read_service.get_teacher_url(
                {
                    field: get_index_cookie(field, request)
                    for field in ("state", "county", "district", "school", "teacher")
                }
            )
            if url is None:
                raise HTTPException(
                    status_code=404,
                    detail="No matching teacher found",
                )
            return {"url": url}
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    return router
