import hashlib
from pathlib import Path

from app.domain.errors import Missing


def read_source_file(directory: Path, document: dict) -> bytes:
    """Read the authorized original once; serve the same bytes that were verified."""
    root = directory.resolve()
    relative = Path(document["source_path"])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "raw":
        raise Missing("Оригинал документа недоступен")
    path = (root / relative).resolve()
    if not path.is_relative_to(root / "raw"):
        raise Missing("Оригинал документа недоступен")
    try:
        with path.open("rb") as stream:
            content = stream.read(document["bytes"] + 1)
    except OSError:
        raise Missing("Оригинал отсутствует. Восстановите материалы организаторов по инструкции запуска") from None
    if len(content) != document["bytes"] or hashlib.sha256(content).hexdigest() != document["sha256"]:
        raise Missing("Контрольная сумма оригинала не совпадает; файл не выдан")
    return content
