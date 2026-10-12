#!/usr/bin/env python3
"""Boundary checks for the frozen equal-B stream and scalar laws."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from freeze_inputs import control_indices, scalar_sequence, scan_prefix  # noqa: E402
from preflight import CONFIG, load_json, sha256, validate  # noqa: E402


class EqualBInputTests(unittest.TestCase):
    def test_prefix_boundary_and_monotonicity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "masks.bin.gz"
            raw = b"".join(struct.pack("<I", value) for value in (1, 3, 5, 7))
            with gzip.open(path, "wb") as stream:
                stream.write(raw)
            archive = {
                "gzip_sha256": sha256(path),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "full_signed_classes": 4,
            }
            result = scan_prefix(path, archive, 2, [1, 0],
                                 time.perf_counter(),
                                 {"wall_seconds": 10, "peak_rss_bytes": 1 << 32})
            self.assertEqual(result["selected_raw_sha256"],
                             hashlib.sha256(raw[:8]).hexdigest())
            self.assertEqual(result["last_selected_mask"], 3)
            self.assertEqual(result["first_excluded_mask"], 5)
            self.assertEqual(result["control_masks"], [3, 1])

            bad_raw = b"".join(struct.pack("<I", value)
                               for value in (1, 5, 3, 7))
            with gzip.open(path, "wb") as stream:
                stream.write(bad_raw)
            archive["gzip_sha256"] = sha256(path)
            archive["raw_sha256"] = hashlib.sha256(bad_raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                scan_prefix(path, archive, 2, [1, 0],
                            time.perf_counter(),
                            {"wall_seconds": 10, "peak_rss_bytes": 1 << 32})

    def test_scalar_law_vector_and_control_uniqueness(self):
        self.assertEqual(
            list(scalar_sequence("unit-test-domain", (1 << 129) + 12345, 3)),
            [
                (2, 496748400649113108823312701815621266373),
                (3, 247264752032887931110116485672000071792),
                (4, 148300349868261944566524708220978612129),
            ],
        )
        indices = control_indices("unit-test-controls", "source", 100, 64)
        self.assertEqual(len(indices), len(set(indices)))
        self.assertTrue(all(0 <= index < 100 for index in indices))

    def test_bound_q1421_size_change_rejected(self):
        config = load_json(CONFIG)
        self.assertEqual(validate(config)["status"],
                         "PASS_FROZEN_INPUT_PREFLIGHT")
        config["equal_base"]["actual_usable_points_B"] += 2
        with self.assertRaisesRegex(ValueError, "Q1421 count"):
            validate(config)


if __name__ == "__main__":
    unittest.main()
