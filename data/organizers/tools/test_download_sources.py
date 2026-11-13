import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import download_sources as module


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = patch.object(module, "BASE", self.root)
        self.base.start()
        self.addCleanup(self.base.stop)
        self.payload = b"original organizer file"
        self.entry = {"original_path": "/unit.bin", "file": "raw/unit.bin", "bytes": len(self.payload), "sha256": hashlib.sha256(self.payload).hexdigest()}

    def mock_download(self, payload):
        return patch.object(module, "open_official", side_effect=[
            io.BytesIO(json.dumps({"href": "https://downloader.disk.yandex.ru/public-file"}).encode()),
            io.BytesIO(payload),
        ])

    def test_verified_cache_does_not_request_network(self):
        target = module.target_path(self.entry)
        target.parent.mkdir()
        target.write_bytes(self.payload)
        with patch.object(module, "open_official", side_effect=AssertionError("Network must not be used")):
            self.assertTrue(module.restore(self.entry, False))

    def test_verify_only_missing_file_does_not_write_or_connect(self):
        with patch.object(module, "open_official", side_effect=AssertionError("Network must not be used")):
            self.assertFalse(module.restore(self.entry, True))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_failed_checksum_preserves_existing_original(self):
        target = module.target_path(self.entry)
        target.parent.mkdir()
        target.write_bytes(b"existing local file")
        for payload in (b"x" * len(self.payload), b"x", self.payload + b"extra"):
            with self.subTest(length=len(payload)), self.mock_download(payload):
                with self.assertRaises(module.DownloadError):
                    module.restore(self.entry, False)
            self.assertEqual(target.read_bytes(), b"existing local file")
            self.assertEqual(list(target.parent.glob("*.partial")), [])

    def test_success_publishes_exact_file_without_staging_leftovers(self):
        with self.mock_download(self.payload):
            self.assertTrue(module.restore(self.entry, False))
        self.assertEqual(module.target_path(self.entry).read_bytes(), self.payload)
        self.assertEqual(list((self.root / "raw").iterdir()), [self.root / "raw/unit.bin"])

    def test_manifest_paths_cannot_escape_raw(self):
        for path in ("/../secret", "//secret", "/a/../../secret", "/a\\secret", "/"):
            with self.subTest(path=path), self.assertRaises(module.DownloadError):
                module.target_path({**self.entry, "original_path": path, "file": "raw" + path})

    def test_only_expected_https_servers_are_allowed(self):
        for url in ("file:///etc/passwd", "https://127.0.0.1/x", "http://downloader.disk.yandex.ru/x", "https://downloader.disk.yandex.ru.evil.test/x", "https://user@downloader.disk.yandex.ru/x", "https://downloader.disk.yandex.ru:444/x"):
            with self.subTest(url=url):
                self.assertFalse(module.allowed_url(url))
        self.assertTrue(module.allowed_url(module.DOWNLOAD_API))


if __name__ == "__main__":
    unittest.main()
