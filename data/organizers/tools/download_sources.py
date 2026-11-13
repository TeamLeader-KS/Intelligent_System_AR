"""Restore pinned organizer originals with Python stdlib; never change manifests."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE = "https://disk.yandex.ru/d/CaiCoW791_PlJA"
DOWNLOAD_API = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
ALLOWED_HOSTS = {"cloud-api.yandex.net", "downloader.disk.yandex.ru"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE_BYTES = 100_000_000
MAX_TOTAL_BYTES = 500_000_000


class DownloadError(Exception):
    """Safe user-facing error without temporary signed URLs."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def allowed_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url)
        return (
            parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS
            and parts.port in (None, 443) and parts.username is None
            and parts.password is None and not parts.fragment
        )
    except ValueError:
        return False


def open_official(url: str):
    # Default HTTPS certificate verification stays enabled.
    opener = urllib.request.build_opener(NoRedirect())
    for _ in range(5):
        if not allowed_url(url):
            raise DownloadError("Загрузка направлена за пределы разрешенных HTTPS-серверов Яндекс Диска")
        try:
            return opener.open(urllib.request.Request(url, headers={"User-Agent": "IndustrialVision-organizer-materials/1"}), timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                url = urllib.parse.urljoin(url, exc.headers["Location"])
                exc.close()
                continue
            code = exc.code
            exc.close()
            raise DownloadError(f"Яндекс Диск ответил HTTP {code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise DownloadError("Ошибка HTTPS-соединения с Яндекс Диском; повторите запуск") from None
    raise DownloadError("Слишком много перенаправлений Яндекс Диска")


def target_path(entry: dict) -> Path:
    original = entry.get("original_path")
    if not isinstance(original, str) or not original.startswith("/") or original.startswith("//") or "\\" in original or "\x00" in original:
        raise DownloadError("Некорректный исходный путь в source-manifest.json")
    parts = PurePosixPath(original)
    if ".." in parts.parts or str(parts) != original or original == "/":
        raise DownloadError("Неканонический исходный путь в source-manifest.json")
    relative = "raw" + original
    if entry.get("file") != relative:
        raise DownloadError("Локальный и исходный пути в source-manifest.json не согласованы")
    root = BASE / "raw"
    target = BASE / relative
    if not root.resolve().is_relative_to(BASE.resolve()) or not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
        raise DownloadError("Путь материала выходит за пределы raw/")
    return target


def load_entries() -> list[dict]:
    manifest = json.loads((BASE / "source-manifest.json").read_text())
    if manifest.get("public_source") != PUBLIC_SOURCE:
        raise DownloadError("В манифесте указан другой публичный источник")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise DownloadError("Манифест материалов пуст")
    paths = set()
    total = 0
    for entry in entries:
        target_path(entry)
        size = entry.get("bytes")
        if type(size) is not int or not 0 < size <= MAX_FILE_BYTES or not SHA256.fullmatch(entry.get("sha256", "")):
            raise DownloadError("Неверный размер или SHA256 в source-manifest.json")
        if entry.get("public_source") != PUBLIC_SOURCE or entry["original_path"] in paths:
            raise DownloadError("Повторный путь или другой источник материала")
        paths.add(entry["original_path"])
        total += size
    if total > MAX_TOTAL_BYTES or total != manifest.get("total_bytes") or len(entries) != manifest.get("total_files"):
        raise DownloadError("Итоговые размеры или число файлов в манифесте не совпадают")
    return entries


def verified(target: Path, entry: dict) -> bool:
    if not target.is_file() or target.stat().st_size != entry["bytes"]:
        return False
    digest = hashlib.sha256()
    with target.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == entry["sha256"]


def restore(entry: dict, verify_only: bool) -> bool:
    target = target_path(entry)
    if verified(target, entry):
        print("ПРОВЕРЕН", entry["original_path"], flush=True)
        return True
    if verify_only:
        print("ОТСУТСТВУЕТ ИЛИ ПОВРЕЖДЁН", entry["original_path"], flush=True)
        return False
    query = urllib.parse.urlencode({"public_key": PUBLIC_SOURCE, "path": entry["original_path"]})
    with open_official(DOWNLOAD_API + "?" + query) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise DownloadError("Слишком большой ответ API Яндекс Диска")
    try:
        href = json.loads(raw)["href"]
        if not isinstance(href, str) or not allowed_url(href):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise DownloadError("API не вернул разрешённую ссылку на материал") from None
    target.parent.mkdir(parents=True, exist_ok=True)
    # Unique staging file prevents interrupted/parallel launches from publishing partial bytes.
    fd, name = tempfile.mkstemp(prefix=".organizer-", suffix=".partial", dir=target.parent)
    temporary = Path(name)
    try:
        digest = hashlib.sha256()
        count = 0
        with os.fdopen(fd, "wb") as output, open_official(href) as response:
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > entry["bytes"]:
                    raise DownloadError("Размер загрузки превышает закрепленный размер; исходный файл мог измениться")
                digest.update(chunk)
                output.write(chunk)
        if count != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
            raise DownloadError("Размер или SHA256 не совпал; материал не опубликован, проверьте актуальность манифеста")
        temporary.replace(target)
        print("ЗАГРУЖЕН И ПРОВЕРЕН", entry["original_path"], flush=True)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Проверить исходники без сети и изменений")
    parser.add_argument("--file", help="Один точный original_path из source-manifest.json, например /Температура/БД значений (температура).xlsx")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4, help="Число параллельных файлов: 1–4")
    arguments = parser.parse_args()
    try:
        entries = load_entries()
        if arguments.file:
            entries = [entry for entry in entries if entry["original_path"] == arguments.file]
            if not entries:
                raise DownloadError("Указанный путь отсутствует в закрепленном манифесте")
        with concurrent.futures.ThreadPoolExecutor(max_workers=arguments.workers) as pool:
            results = list(pool.map(lambda entry: restore(entry, arguments.verify_only), entries))
        print(f"Готово: проверено {sum(results)}/{len(entries)} файлов")
        return 0 if all(results) else 1
    except DownloadError as exc:
        print(f"Материалы не подготовлены: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError):
        # Never expose temporary signed URLs from low-level exceptions.
        print("Материалы не подготовлены: ошибка локального файла, манифеста или потока загрузки", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
