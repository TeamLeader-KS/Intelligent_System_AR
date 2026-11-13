"""Fetch a small attributed YOLO corrosion smoke set; not a pump-quality benchmark."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

REPO = "LibreYOLO/corrosion-bi3q3"
SOURCE = "https://huggingface.co/datasets/" + REPO
MAX_FILE_BYTES = 8 * 1024 * 1024


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        content = response.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("Unexpectedly large remote file")
    return content


def verify(content: bytes, entry: dict) -> None:
    if len(content) != entry["size"]:
        raise ValueError(f"Size differs from source metadata: {entry['path']}")
    if "lfs" in entry:
        digest = hashlib.sha256(content).hexdigest()
        expected = entry["lfs"]["oid"]
    else:
        digest = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        expected = entry["oid"]
    if digest != expected:
        raise ValueError(f"Checksum differs from source metadata: {entry['path']}")


def download(output: Path, count: int, split: str = "test") -> dict:
    metadata = json.loads(fetch("https://huggingface.co/api/datasets/" + REPO))
    revision = metadata["sha"]
    tree = []
    for directory in ("images", "labels"):
        tree.extend(json.loads(fetch(f"https://huggingface.co/api/datasets/{REPO}/tree/{revision}/{split}/{directory}?limit=1000")))
    tree.extend(json.loads(fetch(f"https://huggingface.co/api/datasets/{REPO}/tree/{revision}?limit=100")))
    entries = {entry["path"]: entry for entry in tree if entry["type"] == "file"}
    images = sorted(path for path in entries if path.startswith(split+"/images/"))[:count]
    if len(images) != count:
        raise ValueError("Requested sample is not present in source tree")
    files = []
    samples = []
    for image in images:
        label = split+"/labels/" + Path(image).with_suffix(".txt").name
        if label not in entries:
            raise ValueError(f"No matching source label for {image}")
        files.extend((image, label))
        samples.append({"image": image, "label": label, "source_url": SOURCE + "/resolve/" + revision + "/" + image,
                        "license": "CC BY 4.0", "origin": "real", "reviewed": False,
                        "equipment_group": "UNREVIEWED_SOURCE_SCENE", "split": split})
    files.extend(name for name in ("README.md", "README.roboflow.txt", "data.yaml") if name in entries)
    output.mkdir(parents=True, exist_ok=True)

    def save(path: str) -> dict:
        if ".." in Path(path).parts:
            raise ValueError("Invalid remote path")
        target = output / path
        content = target.read_bytes() if target.exists() else fetch(SOURCE + "/resolve/" + revision + "/" + quote(path))
        verify(content, entries[path])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return {"path": path, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        checksums = list(pool.map(save, files))
    report = {"source": SOURCE, "original_source": "https://universe.roboflow.com/roboflow-100/corrosion-bi3q3/dataset/1",
              "revision": revision, "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
              "attribution": "Roboflow 100 benchmark; publisher Roboflow 100, mirror LibreYOLO. See included upstream READMEs and source URL.",
              "classes": ["Slippage", "corrosion", "crack"],
              "samples": samples, "files": checksums, "upstream_split": split,
              "purpose": "General corrosion inference/annotation smoke set only" if split == "test" else "General corrosion CPU training pipeline smoke input only",
              "limitations": ["Not pump-specific; physical-equipment groups and negatives not reviewed",
                              "Do not train on this held-out smoke set" if split == "test" else "Training pipeline smoke only; preserve the independent upstream test set",
                              "Not evidence of pump field accuracy or fine-grained pitting recognition"]}
    (output / "source-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, default=24, choices=range(1, 106), metavar="1..105")
    parser.add_argument("--split", choices=("train", "valid", "test"), default="test")
    args = parser.parse_args()
    report = download(args.output, args.count, args.split)
    print(f"Downloaded {len(report['samples'])} image/label pairs; inspect source-manifest.json before use.")


if __name__ == "__main__":
    main()
