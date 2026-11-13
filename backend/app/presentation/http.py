import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from typing import Annotated, Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyCookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path
from .schemas import Login, NewUser, Named, NewKey, NewEquipment, NewDefect, AccountOut, UserOut, KeyOut, IssuedKeyOut, NamedOut, EquipmentOut, DefectOut
from sqlalchemy.exc import IntegrityError
from app.application.auth import AuthService, InvalidLogin, LoginLimited, digest, SESSION_TTL_SECONDS
from app.application.contracts import Account
from app.infrastructure.database import make_engine, migrate, sessions, database_url
from app.infrastructure.passwords import Passwords
from .dependencies import create_services
from app.domain.errors import InvalidInput, Missing
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.concurrency import run_in_threadpool
from app.domain.errors import AnalysisError
from .uploads import read_photo, read_evidence, read_vision_photo, PREVIEW_REQUEST_SCHEMA
from .demo_gallery import register_demo_gallery
from .field_schemas import (NewMobileModel, NewDeviceInspection, NewComponent, NewComponentWork,
                            EquipmentDigitalCard, ComponentOut, ComponentWorkOut, WorkHistoryOut,
                            PhotoAttachedOut, DeviceInspectionOut, NewDiagnosticPreview, DiagnosticPreviewOut)
from .schemas import PreviewOut
from .schemas import AndroidBuildOut
from .schemas import InspectionOut, HistoryOut
from .schemas import NewReport, ReportOut, NotificationOut, NotificationsOut, NotificationUpdate
from .schemas import NewReview, ReviewOut, ReviewsOut, CloseIssue, IssueOut, InspectionDetailOut
from .schemas import MobileTokenOut, IdOut, HealthOut
from .openapi import API_DESCRIPTION, TAGS, configure_openapi
from app.application.dtos.inspections import ERROR_STATUS
from app.infrastructure.inspection_export import render_inspection
from app.infrastructure.source_files import read_source_file
from .source_schemas import SourceDocumentsOut, ReferenceDatasetsOut, ReferenceRowsOut
from .browser_origin import local_browser_origin
from .documentation import asset_response, docs_html, redoc_html
from fastapi import Query, Header
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from uuid import UUID
import re

COOKIE = "iv_admin_session"
bearer = HTTPBearer(auto_error=False, scheme_name="AccessToken", description="Токен сотрудника из POST /auth/token либо API-ключ интеграции. Введите только значение, без слова Bearer.")
admin_cookie = APIKeyCookie(name=COOKIE, auto_error=False, scheme_name="AdminSession",
                           description="HttpOnly-cookie кабинета. Войдите как администратор через страницу входа; браузер отправляет cookie автоматически. Это не Bearer-токен.")

def public_user(user: Account):
    result = asdict(user)
    result.pop("password_hash")
    return result


def inspection_path(request: Request) -> bool:
    path = request.url.path.split("/api/v1/", 1)[-1]
    return path in ("inspections", "notifications") or path.startswith(("inspections/", "photos/", "reports/", "notifications/", "issues/")) or bool(re.fullmatch(r"equipment/[^/]+/inspections", path))







