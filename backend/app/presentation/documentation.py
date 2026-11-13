"""Admin-only documentation assets are served by the authenticated HTTP routes.

Vendor bytes are pinned in vendor/manifest.json. Never construct a filesystem path
from a request value: asset_response accepts only the explicit public names below.
"""
from pathlib import Path

from fastapi import HTTPException
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, Response

_VENDOR = Path(__file__).with_name("vendor")
_ASSETS = {
    "swagger-ui-bundle.js": ("swagger-ui-bundle.js.gz", "text/javascript"),
    "swagger-ui.css": ("swagger-ui.css.gz", "text/css"),
    "redoc.standalone.js": ("redoc.standalone.js.gz", "text/javascript"),
}
_FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#182c38"/><circle cx="16" cy="16" r="9" fill="none" stroke="#62c6e4" stroke-width="3"/><circle cx="16" cy="16" r="3" fill="#62c6e4"/></svg>'


def docs_html(root_path: str) -> HTMLResponse:
    base = root_path.rstrip("/")
    return get_swagger_ui_html(
        openapi_url=base + "/openapi.json", title="Industrial Vision API — документация",
        swagger_js_url=base + "/docs-assets/swagger-ui-bundle.js",
        swagger_css_url=base + "/docs-assets/swagger-ui.css",
        swagger_favicon_url=base + "/docs-assets/favicon.svg",
        swagger_ui_parameters={"filter": True, "displayRequestDuration": True,
                               "docExpansion": "none", "defaultModelsExpandDepth": 1,
                               "validatorUrl": None},
    )


def redoc_html(root_path: str) -> HTMLResponse:
    base = root_path.rstrip("/")
    return get_redoc_html(
        openapi_url=base + "/openapi.json", title="Industrial Vision API",
        redoc_js_url=base + "/docs-assets/redoc.standalone.js",
        redoc_favicon_url=base + "/docs-assets/favicon.svg",
        with_google_fonts=False,
    )


def asset_response(name: str) -> Response:
    if name == "favicon.svg":
        return Response(_FAVICON, media_type="image/svg+xml",
                        headers={"X-Content-Type-Options": "nosniff"})
    asset = _ASSETS.get(name)
    if asset is None:
        raise HTTPException(404, "Ресурс документации не найден")
    filename, media_type = asset
    return FileResponse(_VENDOR / filename, media_type=media_type,
                        headers={"Content-Encoding": "gzip", "X-Content-Type-Options": "nosniff"})
