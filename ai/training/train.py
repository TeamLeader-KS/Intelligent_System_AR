"""Train a candidate; evaluate once on held-out pumps; never replace the APK model."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Directory created by prepare_dataset.py")
    parser.add_argument("--weights", type=Path, required=True, help="Trusted original YOLO .pt checkpoint; never .tflite")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="cpu", help="cpu or CUDA device number; confirm working drivers first")
    parser.add_argument("--allow-new-head", action="store_true", help="Explicitly train a new class mapping; candidate is NOT a drop-in replacement")
    parser.add_argument("--export", action="store_true", help="Export candidate to .tflite; may download additional converter dependencies")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch < 1:
        parser.error("epochs and batch must be positive")
    if args.weights.suffix != ".pt" or not args.weights.is_file():
        parser.error("Provide the trusted original best.pt; .tflite is an inference artifact")
    if args.output.exists():
        parser.error("Output already exists; use a new experiment directory")
    provenance = json.loads((args.dataset / "provenance.json").read_text())
    config = json.loads((args.dataset / "data.yaml").read_text())
    if config["names"] != provenance["classes"]:
        parser.error("Dataset class mapping changed after preparation")
    if Path(config["path"]).resolve() != args.dataset.resolve() or any(config[split] != f"images/{split}" for split in ("train", "val", "test")):
        parser.error("Dataset paths changed after preparation; prepare a new dataset version")
    if len(provenance["samples"]) == 0:
        parser.error("Empty dataset")
    from prepare_dataset import validate_manifest
    validate_manifest((args.dataset / "provenance.json").resolve())
    # Imported only here, so dataset validation does not install PyTorch/CUDA.
    from ultralytics import YOLO
    model = YOLO(str(args.weights.resolve()))
    if model.task != "detect":
        parser.error("Only an object-detection checkpoint is supported")
    original_names = [model.names[i] for i in range(len(model.names))]
    if original_names != config["names"] and not args.allow_new_head:
        parser.error("Checkpoint and dataset class order differ. Get the original class mapping or explicitly allow a new head.")
    model.train(data=str((args.dataset / "data.yaml").resolve()), epochs=args.epochs, imgsz=640,
                batch=args.batch, device=args.device, workers=4, seed=102, deterministic=True,
                project=str(args.output.resolve().parent), name=args.output.name, exist_ok=False,
                patience=10, plots=True)
    best_path = Path(model.trainer.best)
    best = YOLO(str(best_path))
    metrics = best.val(data=str((args.dataset / "data.yaml").resolve()), split="test", imgsz=640,
                       batch=args.batch, device=args.device, workers=4, plots=True)
    result = {"status": "CANDIDATE_NOT_DEPLOYED", "classes": config["names"], "original_classes": original_names,
              "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(),
              "dataset_manifest_sha256": provenance["manifest_sha256"], "python": platform.python_version(),
              "ultralytics": importlib.metadata.version("ultralytics"), "torch": importlib.metadata.version("torch"),
              "epochs_requested": args.epochs, "metrics_test": {k: float(v) for k, v in metrics.results_dict.items()},
              "apk_compatible": False,
              "deployment_blockers": ["Check input/output tensor shapes and full class order", "Compare current/candidate on the same held-out real pumps", "Measure recall, false alarms and latency on the target phone", "Register a new SHA/version contract before installing"]}
    if args.export:
        result["export_path"] = str(best.export(format="tflite", imgsz=640, half=True, nms=False, batch=1))
    (args.output / "candidate-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    # Record exact resolved package versions; no claim that the unpinned platform wheel is portable.
    with (args.output / "environment-freeze.txt").open("w") as file:
        subprocess.run([sys.executable, "-m", "pip", "freeze"], stdout=file, check=True)
    print(f"Candidate saved to {args.output}. Current APK model has not been changed.")


if __name__ == "__main__":
    main()
