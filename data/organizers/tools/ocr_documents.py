"""Offline OCR of organizer scans; original documents remain read-only."""
from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import shutil
import statistics
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

INPUT = Path("/input")
OUTPUT = Path("/output")
LOCK = threading.Lock()
DPI = 200
WORKERS = 4


def run(arguments: list[str]) -> str:
    result = subprocess.run(arguments, check=True, text=True, capture_output=True, timeout=180)
    return result.stdout


def publish(record: dict) -> None:
    with LOCK:
        path = OUTPUT / "ocr-manifest.json"
        manifest = json.loads(path.read_text()) if path.exists() else {
            "publisher_origin": "ORGANIZER_DOCUMENT",
            "method": "pdftoppm 200 DPI; Tesseract rus+eng --psm 3",
            "warning": "OCR text is a search aid. Every numeric fact needs visual comparison against the cited original PDF page.",
            "confidence_definition": "Unweighted mean of nonnegative Tesseract word confidences, 0–100; not factual accuracy.",
            "entries": [],
        }
        manifest["entries"] = [item for item in manifest["entries"] if item["source_file"] != record["source_file"]] + [record]
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        staging = path.with_suffix(".json.partial")
        staging.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        staging.replace(path)


def ocr(source: Path) -> dict:
    relative = source.relative_to(INPUT)
    target = OUTPUT / relative.parent / (source.name + ".txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    info = run(["pdfinfo", str(source)])
    pages = int(next(line.split(":", 1)[1].strip() for line in info.splitlines() if line.startswith("Pages:")))
    page_records = []
    texts = []
    with tempfile.TemporaryDirectory(prefix="organizer-ocr-") as temporary:
        temporary = Path(temporary)
        for number in range(1, pages + 1):
            image = temporary / "page"
            run(["pdftoppm", "-f", str(number), "-l", str(number), "-r", str(DPI), "-singlefile", "-png", str(source), str(image)])
            image = image.with_suffix(".png")
            result = temporary / "result"
            run(["tesseract", str(image), str(result), "-l", "rus+eng", "--psm", "3", "txt", "tsv"])
            texts.append(result.with_suffix(".txt").read_text())
            with result.with_suffix(".tsv").open() as handle:
                words = [row for row in csv.DictReader(handle, delimiter="\t") if row.get("text", "").strip() and float(row["conf"]) >= 0]
            confidences = [float(word["conf"]) for word in words]
            page_records.append({"page": number, "word_count": len(words), "mean_word_confidence": round(statistics.mean(confidences), 2) if confidences else None, "needs_manual_review": True})
            if number == 1 and source.name in ("1) Насос №1 ПС.pdf", "2) Редукт, ЭД, ТПП №1 ПС.pdf"):
                qa = OUTPUT / "qa"
                qa.mkdir(exist_ok=True)
                shutil.copyfile(image, qa / (source.stem + "-page-001.png"))
            image.unlink()
            result.with_suffix(".txt").unlink()
            result.with_suffix(".tsv").unlink()
    staging = target.with_suffix(target.suffix + ".partial")
    staging.write_text("\f".join(texts))
    staging.replace(target)
    record = {"source_file": "raw/" + relative.as_posix(), "source_sha256": sha256, "text_file": target.relative_to(OUTPUT).as_posix(), "publisher_origin": "ORGANIZER_DOCUMENT", "pages": pages, "page_indexing": "1-based", "dpi": DPI, "needs_manual_review": True, "completed_at": datetime.now(timezone.utc).isoformat(), "page_results": page_records}
    publish(record)
    print("OCR_COMPLETE", str(relative), pages, len("".join(texts)), flush=True)
    return record


def main() -> None:
    manifest = json.loads((OUTPUT / "extraction-manifest.json").read_text())
    sources = [INPUT / entry["source_file"].removeprefix("raw/") for entry in manifest["entries"] if entry.get("needs_ocr")]
    sources.sort(key=lambda path: (not path.name.startswith(("1)", "2)")), path.name))
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(ocr, sources))
    print("OCR_FINISHED", len(sources), flush=True)


if __name__ == "__main__":
    main()
