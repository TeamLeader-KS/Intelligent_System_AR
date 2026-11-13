from dataclasses import dataclass
from app.application.auth import AuthService
from app.application.use_case.administration import CreateUserUseCase, IssueKeyUseCase, RevokeKeyUseCase, CatalogueCreateUseCase, AdminQueriesUseCase
from app.infrastructure.passwords import Passwords
from app.infrastructure.repository import Repository
from app.infrastructure.queries.admin import AdminQueries
from app.application.use_case.preview import PreviewInspectionUseCase
from app.infrastructure.images import PillowImageDecoder
from app.infrastructure.mock_model import MockModelAdapter
from app.application.use_case.inspections import InspectionsUseCase
from app.infrastructure.inspections import PostgresInspectionRepository
from app.infrastructure.queries.inspections import PostgresInspectionQueries
from app.infrastructure.photo_storage import photo_storages
from app.application.use_case.reporting import ReportingUseCase
from app.infrastructure.reporting import PostgresReportingRepository
from app.infrastructure.queries.reporting import PostgresReportingQueries
from app.application.use_case.reviews import ReviewUseCase
from app.infrastructure.reviews import PostgresReviewRepository
from app.infrastructure.queries.reviews import PostgresReviewQueries
from app.application.use_case.field_service import FieldServiceUseCase
from app.infrastructure.field_service import PostgresFieldServiceRepository
from app.application.use_case.vision import VisionInspectionUseCase
from app.infrastructure.local_vision import OllamaVision
from app.application.use_case.sources import SourcesUseCase
from app.infrastructure.queries.sources import PostgresSourceQueries
import os

@dataclass(frozen=True)
class Services:
    auth: AuthService
    users: CreateUserUseCase
    issue_key: IssueKeyUseCase
    revoke_key: RevokeKeyUseCase
    catalogue: CatalogueCreateUseCase
    queries: AdminQueriesUseCase
    preview: PreviewInspectionUseCase
    inspections: InspectionsUseCase
    reporting: ReportingUseCase
    reviews: ReviewUseCase
    field_service: FieldServiceUseCase
    vision: VisionInspectionUseCase
    sources: SourcesUseCase

def create_services(*, session_factory, analysis_mode: str = "disabled") -> Services:
    if analysis_mode not in ("disabled", "mock"):
        raise ValueError("ANALYSIS_MODE must be disabled or mock")
    repository=Repository(session_factory)
    passwords=Passwords()
    queries = AdminQueries(session_factory)
    preview = PreviewInspectionUseCase(queries=queries, images=PillowImageDecoder(),
                                      model=MockModelAdapter() if analysis_mode == "mock" else None)
    records = PostgresInspectionRepository(session_factory)
    records.recover_stale()
    storage_backend, storages = photo_storages()
    review_queries = PostgresReviewQueries(session_factory)
    inspections = InspectionsUseCase(catalogue=queries, records=records,
                                    queries=PostgresInspectionQueries(session_factory, records), analyzer=preview,
                                    storage_backend=storage_backend, storages=storages, reviews=review_queries)
    field_service = FieldServiceUseCase(records=PostgresFieldServiceRepository(session_factory), catalogue=queries,
                                        inspections=inspections, inspection_records=records,
                                        inspection_queries=PostgresInspectionQueries(session_factory, records),
                                        images=PillowImageDecoder(), storage_backend=storage_backend, storages=storages)
    vision_url = os.getenv("VISION_BASE_URL")
    vision_model = OllamaVision(vision_url, os.getenv("VISION_MODEL", "qwen3-vl:2b-instruct")) if vision_url else None
    return Services(
        auth=AuthService(repository,passwords),
        users=CreateUserUseCase(users=repository,passwords=passwords),
        issue_key=IssueKeyUseCase(keys=repository),
        revoke_key=RevokeKeyUseCase(keys=repository),
        catalogue=CatalogueCreateUseCase(records=repository),
        queries=AdminQueriesUseCase(queries=AdminQueries(session_factory)),
        preview=preview,
        inspections=inspections,
        reporting=ReportingUseCase(records=PostgresReportingRepository(session_factory), queries=PostgresReportingQueries(session_factory)),
        reviews=ReviewUseCase(records=PostgresReviewRepository(session_factory), queries=review_queries),
        field_service=field_service,
        vision=VisionInspectionUseCase(field_service=field_service, inspections=inspections, records=records,
                                        images=PillowImageDecoder(), model=vision_model),
        sources=SourcesUseCase(PostgresSourceQueries(session_factory)),
    )
