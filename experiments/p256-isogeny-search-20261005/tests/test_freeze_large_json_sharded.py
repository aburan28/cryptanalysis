import tempfile
import unittest
from pathlib import Path

from scripts.freeze_large_json_sharded import (
    materialize,
    pack_shards,
    shard_paths,
    verify_shards,
)


class ShardedLargeJsonFreezeTests(unittest.TestCase):
    def test_deterministic_pack_verify_and_materialize(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "registry.json"
            first_prefix = root / "first.json.gz"
            second_prefix = root / "second.json.gz"
            output = root / "materialized.json"
            source.write_bytes((b'{"candidates":[1,2,3]}\n' * 64) + b"\n")

            first = pack_shards(source, first_prefix, shard_bytes=8)
            second = pack_shards(source, second_prefix, shard_bytes=8)
            self.assertGreater(len(first["archive"]["shards"]), 1)
            self.assertEqual(
                [path.read_bytes() for path in shard_paths(first_prefix, first)],
                [path.read_bytes() for path in shard_paths(second_prefix, second)],
            )
            self.assertEqual(first["archive"]["sha256"], second["archive"]["sha256"])

            status = verify_shards(first_prefix, first)
            self.assertEqual(status["archive_shards"], len(first["archive"]["shards"]))
            materialize(first_prefix, first, output)
            self.assertEqual(output.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
