import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from prepare_dataset import prepare, validate_manifest


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        samples = []
        for group, split in enumerate(("train", "val", "test")):
            for negative in (True, False):
                stem = f"{group}-{negative}"
                Image.new("RGB", (48, 48), (group * 60, int(negative) * 60, 90)).save(self.root / (stem + ".png"))
                (self.root / (stem + ".txt")).write_text("" if negative else "0 0.5 0.5 0.4 0.4\n")
                samples.append({"image": stem + ".png", "label": stem + ".txt", "equipment_group": str(group),
                                "origin": "real", "reviewed": True, "source_url": "internal://test",
                                "license": "test-fixture", "negative": negative, "split": split})
        self.data = {"classes": ["rust"], "samples": samples}
        self.path = self.root / "manifest.json"
        self.write()

    def write(self):
        self.path.write_text(json.dumps(self.data))

    def test_prepare_preserves_class_order_and_separates_groups(self):
        report = prepare(self.path, self.root / "prepared")
        self.assertEqual(len(report["samples"]), 6)
        self.assertEqual(json.loads((self.root / "prepared/data.yaml").read_text())["names"], ["rust"])
        self.assertEqual(report["counts"]["test"], {0: 1})
        with self.assertRaisesRegex(ValueError, "already exists"):
            prepare(self.path, self.root / "prepared")

    def test_rejects_duplicate_pixels_even_with_different_filename(self):
        (self.root / "1-True.png").write_bytes((self.root / "0-True.png").read_bytes())
        with self.assertRaisesRegex(ValueError, "Duplicate decoded"):
            validate_manifest(self.path)

    def test_automatic_split_is_reproducible_and_keeps_each_pump_together(self):
        for item in self.data["samples"]:
            item.pop("split")
        self.write()
        first = prepare(self.path, self.root / "first", seed=102)
        second = prepare(self.path, self.root / "second", seed=102)
        mapping = lambda report: {s["image"]: s["split"] for s in report["samples"]}
        self.assertEqual(mapping(first), mapping(second))
        self.assertEqual({s["split"] for s in first["samples"]}, {"train", "val", "test"})
        for group in ("0", "1", "2"):
            self.assertEqual(len({s["split"] for s in first["samples"] if s["equipment_group"] == group}), 1)

    def test_rejects_equipment_leakage(self):
        self.data["samples"][2]["equipment_group"] = "0"
        self.write()
        with self.assertRaisesRegex(ValueError, "leaks across splits"):
            validate_manifest(self.path)

    def test_rejects_synthetic_test_and_unreviewed_data(self):
        self.data["samples"][-1]["origin"] = "synthetic"
        self.write()
        with self.assertRaisesRegex(ValueError, "never validation/test"):
            validate_manifest(self.path)
        self.data["samples"][-1]["origin"] = "real"
        self.data["samples"][-1]["reviewed"] = False
        self.write()
        with self.assertRaisesRegex(ValueError, "Not human-reviewed"):
            validate_manifest(self.path)

    def test_rejects_invalid_boxes_and_false_negative(self):
        (self.root / "0-False.txt").write_text("0 0.9 0.5 0.8 0.8")
        with self.assertRaisesRegex(ValueError, "outside normalized"):
            validate_manifest(self.path)
        (self.root / "0-False.txt").write_text("")
        with self.assertRaisesRegex(ValueError, "negative must explicitly"):
            validate_manifest(self.path)

    def test_prepared_provenance_detects_changed_labels(self):
        output = self.root / "prepared"
        report = prepare(self.path, output)
        validate_manifest(output / "provenance.json")
        label = output / report["samples"][0]["label"]
        label.write_text("0 0.5 0.5 0.4 0.4")
        with self.assertRaisesRegex(ValueError, "Annotation changed"):
            validate_manifest(output / "provenance.json")


if __name__ == "__main__":
    unittest.main()
