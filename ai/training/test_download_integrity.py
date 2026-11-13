import hashlib
import unittest

from download_public_smoke import verify


class DownloadIntegrityTests(unittest.TestCase):
    def test_lfs_and_git_blob_checksums(self):
        data = b"reviewed source file"
        lfs = {"path": "test.jpg", "size": len(data), "lfs": {"oid": hashlib.sha256(data).hexdigest()}}
        verify(data, lfs)
        blob = {"path": "test.txt", "size": len(data), "oid": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
        verify(data, blob)
        with self.assertRaisesRegex(ValueError, "Checksum"):
            verify(b"X" + data[1:], lfs)
        with self.assertRaisesRegex(ValueError, "Size"):
            verify(data + b"X", blob)


if __name__ == "__main__":
    unittest.main()
