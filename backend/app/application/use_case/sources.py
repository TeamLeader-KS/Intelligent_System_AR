from app.application.contracts import Account
from app.application.ports.sources import SourceQueries
from app.domain.errors import Missing


class SourcesUseCase:
    def __init__(self, queries: SourceQueries):
        self.queries = queries

    def documents(self, actor: Account) -> dict:
        return {"items": self.queries.documents(actor)}

    def document(self, document_id: str, actor: Account) -> dict:
        result = self.queries.document(document_id, actor)
        if result is None:
            raise Missing("Документ не найден")
        return result

    def datasets(self, actor: Account) -> dict:
        return {"items": self.queries.datasets(actor)}

    def dataset(self, dataset_id: str, actor: Account, offset: int, limit: int) -> dict:
        result = self.queries.dataset(dataset_id, actor, offset, limit)
        if result is None:
            raise Missing("Набор справочных данных не найден")
        return result
