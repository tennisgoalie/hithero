import os
import tempfile

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import String, cast, delete, insert, select, update

from backend.repositories.admin import AdminRepository
from backend.core.errors import ForbiddenError
from backend.core.policies import require_admin, require_teacher_or_admin
from backend.services.admin import (
    AdminService,
    PendingUserNotFound,
    UserAccountNotFound,
    ValidationScopeForbidden,
)


def create_admin_router(
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
    router = APIRouter()
    account_repository = AdminRepository(
        session_factory=session_factory,
        registered_user_model=registered_user_model,
        teacher_model=teacher_model,
        pending_user_model=pending_user_model,
    )
    admin_service = AdminService(account_repository)

    def serialize_pending_users(rows):
        return [
            {
                "name": row.name,
                "email": row.email,
                "state": row.state,
                "district": row.district,
                "school": row.school,
                "phone_number": row.phone_number,
                "report": row.report,
                "emailed": row.emailed,
            }
            for row in rows
        ]

    @router.post("/validation/validate_user/{user_email}")
    async def move_user(
        user_email: str,
        request: Request,
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Access denied.")

        try:
            validated_email = admin_service.validate_pending_user(
                user_email,
                role=role,
                current_user_id=get_current_id(request),
            )
            if not send_validation_email(validated_email):
                raise HTTPException(
                    status_code=502,
                    detail="Validation email provider is temporarily unavailable.",
                )
            return {"message": "User validated."}
        except PendingUserNotFound:
            raise HTTPException(status_code=404, detail="User not found in new_users")
        except (ValidationScopeForbidden, ForbiddenError):
            raise HTTPException(
                status_code=403,
                detail="You can only validate teachers in your own district.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.get("/api/validation_list/")
    async def validation_page(
        request: Request,
        role: str = Depends(get_current_role),
        user_id: int = Depends(get_current_id),
    ):
        require_teacher_or_admin(
            role,
            detail="You don't have permission to access this page.",
        )
        try:
            teacher, new_users = admin_service.get_validation_users(
                role=role,
                user_id=user_id,
            )
            if teacher is not None:
                set_teacher_session(request, teacher)
            return {
                "new_users": serialize_pending_users(new_users),
                "role": role,
            }
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/validation/delete_user/{user_email}")
    async def delete_user(
        user_email: str,
        role: str = Depends(get_current_role),
    ):
        require_admin(role, detail="No permission to to action.")

        try:
            admin_service.delete_pending_user(user_email)
            return {"message": "User deleted successfully."}
        except PendingUserNotFound:
            raise HTTPException(status_code=404, detail="User not found in new_users")
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/validation/report_user/{user_email}")
    async def report_user(
        user_email: str,
        request: Request,
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Access denied.")

        try:
            admin_service.report_pending_user(
                user_email,
                role=role,
                current_user_id=get_current_id(request),
            )
            return {"message": "User reported."}
        except (ValidationScopeForbidden, ForbiddenError):
            raise HTTPException(
                status_code=403,
                detail="You can only report teachers in your own district.",
            )
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/validation/emailed_user/{user_email}")
    async def emailed_user(
        user_email: str,
        request: Request,
        role: str = Depends(get_current_role),
    ):
        require_teacher_or_admin(role, detail="Access denied.")

        try:
            admin_service.mark_pending_user_emailed(
                user_email,
                role=role,
                current_user_id=get_current_id(request),
            )
            return {"message": "User emailed."}
        except (ValidationScopeForbidden, ForbiddenError):
            raise HTTPException(
                status_code=403,
                detail="You can only mark teachers in your own district as emailed.",
            )
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/admin/generate_teacher_report/")
    async def generate_teacher_report(
        state: str = Form(...),
        county: str = Form(None),
        district: str = Form(None),
        school: str = Form(None),
        role: str = Depends(get_current_role),
    ):
        require_admin(
            role,
            detail="Access denied: Only administrators can generate reports.",
        )

        try:
            report = admin_service.build_teacher_report(
                state=state,
                county=county,
                district=district,
                school=school,
            )
            if report is None:
                raise HTTPException(
                    status_code=404,
                    detail="No teachers found with the specified criteria.",
                )

            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="teacher-report-",
                suffix=".txt",
                delete=False,
            ) as temp_file:
                temp_file.write(report)
                file_path = temp_file.name

            try:
                sent = send_attachment(
                    recipient_email="homeroom.heroes.main@gmail.com",
                    subject="Teacher Report",
                    message="Please find the attached teacher report.",
                    attachment_path=file_path,
                )
                if not sent:
                    raise HTTPException(
                        status_code=502,
                        detail="Report email provider is temporarily unavailable.",
                    )
            finally:
                try:
                    os.remove(file_path)
                except OSError:
                    logger.error("Failed to delete temporary report file.")
            return {"message": "Teacher report saved and sent via email."}
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Report generation error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/profile/delete/")
    async def admin_delete_user_account(
        target_email: str = Form(...),
        admin_secret_input: str = Form(...),
        current_role: str = Depends(get_current_role),
    ):
        require_admin(
            current_role,
            detail="Forbidden. Only administrators can delete user accounts.",
        )
        admin_secret = get_admin_secret("admin_secret")
        if not admin_secret or admin_secret_input != admin_secret:
            raise HTTPException(
                status_code=403,
                detail="Invalid administrator secret provided.",
            )

        try:
            message = admin_service.delete_user_account(target_email)
            return {
                "message": message
            }
        except UserAccountNotFound:
            raise HTTPException(
                status_code=404,
                detail=f"User account linked to '{target_email}' not found.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Internal Server Error: {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    return router
