import tempfile
import unittest
from pathlib import Path

from scripts.freeze_large_json import pack, sha256, verify_archive


class LargeJsonFreezeTests(unittest.TestCase):
    def test_deterministic_pack_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "registry.json"
            first = root / "first.json.gz"
            second = root / "second.json.gz"
            source.write_text('{"candidates":[1,2,3]}\n', encoding="utf-8")

            pack(source, first)
            pack(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            source_hash, source_bytes = sha256(source)
            archive_hash, archive_bytes = sha256(first)
            manifest = {
                "uncompressed": {
                    "sha256": source_hash,
                    "bytes": source_bytes,
                },
                "archive": {
                    "sha256": archive_hash,
                    "bytes": archive_bytes,
                },
            }
            status = verify_archive(first, manifest)
            self.assertEqual(status["uncompressed_sha256"], source_hash)
            self.assertEqual(status["archive_sha256"], archive_hash)


if __name__ == "__main__":
    unittest.main()
