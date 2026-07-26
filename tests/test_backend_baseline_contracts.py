from fastapi.routing import APIRoute


# B0 contract snapshot. Any route move, removal, method change, or accidental
# new endpoint must update this snapshot and the accompanying inventory in the
# same reviewed change.
EXPECTED_BACKEND_ROUTES = {
    ("POST", "/internal/run-wednesday-job"),
    ("POST", "/internal/run-tuesday-job"),
    ("POST", "/internal/run-thursday-job"),
    ("POST", "/internal/run-daily-job"),
    ("GET", "/api/random_teacher/"),
    ("POST", "/api/contact_us/"),
    ("GET", "/spotlight/{token}"),
    ("GET", "/teacher/{url_id}"),
    ("GET", "/promo/get_promo_info/"),
    ("GET", "/api/get_states/"),
    ("GET", "/api/get_counties/{state}"),
    ("GET", "/api/get_districts/{state}/{county}"),
    ("GET", "/api/get_schools/{state}/{county}/{district}"),
    ("GET", "/api/index_states/"),
    ("GET", "/api/index_counties/{state}"),
    ("GET", "/api/index_districts/{state}/{county}"),
    ("GET", "/api/index_schools/{state}/{county}/{district}"),
    ("GET", "/api/teachers/"),
    ("GET", "/api/teacher/{url_id}/"),
    ("POST", "/api/index_teachers/"),
    ("POST", "/forum/create_post"),
    ("GET", "/forum/get_posts"),
    ("GET", "/forum/get_post"),
    ("POST", "/forum/posts/{post_id}/vote"),
    ("POST", "/forum/posts/{post_id}/comment"),
    ("GET", "/forum/comments/{post_id}/"),
    ("DELETE", "/forum/post/{post_id}/delete"),
    ("DELETE", "/forum/comment/{comment_id}/delete"),
    ("PATCH", "/forum/post/{post_id}/update"),
    ("PATCH", "/forum/comment/{comment_id}/update"),
    ("POST", "/profile/register/"),
    ("POST", "/profile/login/"),
    ("POST", "/profile/logout/"),
    ("POST", "/profile/create_teacher_profile/"),
    ("GET", "/api/profile/"),
    ("GET", "/api/current_teacher/"),
    ("GET", "/api/get_teacher_info/"),
    ("POST", "/profile/update_info/"),
    ("POST", "/profile/update_teacher_school/"),
    ("POST", "/profile/update_teacher_name/"),
    ("POST", "/profile/update_wishlist/"),
    ("POST", "/profile/update_url_id/"),
    ("POST", "/profile/update_teacher_image/"),
    ("GET", "/profile/myinfo/"),
    ("POST", "/profile/update_password/"),
    ("GET", "/api/check_access_teacher/"),
    ("POST", "/profile/forgot_password/"),
    ("POST", "/profile/reset_password/"),
    ("GET", "/api/teacher_url/"),
    ("POST", "/validation/validate_user/{user_email}"),
    ("GET", "/api/validation_list/"),
    ("POST", "/validation/delete_user/{user_email}"),
    ("POST", "/validation/report_user/{user_email}"),
    ("POST", "/validation/emailed_user/{user_email}"),
    ("POST", "/admin/generate_teacher_report/"),
    ("POST", "/profile/delete/"),
}


def test_backend_business_route_contract_is_stable(app_module):
    actual_routes = {
        (method, route.path)
        for route in app_module.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if route.path.startswith(
            (
                "/api/",
                "/forum/",
                "/profile/",
                "/validation/",
                "/admin/",
                "/internal/",
                "/spotlight/",
                "/teacher/",
                "/promo/",
            )
        )
        and route.path not in {"/forum/new", "/forum/post", "/profile/create", "/profile/edit"}
    }

    assert actual_routes == EXPECTED_BACKEND_ROUTES
