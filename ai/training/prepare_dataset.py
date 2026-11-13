"""Validate reviewed YOLO boxes and split by physical equipment, never by frames."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil

from PIL import Image, ImageOps

SPLITS = ("train", "val", "test")


def relative_file(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("Image/label paths must be nonempty paths relative to the manifest")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Missing file or path outside dataset: {value}")
    return path


def read_boxes(path: Path, classes: list[str]) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        values = line.split()
        if not values:
            continue
        if len(values) != 5:
            raise ValueError(f"{path.name}:{number}: expected class_id x_center y_center width height")
        if not values[0].isdigit():
            raise ValueError(f"{path.name}:{number}: class_id must be an integer")
        class_id = int(values[0])
        x, y, width, height = map(float, values[1:])
        if class_id >= len(classes) or not all(math.isfinite(v) for v in (x, y, width, height)):
            raise ValueError(f"{path.name}:{number}: invalid class or non-finite coordinate")
        if width <= 0 or height <= 0 or min(x-width/2, y-height/2) < -1e-6 or max(x+width/2, y+height/2) > 1+1e-6:
            raise ValueError(f"{path.name}:{number}: box lies outside normalized image")
        boxes.append((class_id, x, y, width, height))
    if len(set(boxes)) != len(boxes):
        raise ValueError(f"Duplicate box in {path.name}")
    return boxes


def validate_manifest(manifest_path: Path) -> tuple[dict, list[dict]]:
    data = json.loads(manifest_path.read_text())
    classes = data.get("classes", [])
    if not classes or not all(isinstance(name, str) and name.strip() for name in classes) or len(set(classes)) != len(classes):
        raise ValueError("classes must be an ordered list of distinct nonempty names")
    if not isinstance(data.get("samples"), list) or not data["samples"]:
        raise ValueError("No samples: collect and label real pump images first")
    seen_pixels: dict[str, str] = {}
    samples = []
    group_splits: dict[str, str] = {}
    for item in data["samples"]:
        name = item.get("image", "<unnamed>")
        if item.get("reviewed") is not True:
            raise ValueError(f"Not human-reviewed: {name}")
        if item.get("origin") not in ("real", "synthetic"):
            raise ValueError(f"Origin must be real/synthetic: {name}")
        if not item.get("source_url") or not item.get("license") or item["license"] == "UNVERIFIED":
            raise ValueError(f"Missing source/license: {name}")
        group = item.get("equipment_group")
        if not isinstance(group, str) or not group.strip():
            raise ValueError(f"Set equipment_group to the physical pump/source scene: {name}")
        image = relative_file(manifest_path.parent, name)
        label = relative_file(manifest_path.parent, item.get("label"))
        boxes = read_boxes(label, classes)
        label_digest = hashlib.sha256(label.read_bytes()).hexdigest()
        if item.get("label_sha256") not in (None, label_digest):
            raise ValueError(f"Annotation changed after preparation: {name}")
        if not isinstance(item.get("negative"), bool) or item["negative"] != (len(boxes) == 0):
            raise ValueError(f"negative must explicitly agree with empty/nonempty annotation: {name}")
        with Image.open(image) as raw:
            if raw.getexif().get(274, 1) != 1:
                raise ValueError(f"Normalize EXIF orientation before annotating: {name}")
            rgb = ImageOps.exif_transpose(raw).convert("RGB")
            if min(rgb.size) < 32:
                raise ValueError(f"Image too small: {name}")
            digest = hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
        if item.get("pixel_sha256") not in (None, digest):
            raise ValueError(f"Image changed after preparation: {name}")
        if digest in seen_pixels:
            raise ValueError(f"Duplicate decoded image: {name} and {seen_pixels[digest]}")
        seen_pixels[digest] = name
        split = item.get("split")
        if split is not None:
            if split not in SPLITS or group_splits.setdefault(group, split) != split:
                raise ValueError(f"Equipment group leaks across splits: {group}")
            if item["origin"] == "synthetic" and split != "train":
                raise ValueError(f"Synthetic images are never validation/test evidence: {name}")
        samples.append({**item, "image_path": image, "label_path": label,
                        "pixel_sha256": digest, "label_sha256": label_digest, "box_classes": [box[0] for box in boxes]})
    # If any split was fixed manually, every sample must have an explicit split.
    if group_splits and any(item.get("split") is None for item in samples):
        raise ValueError("Specify split for every sample, or leave all splits unset")
    return data, samples


def assign_splits(samples: list[dict], seed: int) -> None:
    if all(item.get("split") for item in samples):
        return
    synthetic = {item["equipment_group"] for item in samples if item["origin"] == "synthetic"}
    real = {item["equipment_group"] for item in samples if item["origin"] == "real"}
    if synthetic & real:
        raise ValueError("Real/synthetic variants of one scene must share a training-only group")
    groups = sorted(real, key=lambda group: hashlib.sha256(f"{seed}:{group}".encode()).digest())
    if len(groups) < 3:
        raise ValueError("Need at least three independent real equipment groups for train/val/test")
    n_val = max(1, round(len(groups) * 0.15))
    n_test = max(1, round(len(groups) * 0.15))
    mapping = {g: "test" if i < n_test else "val" if i < n_test+n_val else "train" for i, g in enumerate(groups)}
    mapping.update({g: "train" for g in synthetic})
    for item in samples:
        item["split"] = mapping[item["equipment_group"]]


def prepare(manifest_path: Path, output: Path, seed: int = 102) -> dict:
    data, samples = validate_manifest(manifest_path)
    assign_splits(samples, seed)
    if output.exists():
        raise ValueError("Output already exists; use a new versioned dataset directory")
    counts = {split: Counter(c for item in samples if item["split"] == split for c in item["box_classes"]) for split in SPLITS}
    for split in SPLITS:
        missing = [name for c, name in enumerate(data["classes"]) if counts[split][c] == 0]
        if missing:
            raise ValueError(f"{split}: no annotated examples for {missing}; collect more independent pumps or set reviewed splits")
        if not any(item["split"] == split and item["negative"] and item["origin"] == "real" for item in samples):
            raise ValueError(f"{split}: include reviewed real negative images, not only damaged surfaces")
    output.mkdir(parents=True)
    copied = []
    for split in SPLITS:
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)
    for item in samples:
        stem = item["pixel_sha256"]
        destination = Path("images") / item["split"] / (stem + item["image_path"].suffix.lower())
        shutil.copy2(item["image_path"], output / destination)
        shutil.copy2(item["label_path"], output / "labels" / item["split"] / (stem + ".txt"))
        copied.append({**{k: v for k, v in item.items() if not k.endswith("_path")},
                       "image": destination.as_posix(), "label": f"labels/{item['split']}/{stem}.txt"})
    config = {"path": str(output.resolve()), "train": "images/train", "val": "images/val", "test": "images/test", "names": data["classes"]}
    # JSON is a valid YAML subset and is accepted by the YOLO dataset reader.
    (output / "data.yaml").write_text(json.dumps(config, ensure_ascii=False, indent=2))
    report = {"seed": seed, "classes": data["classes"], "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "samples": copied, "counts": {s: dict(counts[s]) for s in SPLITS},
              "limitations": "Group separation and duplicate checks do not establish recognition quality; review near-duplicates manually."}
    (output / "provenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=102)
    args = parser.parse_args()
    try:
        report = prepare(args.manifest.resolve(), args.output.resolve(), args.seed)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Dataset not ready: {exc}\n")
    print(json.dumps({"samples": len(report["samples"]), "counts": report["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
