import hashlib
import io
import json
import stat
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
        self.assertEqual(stat.S_IMODE(module.target_path(self.entry).stat().st_mode), 0o644)

    def test_valid_seed_copies_without_network_and_publishes_readable_file(self):
        seed = self.root / "seed"
        seed.mkdir()
        (seed / "unit.bin").write_bytes(self.payload)
        (seed / "unit.bin").chmod(0o600)
        with patch.object(module, "open_official", side_effect=AssertionError("Network must not be used")):
            self.assertTrue(module.restore(self.entry, False, seed))
        target = module.target_path(self.entry)
        self.assertEqual(target.read_bytes(), self.payload)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE((seed / "unit.bin").stat().st_mode), 0o600)

    def test_invalid_seed_falls_back_to_official_download(self):
        seed = self.root / "seed"
        seed.mkdir()
        (seed / "unit.bin").write_bytes(b"x" * len(self.payload))
        with self.mock_download(self.payload) as network:
            self.assertTrue(module.restore(self.entry, False, seed))
        self.assertEqual(network.call_count, 2)
        self.assertEqual(module.target_path(self.entry).read_bytes(), self.payload)

    def test_seed_directory_symlink_escape_is_not_used(self):
        seed = self.root / "seed"
        outside = self.root / "outside"
        seed.mkdir()
        outside.mkdir()
        (outside / "unit.bin").write_bytes(self.payload)
        (seed / "sub").symlink_to(outside, target_is_directory=True)
        entry = {**self.entry, "original_path": "/sub/unit.bin", "file": "raw/sub/unit.bin"}
        with self.mock_download(self.payload) as network:
            self.assertTrue(module.restore(entry, False, seed))
        self.assertEqual(network.call_count, 2)

    def test_seed_leaf_symlink_is_not_used(self):
        seed = self.root / "seed"
        seed.mkdir()
        (self.root / "outside.bin").write_bytes(self.payload)
        (seed / "unit.bin").symlink_to(self.root / "outside.bin")
        with self.mock_download(self.payload) as network:
            self.assertTrue(module.restore(self.entry, False, seed))
        self.assertEqual(network.call_count, 2)

    def test_seed_mutation_between_verification_and_copy_is_rechecked(self):
        seed = self.root / "seed"
        seed.mkdir()
        source = seed / "unit.bin"
        source.write_bytes(self.payload)
        original_publish = module.publish_stream
        count = 0

        def publish(stream, target, entry):
            nonlocal count
            count += 1
            if count == 1:
                source.write_bytes(b"x" * len(self.payload))
            return original_publish(stream, target, entry)

        with patch.object(module, "publish_stream", side_effect=publish), self.mock_download(self.payload) as network:
            self.assertTrue(module.restore(self.entry, False, seed))
        self.assertEqual(network.call_count, 2)
        self.assertEqual(module.target_path(self.entry).read_bytes(), self.payload)
        self.assertEqual(list((self.root / "raw").glob("*.partial")), [])

    def test_verify_only_ignores_seed_and_preserves_existing_permissions(self):
        seed = self.root / "seed"
        seed.mkdir()
        (seed / "unit.bin").write_bytes(self.payload)
        with patch.object(module, "restore_seed", side_effect=AssertionError("Seed must not be accessed")), patch.object(module, "open_official", side_effect=AssertionError("Network must not be used")):
            self.assertFalse(module.restore(self.entry, True, seed))
        self.assertFalse((self.root / "raw").exists())
        target = module.target_path(self.entry)
        target.parent.mkdir()
        target.write_bytes(self.payload)
        target.chmod(0o600)
        self.assertTrue(module.restore(self.entry, True, seed))
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_verified_existing_public_file_becomes_readable_without_network(self):
        target = module.target_path(self.entry)
        target.parent.mkdir()
        target.write_bytes(self.payload)
        target.chmod(0o600)
        with patch.object(module, "open_official", side_effect=AssertionError("Network must not be used")):
            self.assertTrue(module.restore(self.entry, False))
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_unverified_existing_file_permissions_are_not_relaxed(self):
        target = module.target_path(self.entry)
        target.parent.mkdir()
        target.write_bytes(b"unverified local content")
        target.chmod(0o600)
        with self.mock_download(b"wrong"):
            with self.assertRaises(module.DownloadError):
                module.restore(self.entry, False)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_manifest_paths_cannot_escape_raw(self):
        for path in ("/../secret", "//secret", "/a/../../secret", "/a\\secret", "/"):
            with self.subTest(path=path), self.assertRaises(module.DownloadError):
                module.target_path({**self.entry, "original_path": path, "file": "raw" + path})

    def test_only_expected_https_servers_are_allowed(self):
        for url in ("file:///etc/passwd", "https://127.0.0.1/x", "http://downloader.disk.yandex.ru/x", "https://downloader.disk.yandex.ru.evil.test/x", "https://user@downloader.disk.yandex.ru/x", "https://downloader.disk.yandex.ru:444/x"):
            with self.subTest(url=url):
                self.assertFalse(module.allowed_url(url))
        self.assertTrue(module.allowed_url(module.DOWNLOAD_API))
        self.assertTrue(module.allowed_url("https://mds.storage.yandex.net/verified-public-object"))
        self.assertFalse(module.allowed_url("https://mds.storage.yandex.net.evil.test/x"))


if __name__ == "__main__":
    unittest.main()
