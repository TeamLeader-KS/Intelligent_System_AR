from sqlalchemy import func, select

from app.application.contracts import Account
from app.infrastructure.models import ReferenceDataset, SourceDocument


class PostgresSourceQueries:
    def __init__(self, sessions):
        self.sessions = sessions

    @staticmethod
    def scoped(query, model, actor: Account):
        if actor.role != "ADMIN":
            query = query.where(model.workshop_id == actor.workshop_id)
        return query

    @staticmethod
    def document_dict(row: SourceDocument) -> dict:
        return {"id": row.id, "name": row.name, "workshop_id": row.workshop_id,
                "original_path": row.original_path, "public_source": row.public_source,
                "bytes": row.bytes, "media_type": row.media_type, "details": row.details,
                "sha256": row.id}

    def documents(self, actor: Account) -> list[dict]:
        query = self.scoped(select(SourceDocument).order_by(SourceDocument.original_path), SourceDocument, actor)
        with self.sessions() as db:
            return [self.document_dict(row) for row in db.scalars(query.limit(500))]

    def document(self, document_id: str, actor: Account) -> dict | None:
        query = self.scoped(select(SourceDocument).where(SourceDocument.id == document_id), SourceDocument, actor)
        with self.sessions() as db:
            row = db.scalar(query)
            return {**self.document_dict(row), "source_path": row.source_path} if row else None

    def datasets(self, actor: Account) -> list[dict]:
        # Do not load every reference row merely to display the dataset list.
        query = select(ReferenceDataset.id, ReferenceDataset.name, ReferenceDataset.workshop_id,
                       ReferenceDataset.equipment_id, ReferenceDataset.document_id, ReferenceDataset.sheet,
                       ReferenceDataset.headers, ReferenceDataset.details,
                       func.jsonb_array_length(ReferenceDataset.rows).label("row_count"))
        query = self.scoped(query, ReferenceDataset, actor).order_by(ReferenceDataset.id)
        with self.sessions() as db:
            return [dict(row) for row in db.execute(query.limit(100)).mappings()]

    def dataset(self, dataset_id: str, actor: Account, offset: int, limit: int) -> dict | None:
        query = self.scoped(select(ReferenceDataset).where(ReferenceDataset.id == dataset_id), ReferenceDataset, actor)
        with self.sessions() as db:
            row = db.scalar(query)
            if row is None:
                return None
            return {"id": row.id, "name": row.name, "workshop_id": row.workshop_id,
                    "equipment_id": row.equipment_id, "document_id": row.document_id,
                    "sheet": row.sheet, "headers": row.headers, "details": row.details,
                    "row_count": len(row.rows), "offset": offset, "limit": limit,
                    "rows": row.rows[offset:offset + limit], "data_origin": "ORGANIZER_REFERENCE",
                    "is_live_telemetry": False}