def create_app(url: str | None = None, *, secure: bool | None = None, origin: str | None = None):
    root_path = os.getenv("ROOT_PATH", "")
    cookie_secure = secure if secure is not None else os.getenv("COOKIE_SECURE", "true").lower() == "true"
    allowed_origin = origin or os.getenv("ALLOWED_ORIGIN", "https://pet.oppennec.ru")
    @asynccontextmanager
    async def lifespan(app):
        engine = make_engine(url or database_url())
        try:
            migrate(engine)
            app.state.services = create_services(session_factory=sessions(engine), analysis_mode=os.getenv("ANALYSIS_MODE", "disabled"))
            yield
        finally:
            engine.dispose()
    app = FastAPI(title="Industrial Vision API", description=API_DESCRIPTION, openapi_tags=TAGS,
                  root_path=root_path, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.exception_handler(AnalysisError)
    async def analysis_error(request, exc):
        status = ERROR_STATUS[exc.code]
        return JSONResponse({"error":{"code":exc.code, "message":str(exc)}}, status_code=status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if inspection_path(request) and exc.status_code in (401, 403):
            code = "UNAUTHENTICATED" if exc.status_code == 401 else "FORBIDDEN"
            return JSONResponse({"error":{"code":code, "message":exc.detail}}, status_code=exc.status_code, headers=exc.headers)
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if inspection_path(request):
            return JSONResponse({"error":{"code":"VALIDATION_ERROR", "message":"Некорректные параметры запроса"}}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse({"detail":"Такая запись уже есть или связанная запись не найдена"},status_code=409)
    @app.exception_handler(InvalidInput)
    async def invalid_input(request, exc):
        return JSONResponse({"detail":str(exc)},status_code=422)
    @app.exception_handler(Missing)
    async def missing(request, exc):
        return JSONResponse({"detail":str(exc)},status_code=404)

    @app.middleware("http")
    async def private_cache(request, call_next):
        response = await call_next(request)
        renewed_cookie = getattr(request.state, "renewed_cookie", None)
        if renewed_cookie and response.status_code < 400:
            response.set_cookie(COOKIE, renewed_cookie, max_age=SESSION_TTL_SECONDS, httponly=True, secure=cookie_secure, samesite="strict", path=(root_path or "")+"/")
        if request.url.path != "/healthz":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def csrf(request: Request):
        origin = request.headers.get("origin")
        trusted_local = os.getenv("LOCAL_DEMO_ENABLED") == "true" and local_browser_origin(origin, request.headers.get("host"), request.url.scheme)
        if request.headers.get("x-iv-client") != "browser" or not (origin == allowed_origin or trusted_local):
            raise HTTPException(403, "Недопустимый источник запроса")

    def administrator(request: Request, cookie: Annotated[str | None, Security(admin_cookie)]) -> Account:
        user = request.app.state.services.auth.authenticate(cookie or "", "session")
        if not user: raise HTTPException(401, "Войдите как администратор")
        if user.role != "ADMIN": raise HTTPException(403, "Требуется администратор")
        request.state.renewed_cookie = request.cookies[COOKIE]
        return user

    def principal(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
                  cookie: Annotated[str | None, Security(admin_cookie)]) -> Account:
        if credentials:
            raw = credentials.credentials
            user = request.app.state.services.auth.authenticate(raw, "key" if raw.startswith("iv_k_") else "session")
        else:
            user = request.app.state.services.auth.authenticate(cookie or "", "session")
        if not user: raise HTTPException(401, "Требуется авторизация", headers={"WWW-Authenticate":"Bearer"})
        if not credentials:
            request.state.renewed_cookie = request.cookies[COOKIE]
        return user

    Admin = Annotated[Account, Depends(administrator)]
    Member = Annotated[Account, Depends(principal)]

    def write_source(request: Request):
        if getattr(request.state, "renewed_cookie", None):
            csrf(request)

    def repeat_key(value: str | None) -> str:
        try:
            return str(UUID(value or ""))
        except ValueError:
            raise AnalysisError("VALIDATION_ERROR", "Нужен Idempotency-Key в формате UUID") from None

    @app.get("/api/v1/source-documents", response_model=SourceDocumentsOut)
    def source_documents(request: Request, user: Member):
        return request.app.state.services.sources.documents(user)

    @app.get("/api/v1/source-documents/{document_id}/file", response_class=Response,
             responses={200: {"content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}})
    def source_document_file(document_id: str, request: Request, user: Member):
        from urllib.parse import quote
        document = request.app.state.services.sources.document(document_id, user)
        directory = os.getenv("ORGANIZER_DATA_PATH")
        if not directory:
            raise Missing("Хранилище материалов организаторов не подключено")
        content = read_source_file(Path(directory), document)
        return Response(content=content, media_type="application/octet-stream", headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(document["name"], safe=""),
            "X-Content-SHA256": document["sha256"],
        })

    @app.get("/api/v1/reference-datasets", response_model=ReferenceDatasetsOut)
    def reference_datasets(request: Request, user: Member):
        return request.app.state.services.sources.datasets(user)

    @app.get("/api/v1/reference-datasets/{dataset_id}", response_model=ReferenceRowsOut)
    def reference_dataset(dataset_id: str, request: Request, user: Member,
                          offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
        return request.app.state.services.sources.dataset(dataset_id, user, offset, limit)

    @app.post("/api/v1/mobile-models", response_model=NewMobileModel, status_code=201, dependencies=[Depends(csrf)])
    def register_mobile_model(body: NewMobileModel, request: Request, user: Admin):
        return request.app.state.services.field_service.register_model(body.model_dump(mode="json"), user)

    @app.post("/api/v1/inspections/mobile", response_model=DeviceInspectionOut, status_code=201)
    def device_inspection(body: NewDeviceInspection, request: Request, user: Member,
                          idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
        write_source(request)
        result = request.app.state.services.field_service.mobile_inspection(
            body.model_dump(mode="json"), repeat_key(idempotency_key), user)
        return JSONResponse(result.body, status_code=result.status)

    @app.post("/api/v1/inspections/{inspection_id}/photo", response_model=PhotoAttachedOut)
    async def device_photo(inspection_id: int, request: Request, user: Member):
        write_source(request)
        content = await read_evidence(request)
        result = await run_in_threadpool(request.app.state.services.field_service.attach_photo, inspection_id, content, user)
        return JSONResponse(result)

    @app.post("/api/v1/inspections/vision", status_code=201, response_model=InspectionOut,
              openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                  "type": "object", "required": ["equipment_id", "image"], "properties": {
                      "equipment_id": {"type": "integer", "minimum": 1},
                      "component_id": {"type": "integer", "minimum": 1},
                      "source": {"type": "string", "enum": ["CAMERA"]},
                      "captured_at": {"type": "string", "format": "date-time"},
                      "image": {"type": "string", "format": "binary", "description": "Кадр камеры JPEG/PNG; EXIF нормализуется."}}}}}}})
    async def server_vision(request: Request, user: Member,
                            idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
        write_source(request)
        fields, content = await read_vision_photo(request)
        result = await run_in_threadpool(request.app.state.services.vision.create,
                                        values=fields.model_dump(mode="json"), content=content,
                                        key=repeat_key(idempotency_key), actor=user)
        return JSONResponse(result.body, status_code=result.status)

    @app.get("/api/v1/vision-status", include_in_schema=False)
    def vision_status(request: Request, user: Member):
        return request.app.state.services.vision.status()

    @app.get("/api/v1/equipment/resolve", response_model=EquipmentDigitalCard)
    def resolve_qr(request: Request, user: Member, code: Annotated[str, Query(min_length=1, max_length=120)]):
        return request.app.state.services.field_service.resolve(code, user)

    @app.get("/api/v1/equipment/{equipment_id}/card", response_model=EquipmentDigitalCard)
    def digital_card(equipment_id: int, request: Request, user: Member):
        return request.app.state.services.field_service.card(equipment_id, user)

    @app.post("/api/v1/equipment/{equipment_id}/components", response_model=ComponentOut, status_code=201, dependencies=[Depends(csrf)])
    def add_component(equipment_id: int, body: NewComponent, request: Request, user: Admin):
        return request.app.state.services.field_service.add_component(equipment_id, body.model_dump(mode="json"), user)

    @app.post("/api/v1/components/{component_id}/work", response_model=ComponentWorkOut, status_code=201)
    def component_work(component_id: int, body: NewComponentWork, request: Request, user: Member,
                       idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
        write_source(request)
        return request.app.state.services.field_service.record_work(component_id, body.model_dump(mode="json"), repeat_key(idempotency_key), user)

    @app.get("/api/v1/components/{component_id}/work", response_model=WorkHistoryOut)
    def work_history(component_id: int, request: Request, user: Member,
                     limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
        return request.app.state.services.field_service.work_history(component_id, user, limit, offset)

    @app.post("/api/v1/equipment/{equipment_id}/diagnostics/preview", response_model=DiagnosticPreviewOut)
    def diagnostic_preview(equipment_id: int, body: NewDiagnosticPreview, request: Request, user: Member):
        write_source(request)
        return request.app.state.services.field_service.diagnosis(equipment_id, body.model_dump(mode="json"), user)

    if os.getenv("LOCAL_DEMO_ENABLED") == "true":
        @app.get("/api/v1/equipment/{equipment_id}/demo-scenarios", include_in_schema=False)
        def demo_scenarios(equipment_id: int, request: Request, user: Member):
            from app.domain.diagnostic_scenarios import pump_scenarios
            card = request.app.state.services.field_service.card(equipment_id, user)
            if card["inventory_number"] != "pump_demo_001":
                raise AnalysisError("NOT_FOUND", "Сценарии доступны только для демонстрационного насоса")
            component = next((c for c in card["components"] if any(s["name"] == "current_a" for s in c["specifications"])), None)
            if component is None:
                raise AnalysisError("NOT_FOUND", "Не подготовлены нормы демонстрационного компонента")
            return {"synthetic": True, "component_id": component["id"], "scenarios": pump_scenarios()}

    def do_login(request, body):
        try:
            return request.app.state.services.auth.login(body.login.strip().lower(), body.password)
        except InvalidLogin:
            raise HTTPException(401, "Неверный логин или пароль") from None
        except LoginLimited:
            raise HTTPException(429, "Слишком много попыток. Повторите через 5 минут", headers={"Retry-After":"300"}) from None

    @app.get("/healthz", include_in_schema=False)
    def liveness(): return {"status":"ok"}

    @app.post("/api/v1/auth/login", response_model=AccountOut, dependencies=[Depends(csrf)])
    def login(body: Login, request: Request, response: Response):
        user, token = do_login(request, body)
        if user.role != "ADMIN":
            request.app.state.services.auth.logout(token)
            raise HTTPException(403, "Веб-кабинет доступен только администратору")
        old = request.cookies.get(COOKIE)
        if old: request.app.state.services.auth.logout(old)
        response.set_cookie(COOKIE, token, max_age=SESSION_TTL_SECONDS, httponly=True, secure=cookie_secure, samesite="strict", path=(root_path or "")+"/")
        return public_user(user)

    @app.post("/api/v1/auth/token", response_model=MobileTokenOut)
    def mobile_login(body: Login, request: Request):
        user, token = do_login(request, body)
        return {"access_token":token,"token_type":"bearer","expires_in":SESSION_TTL_SECONDS,"user":public_user(user)}

    @app.get("/api/v1/auth/me", response_model=AccountOut)
    def admin_me(user: Admin): return public_user(user)

    @app.get("/api/v1/me", response_model=AccountOut)
    def me(user: Member): return public_user(user)

    @app.post("/api/v1/auth/logout", status_code=204, dependencies=[Depends(csrf)])
    def logout(request: Request, response: Response):
        request.app.state.services.auth.logout(request.cookies.get(COOKIE, ""))
        response.delete_cookie(COOKIE, path=(root_path or "")+"/", secure=cookie_secure, httponly=True, samesite="strict")

    @app.get("/api/v1/health", response_model=HealthOut)
    def health(user: Member): return {"status":"ok"}

    @app.post("/api/v1/inspections/preview", response_model=PreviewOut, openapi_extra=PREVIEW_REQUEST_SCHEMA)
    async def preview(request: Request, user: Member):
        if getattr(request.state, "renewed_cookie", None):
            csrf(request)
        fields, content = await read_photo(request)
        return await run_in_threadpool(request.app.state.services.preview.execute,
                                       equipment_id=fields.equipment_id, source=fields.source,
                                       content=content, actor=user)

    @app.post("/api/v1/inspections", status_code=201, response_model=InspectionOut,
              openapi_extra={**PREVIEW_REQUEST_SCHEMA, "parameters":[
                  {"name":"Idempotency-Key", "in":"header", "required":True, "schema":{"type":"string", "format":"uuid"}}]})
    async def create_inspection(request: Request, user: Member):
        if getattr(request.state, "renewed_cookie", None):
            csrf(request)
        try:
            key = str(UUID(request.headers.get("idempotency-key", "")))
        except ValueError:
            raise AnalysisError("VALIDATION_ERROR", "Нужен Idempotency-Key в формате UUID") from None
        fields, content = await read_photo(request)
        result = await run_in_threadpool(request.app.state.services.inspections.create,
                                        equipment_id=fields.equipment_id, source=fields.source, content=content, key=key, actor=user)
        return JSONResponse(result.body, status_code=result.status)

    @app.get("/api/v1/inspections/{inspection_id}", response_model=InspectionDetailOut)
    def inspection(inspection_id: int, request: Request, user: Member):
        result = request.app.state.services.inspections.get(inspection_id=inspection_id, actor=user)
        return JSONResponse(result.body, status_code=result.status)

    @app.get("/api/v1/inspections/{inspection_id}/export")
    def inspection_export(inspection_id: int, request: Request, user: Member,
                          format: Literal["pdf", "xlsx"] = "pdf"):
        result = request.app.state.services.inspections.get(inspection_id=inspection_id, actor=user)
        if result.status != 200:
            return JSONResponse(result.body, status_code=result.status)
        content = render_inspection(result.body, format)
        media = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="inspection-{inspection_id}.{format}"'})

    @app.get("/api/v1/photos/{photo_id}")
    def photo(photo_id: int, request: Request, user: Member):
        content, media_type = request.app.state.services.inspections.photo(photo_id=photo_id, actor=user)
        extension = "jpg" if media_type == "image/jpeg" else "png"
        return Response(content, media_type=media_type, headers={"Content-Disposition":f'inline; filename="inspection-{photo_id}.{extension}"'})

    @app.get("/api/v1/equipment/{equipment_id}/inspections", response_model=HistoryOut, response_model_exclude_unset=True)
    def inspection_history(equipment_id: int, request: Request, user: Member,
                           limit: Annotated[int, Query(ge=1, le=100)] = 20,
                           offset: Annotated[int, Query(ge=0)] = 0):
        return request.app.state.services.inspections.history(equipment_id=equipment_id, actor=user, limit=limit, offset=offset)

    @app.post("/api/v1/inspections/{inspection_id}/reports", response_model=ReportOut, status_code=201)
    def create_report(inspection_id: int, body: NewReport, request: Request, user: Member,
                      idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")]):
        if getattr(request.state, "renewed_cookie", None):
            csrf(request)
        result = request.app.state.services.reporting.create(inspection_id=inspection_id, actor=user,
                                                             key=str(idempotency_key), comment=body.comment)
        return JSONResponse(result.body, status_code=result.status)

    @app.get("/api/v1/reports/{report_id}", response_model=ReportOut)
    def report(report_id: int, request: Request, user: Member):
        return request.app.state.services.reporting.report(report_id=report_id, actor=user)

    @app.get("/api/v1/notifications", response_model=NotificationsOut)
    def notifications(request: Request, user: Member, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                      offset: Annotated[int, Query(ge=0)] = 0, unread_only: bool = False):
        return request.app.state.services.reporting.notifications(actor=user, limit=limit, offset=offset, unread_only=unread_only)

    @app.patch("/api/v1/notifications/{notification_id}", response_model=NotificationOut)
    def mark_notification(notification_id: int, body: NotificationUpdate, request: Request, user: Member):
        if getattr(request.state, "renewed_cookie", None):
            csrf(request)
        return request.app.state.services.reporting.mark_notification(notification_id=notification_id, actor=user, is_read=body.is_read)

    @app.post("/api/v1/inspections/{inspection_id}/reviews", response_model=ReviewOut, status_code=201)
    def create_review(inspection_id: int, body: NewReview, request: Request, user: Member,
                      idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")]):
        if getattr(request.state, "renewed_cookie", None):
            csrf(request)
        result = request.app.state.services.reviews.review(inspection_id=inspection_id, actor=user, key=str(idempotency_key), **body.model_dump())
        return JSONResponse(result.body, status_code=result.status)

    @app.get("/api/v1/inspections/{inspection_id}/reviews", response_model=ReviewsOut)
    def review_history(inspection_id: int, request: Request, user: Member,
                       limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
        return request.app.state.services.reviews.history(inspection_id=inspection_id, actor=user, limit=limit, offset=offset)

    @app.get("/api/v1/issues/{issue_id}", response_model=IssueOut)
    def issue(issue_id: int, request: Request, user: Member):
        return request.app.state.services.reviews.issue(issue_id=issue_id, actor=user)

    @app.post("/api/v1/issues/{issue_id}/close", response_model=IssueOut)
    def close_issue(issue_id: int, body: CloseIssue, request: Request, user: Member,
                    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")]):
        if getattr(request.state, "renewed_cookie", None):
            csrf(request)
        result = request.app.state.services.reviews.close(issue_id=issue_id, actor=user, key=str(idempotency_key), **body.model_dump())
        return JSONResponse(result.body, status_code=result.status)

    @app.get("/api/v1/keys", response_model=list[KeyOut])
    def keys(request: Request, user: Admin): return request.app.state.services.queries.keys(actor_id=user.id)

    @app.post("/api/v1/keys", response_model=IssuedKeyOut, status_code=201, dependencies=[Depends(csrf)])
    def new_key(body: NewKey, request: Request, user: Admin):
        return request.app.state.services.issue_key.execute(actor_id=user.id, name=body.name, days=body.days)

    @app.delete("/api/v1/keys/{key_id}", status_code=204, dependencies=[Depends(csrf)])
    def revoke(key_id: int, request: Request, user: Admin):
        request.app.state.services.revoke_key.execute(actor_id=user.id,key_id=key_id)

    @app.get("/api/v1/users", response_model=list[UserOut])
    def users(request: Request, user: Admin): return request.app.state.services.queries.users()

    @app.post("/api/v1/users", response_model=IdOut, status_code=201, dependencies=[Depends(csrf)])
    def add_user(body: NewUser, request: Request, user: Admin):
        return request.app.state.services.users.execute(actor_id=user.id, **body.model_dump())

    def insert(kind, values, request, user):
        return request.app.state.services.catalogue.execute(actor_id=user.id,kind=kind,values=values)


    @app.get("/api/v1/workshops", response_model=list[NamedOut])
    def workshops(request: Request, user: Member): return request.app.state.services.queries.catalogue(kind="workshops",actor=user)
    @app.get("/api/v1/equipment-types", response_model=list[NamedOut])
    def types(request: Request, user: Member): return request.app.state.services.queries.catalogue(kind="equipment-types",actor=user)
    @app.get("/api/v1/equipment", response_model=list[EquipmentOut])
    def equipment(request: Request, user: Member): return request.app.state.services.queries.catalogue(kind="equipment",actor=user)
    @app.get("/api/v1/equipment/{equipment_id}", response_model=EquipmentOut)
    def equipment_card(equipment_id: int, request: Request, user: Member):
        return request.app.state.services.queries.equipment(equipment_id=equipment_id, actor=user)
    @app.get("/api/v1/defect-types", response_model=list[DefectOut])
    def defects(request: Request, user: Member): return request.app.state.services.queries.catalogue(kind="defect-types",actor=user)
    @app.post("/api/v1/workshops", response_model=IdOut, status_code=201, dependencies=[Depends(csrf)])
    def add_workshop(body: Named, request: Request, user: Admin): return insert("workshops",body.model_dump(),request,user)
    @app.post("/api/v1/equipment-types", response_model=IdOut, status_code=201, dependencies=[Depends(csrf)])
    def add_type(body: Named, request: Request, user: Admin): return insert("equipment-types",body.model_dump(),request,user)
    @app.post("/api/v1/equipment", response_model=IdOut, status_code=201, dependencies=[Depends(csrf)])
    def add_equipment(body: NewEquipment, request: Request, user: Admin): return insert("equipment",body.model_dump(),request,user)
    @app.post("/api/v1/defect-types", response_model=IdOut, status_code=201, dependencies=[Depends(csrf)])
    def add_defect(body: NewDefect, request: Request, user: Admin): return insert("defect-types",body.model_dump(),request,user)

    @app.get("/openapi.json", include_in_schema=False)
    def schema(user: Admin):
        result=app.openapi()
        result["servers"]=[{"url":root_path or "/"}]
        return result
    @app.get("/docs", include_in_schema=False)
    def docs(user: Admin):
        return docs_html(root_path)
    @app.get("/redoc", include_in_schema=False)
    def redoc(user: Admin): return redoc_html(root_path)

    @app.get("/docs-assets/{name}", include_in_schema=False)
    def documentation_asset(name: str, user: Admin):
        return asset_response(name)

    apk_path = os.getenv("ANDROID_APK_PATH")
    if apk_path:
        cv_example = os.getenv("CV_EXAMPLE_PATH")
        if cv_example:
            @app.get("/demo-identifiers", response_class=HTMLResponse, include_in_schema=False)
            def demo_identifiers_page():
                from html import escape
                prefix = escape(root_path or "", quote=True)
                return HTMLResponse(f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Демо: QR и шильдик</title><style>body{{font:18px system-ui;background:#edf1f4;color:#18232c;margin:0}}main{{max-width:1200px;margin:auto;padding:24px}}img{{display:block;max-width:100%;height:auto;margin:24px auto;background:white}}.qr{{width:min(65vh,520px)}}a{{color:#0058a0}}</style></head><body><main><h1>QR и шильдик демонстрационного насоса</h1><p>Это учебный макет, а не заводской паспорт. В приложении войдите как pump_engineer. Для QR выберите чтение QR; для таблички нажмите «Считать шильдик» и подтвердите номер.</p><h2>QR: pump_demo_001</h2><img class="qr" src="{prefix}/demo-qr.svg" alt="QR демонстрационного насоса"><h2>Шильдик: DEMO-PUMP-2026-001</h2><img src="{prefix}/demo-nameplate.svg" alt="Демонстрационная заводская табличка"><p>Маркировка не определяет состояние насоса. После идентификации откройте карточку компонента и выполните визуальный осмотр.</p><a href="{prefix}/cv-example">Пример поверхности для анализа камерой</a></main></body></html>''')

            @app.get("/demo-qr.svg", include_in_schema=False)
            def demo_qr_image():
                path = Path(cv_example).with_name("pump-qr.svg")
                if not path.is_file():
                    raise HTTPException(404, "Макет QR не найден")
                return FileResponse(path, media_type="image/svg+xml")

            @app.get("/demo-nameplate.svg", include_in_schema=False)
            def demo_nameplate_image():
                path = Path(cv_example).with_name("nameplate.svg")
                if not path.is_file():
                    raise HTTPException(404, "Макет шильдика не найден")
                return FileResponse(path, media_type="image/svg+xml")

            @app.get("/cv-example", response_class=HTMLResponse, include_in_schema=False)
            def cv_example_page():
                from html import escape
                image_url = escape((root_path or "") + "/cv-example.png", quote=True)
                full_url = escape((root_path or "") + "/cv-example-full.png", quote=True)
                qr_url = escape((root_path or "") + "/demo-qr.svg", quote=True)
                return HTMLResponse(f'''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Машинное зрение — пример насоса</title>
<link rel="icon" href="data:,"><style>body{{margin:0;background:#10151a;color:#fff;font:18px system-ui;text-align:center}}main{{padding:16px}}img{{display:block;height:auto;margin:0 auto}}p{{margin:0 0 12px}}.controls{{display:flex;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:16px}}button{{font:inherit;min-width:44px;padding:8px 14px;border:1px solid #768696;border-radius:8px;background:#273546;color:white;cursor:pointer}}input{{width:min(40vw,300px)}}.image{{overflow:auto}}.scene{{position:relative;display:inline-block;vertical-align:top}}.scene #pump{{width:100%;margin:0}}.plate{{position:absolute;right:2%;bottom:3%;width:68%;box-sizing:border-box;background:#fff;color:#111;padding:12px;box-shadow:0 2px 10px #0009;border:3px solid #343a40;border-radius:6px;text-align:left;display:flex;gap:10px;align-items:center}}.plate[hidden]{{display:none}}.plate-text{{flex:1;min-width:0}}.plate strong{{display:block;font-size:clamp(14px,2.2vw,30px);overflow-wrap:anywhere}}.plate small{{display:block;font-size:clamp(10px,1.4vw,17px)}}.plate img{{width:24%;margin:0;flex:none}}.instructions{{font-size:15px;color:#d1d9e2;max-width:1000px;margin:0 auto 12px}}button[aria-pressed=true]{{background:#365e49}}</style></head>
<body><main><p>Наведите камеру телефона на насос. Меняйте размер изображения для проверки.</p>
<div class="controls"><button id="smaller" aria-label="Уменьшить">−</button><input id="scale" type="range" min="25" max="200" step="5" value="100" aria-label="Размер фотографии"><button id="larger" aria-label="Увеличить">+</button><output id="value">100%</output><button id="fit">По размеру экрана</button><button id="toggle-plate" aria-pressed="true">Шильдик: показан</button></div><p class="instructions">Сначала считайте QR или нажмите «Считать шильдик» и подтвердите DEMO-PUMP-2026-001. Затем выберите компонент и анализируйте поверхность. Макет таблички добавлен для демо и не является заводским паспортом. При необходимости скройте его кнопкой.</p>
<div class="image"><div class="scene" id="scene"><img id="pump" src="{image_url}" alt="Ржавый насос для проверки живой камерой"><div class="plate" id="plate"><div class="plate-text"><small>DEMO TEAM · CENTRIFUGAL DEMO</small><small>SERIAL NUMBER</small><strong>DEMO-PUMP-2026-001</strong><small>INVENTORY: pump_demo_001</small><small>DEMO — УЧЕБНЫЙ МАКЕТ</small></div><img src="{qr_url}" alt="QR: pump_demo_001"></div></div></div><p style="font-size:14px;color:#b7c2ce;margin-top:16px">Демонстрационный исходник Qwen из материалов организаторов. <a style="color:#c4dbff" href="{full_url}" target="_blank" rel="noreferrer">Полное изображение</a></p>
<script>const image=document.getElementById('pump'),scale=document.getElementById('scale'),value=document.getElementById('value');function resize(){{const ratio=image.naturalWidth/image.naturalHeight||1.49;const base=Math.min(innerWidth*.94,innerHeight*.72*ratio,1400);document.getElementById('scene').style.width=(base*Number(scale.value)/100)+'px';value.textContent=scale.value+'%';}}document.getElementById('toggle-plate').onclick=()=>{{const plate=document.getElementById('plate'),button=document.getElementById('toggle-plate');plate.hidden=!plate.hidden;button.setAttribute('aria-pressed',String(!plate.hidden));button.textContent=plate.hidden?'Шильдик: скрыт':'Шильдик: показан';}};scale.addEventListener('input',resize);document.getElementById('smaller').onclick=()=>{{scale.value=Number(scale.value)-10;resize();}};document.getElementById('larger').onclick=()=>{{scale.value=Number(scale.value)+10;resize();}};document.getElementById('fit').onclick=()=>{{scale.value=100;resize();}};image.addEventListener('load',resize);addEventListener('resize',resize);resize();</script></main></body></html>''')

            @app.get("/cv-example-full.png", include_in_schema=False)
            def cv_example_full_image():
                full_path = Path(cv_example).with_name("rust-pump-full.png")
                if not full_path.is_file():
                    raise HTTPException(404, "Полный пример не найден")
                return FileResponse(full_path, media_type="image/png")

            @app.get("/cv-example.png", include_in_schema=False)
            def cv_example_image():
                if not Path(cv_example).is_file():
                    raise HTTPException(404, "Пример для камеры не найден")
                return FileResponse(cv_example, media_type="image/png")

        def android_build_state():
            import json
            state_file = Path(apk_path).with_name("build-status.json")
            try:
                with state_file.open() as file:
                    data = file.read(2049)
                saved = json.loads(data) if len(data) <= 2048 else None
                state = saved.get("state") if isinstance(saved, dict) else "ERROR"
                if not isinstance(state, str) or state not in ("MISSING", "BUILDING", "READY", "ERROR"):
                    state = "ERROR"
            except FileNotFoundError:
                state = "READY" if Path(apk_path).is_file() else "MISSING"
            except (OSError, json.JSONDecodeError):
                state = "ERROR"
            if state == "READY" and not Path(apk_path).is_file():
                state = "MISSING"
            messages = {"MISSING":"APK пока не собран. Запустите локальный проект.",
                        "BUILDING":"APK собирается. Сайт и сервер уже доступны.",
                        "READY":"APK готов к установке.",
                        "ERROR":"Сборка APK не завершена. Посмотрите терминал запуска и повторите команду."}
            return {"state":state, "message":messages[state]}

        @app.get("/api/v1/android-build", response_model=AndroidBuildOut, include_in_schema=False)
        def android_build_status():
            return android_build_state()

        @app.get("/mobile-server", include_in_schema=False)
        def mobile_server_identity():
            return {"service":"industrial-vision", "api_path":(root_path or "") + "/api/v1/"}

        @app.get("/android.apk", include_in_schema=False)
        def android_download():
            state = android_build_state()
            if state["state"] in ("BUILDING", "ERROR"):
                raise HTTPException(503, state["message"], headers={"Retry-After":"5"})
            if not Path(apk_path).is_file():
                raise HTTPException(404, "APK ещё не собран")
            return FileResponse(apk_path, media_type="application/vnd.android.package-archive",
                                filename="intelligent-system-ar-local.apk")

    frontend = Path(os.getenv("FRONTEND_DIR", "/app/frontend"))
    register_demo_gallery(app, root_path, os.getenv("CV_EXAMPLE_PATH"), frontend)
    if frontend.is_dir():
        app.mount("/assets",StaticFiles(directory=frontend/"assets"),name="assets")
        @app.get("/", include_in_schema=False)
        def index(): return FileResponse(frontend/"index.html")
    configure_openapi(app)
    return app
