import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import vision_prepare as module


class PrepareTests(unittest.TestCase):
    def test_only_official_signed_https_redirects(self):
        for url in (
            "http://registry.ollama.ai/x", "https://registry.ollama.ai.evil.test/x",
            "https://evil.test/x", "https://registry.ollama.ai:444/x",
            "https://user@registry.ollama.ai/x",
            "https://r2.cloudflarestorage.com/x?X-Amz-Signature=a",
            "https://bucket.r2.cloudflarestorage.com/x",
        ):
            with self.subTest(url=url):
                self.assertFalse(module.allowed_url(url))
        self.assertTrue(module.allowed_url(module.MANIFEST_URL))
        self.assertTrue(module.allowed_url("https://bucket.r2.cloudflarestorage.com/x?X-Amz-Signature=abc"))

    def test_pin_rejects_modified_manifest(self):
        with self.assertRaises(module.PreparationError):
            module.decode_manifest(b"{}")

    def test_redirect_to_private_or_untrusted_host_rejected(self):
        seen = []

        def response(request):
            seen.append(str(request.url))
            return httpx.Response(302, headers={"location": "https://127.0.0.1/secret"})

        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            with self.assertRaises(module.PreparationError):
                module.fetch(client, module.MANIFEST_URL, lambda _: None)
        self.assertEqual(len(seen), 1)

    def test_failure_does_not_publish_blob(self):
        for body in (b"wrong", b"too large payload", b"x"):
            blob = {"digest": "sha256:" + hashlib.sha256(b"hello").hexdigest(), "size": 5}
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
                    with self.assertRaises(module.PreparationError):
                        module.download_blob(client, root, blob)
                self.assertEqual(list((root / "blobs").iterdir()), [])

    def test_verified_cache_requires_no_network_and_is_rechecked(self):
        blobs = [{"digest": "sha256:" + hashlib.sha256(bytes([i])).hexdigest(), "size": 1} for i in range(5)]
        raw = json.dumps({"schemaVersion": 2, "config": blobs[0], "layers": blobs[1:]}).encode()
        pin = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / module.MANIFEST_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            (root / "blobs").mkdir()
            for i, blob in enumerate(blobs):
                (root / "blobs" / blob["digest"].replace(":", "-")).write_bytes(bytes([i]))
            with patch.object(module, "MANIFEST_SHA256", pin), patch.object(module, "decode_manifest", lambda value: blobs):
                with httpx.Client(transport=httpx.MockTransport(lambda _: self.fail("Unexpected network access"))) as client:
                    module.prepare(root, client)
            self.assertEqual(target.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
