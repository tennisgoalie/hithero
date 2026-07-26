"""Site-level public endpoints that are not part of the legacy page layer."""

import base64
import hashlib
import os
from urllib.parse import quote
from xml.etree import ElementTree

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import String, cast, select

from backend.repositories.teachers import TeacherDirectoryRepository


PROMO_IMAGE_MAPPING = {
    "seattlewolf": "images/partners/1007TheWolf.png",
    "livefree": "images/partners/965CountryColor.png",
    "basecamp": "images/partners/BaseCamp.png",
    "coastal": "images/partners/Coastal.png",
}

SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
SITEMAP_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"
SITEMAP_STATIC_URLS = (
    "https://www.helpteachers.net/",
    "https://www.helpteachers.net/teachers",
    "https://www.helpteachers.net/about",
    "https://www.helpteachers.net/contact",
	"https://www.helpteachers.net/terms",
    "https://www.helpteachers.net/partners",
)


def _build_sitemap_xml(teacher_url_ids):
    """Build a deterministic sitemap without unverifiable modification dates."""
    ElementTree.register_namespace("", SITEMAP_NAMESPACE)
    root = ElementTree.Element(f"{{{SITEMAP_NAMESPACE}}}urlset")
    locations = list(SITEMAP_STATIC_URLS)
    locations.extend(
        f"https://www.helpteachers.net/teacher/{quote(url_id, safe='-._~')}"
        for url_id in teacher_url_ids
    )
    for location in locations:
        url = ElementTree.SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
        ElementTree.SubElement(url, f"{{{SITEMAP_NAMESPACE}}}loc").text = location
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _sitemap_response(request: Request, content: bytes):
    etag = f'"{hashlib.sha256(content).hexdigest()}"'
    headers = {
        "Cache-Control": SITEMAP_CACHE_CONTROL,
        "ETag": etag,
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=content, media_type="application/xml", headers=headers)


def create_site_router(
    *,
    session_factory,
    school_model,
    teacher_model,
    spotlight_model,
    set_teacher_session,
    logger,
    static_dir="static",
):
    """Register public assets, promotion flows, and external teacher links."""
    router = APIRouter()
    teacher_directory_repository = TeacherDirectoryRepository(
        session_factory=session_factory,
        school_model=school_model,
        teacher_model=teacher_model,
    )

    @router.get("/ads.txt", include_in_schema=False)
    async def get_ads_txt():
        return FileResponse(
            os.path.join(static_dir, "ads.txt"),
            media_type="text/plain",
        )

    @router.get("/sitemap.xml", include_in_schema=False)
    async def get_sitemap_xml(request: Request):
        content = _build_sitemap_xml(
            teacher_directory_repository.list_public_teacher_url_ids(),
        )
        return _sitemap_response(request, content)

    @router.get("/spotlight/{token}")
    async def get_spotlight_info(request: Request, token: str):
        db = session_factory()
        try:
            spotlight_info = db.execute(
                select(spotlight_model).where(
                    cast(spotlight_model.token, String)
                    == cast(token, String),
                ),
            ).fetchone()
            if not spotlight_info:
                raise HTTPException(
                    status_code=404,
                    detail="Spotlight info not found for the given token",
                )

            data = spotlight_info[0]
            image_data = (
                base64.b64encode(data.image_data).decode("utf-8")
                if data.image_data
                else None
            )
            teacher_row = db.execute(
                select(teacher_model).where(
                    cast(teacher_model.name, String) == cast(data.name, String),
                    cast(teacher_model.state, String)
                    == cast(data.state, String),
                    cast(teacher_model.county, String)
                    == cast(data.county, String),
                    cast(teacher_model.district, String)
                    == cast(data.district, String),
                    cast(teacher_model.school, String)
                    == cast(data.school, String),
                ),
            ).fetchone()
            if not teacher_row:
                raise HTTPException(
                    status_code=404,
                    detail="Spotlight teacher is not currently public.",
                )
            request.session["state"] = data.state
            request.session["county"] = data.county
            if data.district:
                request.session["district"] = data.district
            if data.school:
                request.session["school"] = data.school
                request.session["teacher"] = data.name
            return {
                "state": data.state,
                "county": data.county,
                "district": data.district,
                "school": data.school,
                "name": data.name,
                "image_data": image_data,
                "url_id": teacher_row[0].url_id,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Internal Server Error: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            )
        finally:
            db.close()

    @router.get("/teacher/{url_id}")
    async def get_teacher_info(url_id: str, request: Request):
        """Preserve externally shared teacher URLs during the page migration."""
        db = session_factory()
        try:
            teacher_info = db.execute(
                select(teacher_model).where(cast(teacher_model.url_id, String) == url_id),
            ).fetchone()
            if not teacher_info:
                return RedirectResponse(url="/404")
            set_teacher_session(request, teacher_info[0])
            return RedirectResponse(url="/teacher")
        except Exception:
            logger.exception(
                "Legacy teacher session bridge failed",
                extra={"url_id": url_id},
            )
            return RedirectResponse(url="/404")
        finally:
            db.close()

    @router.get("/promo/get_promo_info/")
    async def get_promo_info(request: Request):
        return JSONResponse(
            content={
                "promo_image_url": request.session.pop("promo_image_url", None),
                "promo_title": request.session.pop("promo_title", None),
            },
        )

    @router.get("/{token}")
    async def get_promotional_page_with_hero(request: Request, token: str):
        relative_image_path = PROMO_IMAGE_MAPPING.get(token.lower())
        if not relative_image_path:
            relative_image_path = PROMO_IMAGE_MAPPING.get("default")
            if not relative_image_path:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Promotional image not found and no default image "
                        "available in mapping."
                    ),
                )

        full_filesystem_path = os.path.join(static_dir, relative_image_path)
        if not os.path.exists(full_filesystem_path):
            if token != "default":
                default_relative_path = PROMO_IMAGE_MAPPING.get("default")
                if default_relative_path and os.path.exists(
                    os.path.join(static_dir, default_relative_path),
                ):
                    relative_image_path = default_relative_path
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Image for token '{token}' not found and default "
                            "image file is also missing."
                        ),
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail="Default promotional image file not found.",
                )

        request.session["promo_image_url"] = f"/static/{relative_image_path}"
        request.session["promo_title"] = "Working together to serve our communities!"
        return RedirectResponse(url="/")

    return router
