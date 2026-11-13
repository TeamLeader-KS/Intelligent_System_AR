"""Prepare a verified, fixed official Ollama model cache before offline startup."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx

SUPPORTED = "qwen3-vl:2b-instruct"
REGISTRY = "https://registry.ollama.ai"
MANIFEST_URL = REGISTRY + "/v2/library/qwen3-vl/manifests/2b-instruct"
MANIFEST_SHA256 = "afc393e3572c07db0bc84aa460d928a16c75f3fbb9ca9e0dccc4fbd2dafb573e"
MANIFEST_PATH = "manifests/registry.ollama.ai/library/qwen3-vl/2b-instruct"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_MANIFEST = 65536
MAX_BLOB = 2_000_000_000


class PreparationError(Exception):
    """Public, sanitized preparation error, without signed URLs."""


def allowed_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.port not in (None, 443):
            return False
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            return False
        if parsed.hostname == "registry.ollama.ai":
            return True
        return bool(
            parsed.hostname
            and parsed.hostname.endswith(".r2.cloudflarestorage.com")
            and parse_qs(parsed.query).get("X-Amz-Signature")
        )
    except ValueError:
        return False


def fetch(client: httpx.Client, url: str, consume) -> None:
    """Follow only explicitly allowed official HTTPS redirects."""
    for _ in range(4):
        if not allowed_url(url):
            raise PreparationError("Недопустимое направление загрузки модели")
        try:
            with client.stream("GET", url, follow_redirects=False) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise PreparationError("Редирект без адреса")
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise PreparationError(f"Реестр модели ответил HTTP {response.status_code}")
                consume(response.iter_bytes(chunk_size=1024 * 1024))
                return
        except httpx.HTTPError:
            raise PreparationError("Ошибка HTTPS-загрузки официальной модели; повторите подготовку") from None
    raise PreparationError("Слишком много перенаправлений модели")


def decode_manifest(raw: bytes, expected_digest: str = MANIFEST_SHA256) -> list[dict]:
    if len(raw) > MAX_MANIFEST or hashlib.sha256(raw).hexdigest() != expected_digest:
        raise PreparationError("SHA256 манифеста не совпадает с закрепленной версией")
    try:
        manifest = json.loads(raw)
        blobs = [manifest["config"], *manifest["layers"]]
        if manifest["schemaVersion"] != 2 or len(blobs) != 5:
            raise ValueError()
        for blob in blobs:
            size = blob["size"]
            if not DIGEST.fullmatch(blob["digest"]) or type(size) is not int or not 0 < size <= MAX_BLOB:
                raise ValueError()
        if len({blob["digest"] for blob in blobs}) != len(blobs):
            raise ValueError()
        return blobs
    except (KeyError, TypeError, ValueError):
        raise PreparationError("Некорректный манифест модели") from None


def verified(path: Path, blob: dict) -> bool:
    if not path.is_file() or path.stat().st_size != blob["size"]:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == blob["digest"][7:]


def download_blob(client: httpx.Client, root: Path, blob: dict) -> None:
    destination = root / "blobs" / blob["digest"].replace(":", "-", 1)
    if verified(destination, blob):
        print(f"Кеш проверен: {blob['digest'][:19]}", flush=True)
        return
    partial = destination.with_suffix(".partial")
    digest = hashlib.sha256()
    count = 0
    destination.parent.mkdir(parents=True, exist_ok=True)

    def consume(chunks):
        nonlocal count
        with partial.open("wb") as output:
            for chunk in chunks:
                count += len(chunk)
                if count > blob["size"]:
                    raise PreparationError("Размер слоя превышает закрепленный размер")
                digest.update(chunk)
                output.write(chunk)
        if count != blob["size"] or digest.hexdigest() != blob["digest"][7:]:
            raise PreparationError("Проверка размера или SHA256 слоя не пройдена")

    try:
        fetch(client, REGISTRY + "/v2/library/qwen3-vl/blobs/" + blob["digest"], consume)
        partial.replace(destination)
        print(f"Слой проверен: {blob['digest'][:19]} ({count} байт)", flush=True)
    finally:
        partial.unlink(missing_ok=True)


def prepare(root: Path, client: httpx.Client) -> None:
    """Root is the models directory inside the mounted Ollama volume."""
    target = root / MANIFEST_PATH
    raw = None
    cached_manifest = False
    if target.is_file():
        with target.open("rb") as handle:
            candidate = handle.read(MAX_MANIFEST + 1)
        if hashlib.sha256(candidate).hexdigest() == MANIFEST_SHA256:
            raw = candidate
            cached_manifest = True
    if raw is None:
        chunks = bytearray()

        def consume(parts):
            for part in parts:
                if len(chunks) + len(part) > MAX_MANIFEST:
                    raise PreparationError("Слишком большой манифест модели")
                chunks.extend(part)

        fetch(client, MANIFEST_URL, consume)
        raw = bytes(chunks)
    blobs = decode_manifest(raw)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda blob: download_blob(client, root, blob), blobs))
    if not cached_manifest:
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_suffix(".partial")
        staging.write_bytes(raw)
        staging.replace(target)
    print(f"Модель {SUPPORTED} готова к работе без интернета", flush=True)


def main() -> int:
    import fcntl  # Runtime is a Linux Docker container on every supported host OS.

    if os.environ.get("IV_VISION_MODEL", SUPPORTED) != SUPPORTED:
        print(f"Автоподготовка поддерживает только {SUPPORTED}; другую модель подготовьте средствами Ollama", file=sys.stderr)
        return 1
    try:
        root = Path("/models")
        root.mkdir(parents=True, exist_ok=True)
        with (root / ".vision-prepare.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise PreparationError("Подготовка модели уже запущена") from None
            with httpx.Client(timeout=httpx.Timeout(120, connect=30), verify=True, follow_redirects=False) as client:
                prepare(root / "models", client)
        return 0
    except (PreparationError, OSError) as exc:
        # OSError messages may contain paths, but never signed download URLs.
        print(f"Подготовка модели не завершена: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
