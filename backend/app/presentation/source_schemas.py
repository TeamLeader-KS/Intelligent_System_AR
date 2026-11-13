from typing import Literal

from pydantic import BaseModel, Field


class SourceDocumentOut(BaseModel):
    id: str
    name: str
    workshop_id: int
    original_path: str
    public_source: str
    bytes: int
    media_type: str
    details: dict
    sha256: str


class SourceDocumentsOut(BaseModel):
    items: list[SourceDocumentOut]


class ReferenceDatasetOut(BaseModel):
    id: str
    name: str
    workshop_id: int
    equipment_id: int | None
    document_id: str
    sheet: str
    headers: list[str]
    details: dict
    row_count: int


class ReferenceDatasetsOut(BaseModel):
    items: list[ReferenceDatasetOut]


class ReferenceRowsOut(ReferenceDatasetOut):
    rows: list[dict]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    data_origin: Literal["ORGANIZER_REFERENCE"]
    is_live_telemetry: Literal[False]
