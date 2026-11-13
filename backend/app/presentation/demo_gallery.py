"""Public, local-only demonstration gallery. Images remain local files with attribution."""
from pathlib import Path
import json
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_FIELDS = {"name": 200, "description": 4000, "source_url": 2000,
           "author": 400, "license": 200, "license_url": 2000}


def _image_path(directory: Path, filename: str) -> Path:
    if not isinstance(filename, str) or not filename or "\\" in filename or "\x00" in filename or Path(filename).name != filename:
        raise HTTPException(503, "В каталоге примеров указан недопустимый путь изображения")
    path = directory / filename
    if path.suffix.lower() not in _TYPES or path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise HTTPException(503, "В каталоге примеров указан недопустимый файл изображения")
    if not path.is_file():
        raise HTTPException(503, "Изображения примеров ещё не подготовлены")
    return path


def _entries(directory: Path) -> list[dict]:
    if directory.is_symlink() or (directory / "manifest.json").is_symlink():
        raise HTTPException(503, "Каталог примеров не должен содержать символические ссылки")
    try:
        with (directory / "manifest.json").open("rb") as source:
            raw = source.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("manifest too large")
        manifest = json.loads(raw)
    except FileNotFoundError:
        raise HTTPException(503, "Примеры насосов ещё не подготовлены") from None
    except (OSError, ValueError, UnicodeError):
        raise HTTPException(503, "Не удалось прочитать каталог примеров насосов") from None
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    if not isinstance(entries, list) or not entries or len(entries) > 100:
        raise HTTPException(503, "Каталог примеров насосов пуст или имеет неверный формат")
    ids = set()
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not _ID.fullmatch(entry["id"]) or entry["id"] in ids:
            raise HTTPException(503, "В каталоге примеров неверный или повторный идентификатор")
        if not isinstance(entry.get("synthetic"), bool) or any(not isinstance(entry.get(name), str) or len(entry[name]) > limit for name, limit in _FIELDS.items()):
            raise HTTPException(503, "В каталоге примеров отсутствуют сведения об изображении и его источнике")
        if not entry["name"].strip():
            raise HTTPException(503, "В каталоге примеров отсутствует название изображения")
        for name, limit in (("inventory_number", 80), ("serial_number", 120)):
            value = entry.get(name)
            if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > limit):
                raise HTTPException(503, "В каталоге примеров неверная учебная маркировка")
        for name, count, limit in (("expected_observations", 20, 500), ("case_groups", 10, 100)):
            values = entry.get(name, [])
            if not isinstance(values, list) or len(values) > count or any(not isinstance(value, str) or len(value) > limit for value in values):
                raise HTTPException(503, "В каталоге примеров неверное описание учебного сценария")
        if entry.get("plate_position", "bottom-right") not in ("bottom-right", "bottom-left", "top-right", "top-left"):
            raise HTTPException(503, "В каталоге примеров неверное положение учебного шильдика")
        _image_path(directory, entry.get("file"))
        ids.add(entry["id"])
        result.append(entry)
    return result


def register_demo_gallery(app: FastAPI, root_path: str, cv_example: str | Path | None,
                          frontend_path: Path) -> None:
    """Register only when local demo assets are explicitly enabled in the environment."""
    if not cv_example:
        return
    directory = Path(cv_example).parent / "pumps"
    frontend_index = frontend_path / "index.html" if frontend_path.is_dir() else frontend_path

    @app.get("/api/v1/demo-pumps", include_in_schema=False)
    def pump_gallery_metadata():
        return {"items": [{"id": entry["id"], **{name: entry[name] for name in _FIELDS},
                            "synthetic": entry["synthetic"],
                            "inventory_number": entry.get("inventory_number"), "serial_number": entry.get("serial_number"),
                            "expected_observations": entry.get("expected_observations", []), "case_groups": entry.get("case_groups", []),
                            "plate_position": entry.get("plate_position", "bottom-right"),
                            "qr_url": f"{root_path}/demo-pumps/{entry['id']}/qr.svg",
                            "image_url": f"{root_path}/demo-pumps/{entry['id']}/image"}
                           for entry in _entries(directory)]}

    @app.get("/demo-pumps", include_in_schema=False)
    def pump_gallery_page():
        if not frontend_index.is_file():
            raise HTTPException(503, "Интерфейс галереи ещё не собран")
        return FileResponse(frontend_index, media_type="text/html")

    @app.get("/demo-pumps/{sample_id}/image", include_in_schema=False)
    def pump_gallery_image(sample_id: str):
        if not _ID.fullmatch(sample_id):
            raise HTTPException(404, "Пример насоса не найден")
        entry = next((entry for entry in _entries(directory) if entry["id"] == sample_id), None)
        if entry is None:
            raise HTTPException(404, "Пример насоса не найден")
        path = _image_path(directory, entry["file"])
        return FileResponse(path, media_type=_TYPES[path.suffix.lower()])

    @app.get("/demo-pumps/{sample_id}/qr.svg", include_in_schema=False)
    def pump_gallery_qr(sample_id: str):
        if not _ID.fullmatch(sample_id):
            raise HTTPException(404, "Пример насоса не найден")
        entry = next((entry for entry in _entries(directory) if entry["id"] == sample_id), None)
        if entry is None:
            raise HTTPException(404, "Пример насоса не найден")
        path = directory / f"{sample_id}-qr.svg"
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise HTTPException(503, "Учебный QR содержит недопустимый путь")
        if not path.is_file() and not entry.get("inventory_number"):
            # Legacy samples without individual demo cards use the existing demo identifier.
            path = Path(cv_example).parent / "pump-qr.svg"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 262144:
            raise HTTPException(503, "Учебный QR этого примера ещё не подготовлен")
        return FileResponse(path, media_type="image/svg+xml", headers={
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff"})
