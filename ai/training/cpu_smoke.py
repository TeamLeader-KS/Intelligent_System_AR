"""Real tiny fine-tune to exercise the pipeline, explicitly not an accuracy claim."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="ai/ mounted read-only")
    parser.add_argument("output", type=Path)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--evaluate-test", action="store_true", help="Evaluate held-out upstream test once, after selecting best by validation")
    args = parser.parse_args()
    if not 1 <= args.epochs <= 100 or not 1 <= args.patience <= 20:
        parser.error("epochs must be 1..100 and patience 1..20")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Output must be empty; never overwrite an existing experiment")
    args.output.mkdir(parents=True, exist_ok=True)
    counts = {}
    image_hashes = set()
    splits = [("train", "train"), ("valid", "val")]
    if args.evaluate_test:
        splits.append(("test", "test"))
    for source_split, target in splits:
        source = args.input / "dataset" / ("public-corrosion-smoke" if source_split == "test" else "public-corrosion-" + source_split)
        metadata = json.loads((source / "source-manifest.json").read_text())
        if metadata.get("upstream_split", "test") != source_split or metadata["classes"] != ["Slippage", "corrosion", "crack"]:
            parser.error("Unexpected source taxonomy or split")
        for directory in ("images", "labels"):
            (args.output / "data" / directory / target).mkdir(parents=True)
        included = 0
        expected = {item["path"]: item["sha256"] for item in metadata["files"]}
        for sample in metadata["samples"]:
            label_bytes = (source / sample["label"]).read_bytes()
            if hashlib.sha256(label_bytes).hexdigest() != expected[sample["label"]]:
                parser.error("Source annotation changed after download")
            label = [line for line in label_bytes.decode().splitlines() if line.strip()]
            # Do not silently discard other object classes in a mixed-label image.
            if not label or any(line.split()[0] != "1" for line in label if line.strip()):
                continue
            image = source / sample["image"]
            content = image.read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            if sha != expected[sample["image"]]:
                parser.error("Source image changed after download")
            if sha in image_hashes:
                parser.error("Duplicate image across train/validation smoke input")
            image_hashes.add(sha)
            shutil.copy2(image, args.output / "data/images" / target / image.name)
            remapped = ["0 " + " ".join(line.split()[1:]) for line in label if line.strip()]
            (args.output / "data/labels" / target / (image.stem + ".txt")).write_text("\n".join(remapped)+"\n")
            included += 1
        counts[target] = included
        if included < 2:
            parser.error(f"Not enough single-corrosion examples in {source_split}")
    data = args.output / "data/data.yaml"
    config = {"path": str((args.output / 'data').resolve()), "train": "images/train", "val": "images/val", "names": ["Corrosion"]}
    if args.evaluate_test:
        config["test"] = "images/test"
    data.write_text(json.dumps(config))
    # Dataset validation requests Arial even with plots disabled; provide an offline font.
    font_dir = Path(os.environ.get("YOLO_CONFIG_DIR", "/tmp/ultralytics"))
    font_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_dir / "Arial.ttf")
    from ultralytics import YOLO
    import torch
    torch.set_num_threads(4)
    weights = args.input / "candidates/spiderbot/v1_yolov8n.pt"
    assert hashlib.sha256(weights.read_bytes()).hexdigest() == "23616c79be9487c96a4230c11285414b9377544320775c68843afee9b15f2cd4"
    baseline = YOLO(str(weights))
    before = baseline.val(data=str(data), split="val", imgsz=320, batch=2, device="cpu", workers=0,
                          plots=False, project=str(args.output), name="baseline-val")
    baseline_metrics = {k: float(v) for k, v in before.results_dict.items()}
    del baseline
    model = YOLO(str(weights))
    if model.task != "detect" or model.names != {0: "Corrosion"}:
        parser.error("Unexpected candidate checkpoint contract")
    model.train(data=str(data), epochs=args.epochs, imgsz=320, batch=2, device="cpu", workers=0,
                seed=102, deterministic=True, amp=False, plots=False, cache=False,
                project=str(args.output), name="run", exist_ok=False, pretrained=True,
                save=True, val=True, mosaic=0, fliplr=0, patience=args.patience)
    best = YOLO(str(model.trainer.best))
    after = best.val(data=str(data), split="val", imgsz=320, batch=2, device="cpu", workers=0,
                     plots=False, project=str(args.output), name="candidate-val")
    report = {"status": "GENERAL_CORROSION_CANDIDATE_NOT_DEPLOYED", "epochs_requested": args.epochs,
              "input_counts": counts, "classes": ["Corrosion"], "imgsz": 320,
              "baseline_validation": baseline_metrics, "candidate_validation": {k: float(v) for k, v in after.results_dict.items()},
              "new_weights": str(Path(model.trainer.best)), "torch": torch.__version__,
              "limitations": ["General corrosion surfaces, not a pump-specific dataset", "Upstream physical equipment grouping and original pretrained-model data overlap unknown", "Only source corrosion class 1 remapped to model class 0; mixed-class images excluded", "No field-quality improvement claim; no target pump test", "Current APK TFLite unchanged; candidate output shape/class order incompatible"]}
    if args.evaluate_test:
        test_metrics = best.val(data=str(data), split="test", imgsz=320, batch=2, device="cpu", workers=0,
                                plots=False, project=str(args.output), name="final-test")
        report["test_after_selection"] = {k: float(v) for k, v in test_metrics.results_dict.items()}
    (args.output / "smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("Actual CPU epoch completed; this is a pipeline smoke run, not proof of improved pump recognition.")


if __name__ == "__main__":
    main()
