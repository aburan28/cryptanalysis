"""Cache component regressions; optional solve.py CLI integration is outside this package."""
import concurrent.futures
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from boolean_f5b import BooleanF5B
from macaulay_cache import (
    MAGIC, MacaulayCache, boolean_macaulay, monomial_layout,
)


class MacaulayAlgebraTests(unittest.TestCase):
    def test_rows_match_independent_boolean_products(self):
        rng = random.Random(1123)
        for nvars in range(1, 6):
            equations = [[rng.randrange(1 << nvars) for _ in range(7)]
                         for _ in range(3)]
            matrix = boolean_macaulay(equations, nvars, nvars)
            from sympy.polys.orderings import grevlex
            expected_columns = sorted(range(1 << nvars), key=lambda mask: grevlex(
                tuple((mask >> i) & 1 for i in range(nvars))))
            self.assertEqual(matrix.columns, tuple(expected_columns))
            # Evaluate every constructed row independently on every assignment.
            for row, (index, multiplier) in zip(matrix.rows, matrix.sources):
                for assignment in range(1 << nvars):
                    expected = sum(assignment & mask == mask
                                   for mask in equations[index]) % 2
                    expected *= int(assignment & multiplier == multiplier)
                    actual = sum((row >> column) & 1 for column, mask in
                                 enumerate(matrix.columns)
                                 if assignment & mask == mask) % 2
                    self.assertEqual(actual, expected)
            # At full Boolean degree the input equations (multiplier 1) occur.
            for i, equation in enumerate(equations):
                if any(equation.count(mask) % 2 for mask in set(equation)):
                    self.assertIn((i, 0), matrix.sources)

    def test_degree_bound_and_zero_constant_cases(self):
        matrix = boolean_macaulay([[3, 4], [1, 2, 0]], 3, 2)
        self.assertEqual(len(matrix.columns), 7)
        self.assertEqual(len(matrix.rows), 5)
        self.assertEqual(matrix.sources[0], (0, 0))
        self.assertTrue(all(mask.bit_count() <= 2 for mask in matrix.columns))
        self.assertEqual(boolean_macaulay([[1, 1]], 1, 0).rows, ())
        self.assertEqual(boolean_macaulay([[0]], 0, 0).rows, (1,))
        self.assertEqual(boolean_macaulay([[]], 0, 0).rows, ())

    def test_layout_reuse_does_not_reuse_different_equations(self):
        cache = MacaulayCache()
        first = boolean_macaulay([[3, 4]], 3, 3, cache=cache)
        before = dict(cache.stats)
        second = boolean_macaulay([[3, 2]], 3, 3, cache=cache)
        self.assertNotEqual(first.key, second.key)
        self.assertNotEqual(first.rows, second.rows)
        self.assertEqual(cache.stats["memory_hits"] - before["memory_hits"], 2)
        self.assertEqual(cache.stats["builds"] - before["builds"], 1)
        self.assertEqual(second, boolean_macaulay([[3, 2]], 3, 3))

    def test_key_binds_equations_ring_order_degree_and_context(self):
        base = boolean_macaulay([[1, 2, 0], [3, 4]], 3, 2)
        variants = [
            boolean_macaulay([[1, 2], [3, 4]], 3, 2),
            boolean_macaulay([[3, 4], [1, 2, 0]], 3, 2),
            boolean_macaulay([[1, 2, 0], [3, 4]], 4, 2),
            boolean_macaulay([[1, 2, 0], [3, 4]], 3, 3),
            boolean_macaulay([[1, 2, 0], [3, 4]], 3, 2,
                              variables=["v1", "v0", "v2"]),
            boolean_macaulay([[1, 2, 0], [3, 4]], 3, 2,
                              context={"field_modulus": 37}),
        ]
        self.assertEqual(len({base.key, *(variant.key for variant in variants)}), 7)
        self.assertEqual(base, boolean_macaulay([[2, 0, 1, 4, 4], [4, 3]], 3, 2))

    def test_limits_reject_before_construction_or_cache_write(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = MacaulayCache(directory)
            invalid_calls = [
                lambda: boolean_macaulay([[3]], 2, 1, cache=cache),
                lambda: boolean_macaulay([[4]], 2, 2, cache=cache),
                lambda: boolean_macaulay([[-1]], 2, 2, cache=cache),
                lambda: boolean_macaulay([[True]], 2, 2, cache=cache),
                lambda: boolean_macaulay([[1]], 3, 2, cache=cache, max_columns=6),
                lambda: boolean_macaulay([[1]], 3, 2, cache=cache, max_rows=3),
                lambda: boolean_macaulay([[1]], 3, 2, cache=cache, max_matrix_bytes=3),
                lambda: monomial_layout(131, 20, cache=cache),
                lambda: monomial_layout(10**9, 0, cache=cache),
                lambda: monomial_layout(-1, 2, cache=cache),
                lambda: monomial_layout(2, -1, cache=cache),
                lambda: monomial_layout(2, 2, cache=cache, variables=["x", "x"]),
            ]
            for call in invalid_calls:
                with self.assertRaises(ValueError):
                    call()
            self.assertEqual(list(Path(directory).iterdir()), [])


class PersistentCacheTests(unittest.TestCase):
    def test_memory_disk_hits_and_version_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = MacaulayCache(directory)
            build = Mock(return_value=[1, 3, 7])
            expected = cache.get_or_build({"kind": "test-v1"}, 3, 3, build)
            self.assertEqual(expected, (1, 3, 7))
            self.assertEqual(cache.get_or_build({"kind": "test-v1"}, 3, 3, build), expected)
            build.assert_called_once()
            self.assertEqual(cache.stats["memory_hits"], 1)
            fresh = MacaulayCache(directory)
            fail = Mock(side_effect=AssertionError("cache hit rebuilt rows"))
            self.assertEqual(fresh.get_or_build({"kind": "test-v1"}, 3, 3, fail), expected)
            self.assertEqual(fresh.stats["disk_hits"], 1)
            self.assertEqual(fresh.stats["build_seconds"], 0)
            self.assertEqual(fresh.stats["bytes_read"], cache.stats["bytes_written"])
            with patch("macaulay_cache.CACHE_SCHEMA", 2):
                newer = MacaulayCache(directory)
                newer.get_or_build({"kind": "test-v1"}, 3, 3, build)
                self.assertEqual(newer.stats["misses"], 1)

    def test_corrupt_truncated_wrong_identity_and_oversize_headers_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = {"kind": "corruption-test"}
            cache = MacaulayCache(directory)
            cache.get_or_build(spec, 5, 2, lambda: [3, 17])
            path = cache.path_for(cache.key(spec, 5, 2))
            valid = path.read_bytes()
            corruptions = [
                valid[:-1], valid + b"garbage", valid[:-1] + bytes([valid[-1] ^ 1]),
                b"old-format", MAGIC + struct.pack("<I", 2**32 - 1),
            ]
            header_size, = struct.unpack("<I", valid[len(MAGIC):len(MAGIC) + 4])
            header_end = len(MAGIC) + 4 + header_size
            header = json.loads(valid[len(MAGIC) + 4:header_end])
            header["key"] = "0" * 64
            wrong_header = json.dumps(header).encode()
            corruptions.append(MAGIC + struct.pack("<I", len(wrong_header))
                               + wrong_header + valid[header_end:])
            for corrupted in corruptions:
                path.write_bytes(corrupted)
                fresh = MacaulayCache(directory)
                self.assertEqual(fresh.get_or_build(spec, 5, 2, lambda: [3, 17]), (3, 17))
                self.assertEqual(fresh.stats["invalid_entries"], 1)
                self.assertEqual(fresh.stats["builds"], 1)
                self.assertEqual(path.read_bytes(), valid)

    def test_io_failure_and_size_limits_preserve_computation(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "ordinary-file"
            blocker.write_text("unchanged")
            cache = MacaulayCache(blocker)
            self.assertEqual(cache.get_or_build({}, 3, 2, lambda: [1, 7]), (1, 7))
            self.assertEqual(cache.stats["read_errors"], 1)
            self.assertEqual(cache.stats["write_errors"], 1)
            self.assertEqual(blocker.read_text(), "unchanged")
            tiny = MacaulayCache(directory, max_entry_bytes=1)
            self.assertEqual(tiny.get_or_build({}, 3, 2, lambda: [1, 7]), (1, 7))
            self.assertEqual(tiny.stats["oversize_skips"], 1)
            self.assertEqual(list(Path(directory).glob("*.bmc")), [])
            memory = MacaulayCache(memory_bytes=0)
            for _ in range(2):
                memory.get_or_build({}, 3, 1, lambda: [1])
            self.assertEqual(memory.stats["builds"], 2)

    def test_lru_and_disk_eviction_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = MacaulayCache(directory, memory_bytes=600, disk_bytes=400)
            for i in range(5):
                cache.get_or_build({"i": i}, 8, 1, lambda: [i])
                self.assertLessEqual(cache._memory_size, cache.memory_bytes)
                self.assertLessEqual(sum(p.stat().st_size for p in
                                         Path(directory).glob("*.bmc")), cache.disk_bytes)
            self.assertGreater(cache.stats["disk_evictions"], 0)
            self.assertLess(len(cache._memory), 5)

    def test_failed_or_invalid_builder_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = MacaulayCache(directory)
            with self.assertRaises(TimeoutError):
                cache.get_or_build({}, 2, 1, Mock(side_effect=TimeoutError))
            for rows in ([4], [-1], [True], [1, 2]):
                with self.assertRaises(ValueError):
                    cache.get_or_build({}, 2, 1, lambda: rows)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_concurrent_writers_publish_complete_records(self):
        with tempfile.TemporaryDirectory() as directory:
            barrier = threading.Barrier(4)

            def writer(_):
                cache = MacaulayCache(directory)

                def build():
                    barrier.wait(timeout=5)
                    return range(32)

                return cache.get_or_build({"kind": "concurrent"}, 5, 32, build)

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(writer, range(4)))
            self.assertEqual(results, [tuple(range(32))] * 4)
            fresh = MacaulayCache(directory)
            self.assertEqual(fresh.get_or_build({"kind": "concurrent"}, 5, 32,
                                               Mock(side_effect=AssertionError)), results[0])
            self.assertEqual(fresh.stats["disk_hits"], 1)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_precompute_cli_persists_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "input.json"
            fixture.write_text(json.dumps({"nvars": 3, "equations": [[3, 4], [1, 2, 0]]}))
            command = [sys.executable, str(Path(__file__).with_name("macaulay_cache.py")),
                       "--input", str(fixture), "--degree", "3", "--cache-dir",
                       str(Path(directory) / "cache")]
            cold = json.loads(subprocess.check_output(command, text=True))
            warm = json.loads(subprocess.check_output(command, text=True))
            self.assertEqual(cold["key"], warm["key"])
            self.assertEqual((cold["rows"], cold["columns"]), (11, 8))
            self.assertEqual(cold["nonzeros"], warm["nonzeros"])
            self.assertEqual(warm["cache"]["builds"], 0)
            self.assertEqual(warm["cache"]["disk_hits"], 4)


class BooleanEngineCacheTests(unittest.TestCase):


    def test_reducer_order_and_working_copies(self):
        cache = MacaulayCache()
        engine = BooleanF5B(3, matrix_cache=cache)
        reducers = [engine.from_terms([1, 2]), engine.from_terms([1, 4])]
        reference = BooleanF5B(3)
        expected = reference.reduction_table(reducers)
        rows = engine.reduction_table(reducers)
        self.assertEqual(rows, expected)
        rows[:] = [0] * len(rows)
        self.assertEqual(engine.reduction_table(reducers), expected)
        before = cache.stats["builds"]
        self.assertEqual(engine.reduction_table(reducers[::-1]),
                         reference.reduction_table(reducers[::-1]))
        self.assertEqual(cache.stats["builds"], before + 1)

    def test_uncached_cold_and_disk_cached_bases_have_identical_roots(self):
        rng = random.Random(90822)
        with tempfile.TemporaryDirectory() as directory:
            for nvars in range(2, 6):
                for _ in range(5):
                    reference = BooleanF5B(nvars)
                    generators = [reference.from_terms(
                        {rng.randrange(1 << nvars) for _ in range(5)})
                        for _ in range(nvars)]
                    expected = reference.basis(generators)
                    cold = BooleanF5B(nvars, matrix_cache=MacaulayCache(directory))
                    self.assertEqual(cold.basis(generators), expected)
                    disk = MacaulayCache(directory)
                    warm = BooleanF5B(nvars, matrix_cache=disk)
                    self.assertEqual(warm.basis(generators), expected)
                    self.assertTrue(warm.same_roots(generators, expected))
                    self.assertEqual(disk.stats["builds"], 0)
                    self.assertGreater(disk.stats["disk_hits"], 0)
                    self.assertEqual(warm.stats["reduction_table_builds"], 0)


if __name__ == "__main__":
    unittest.main()
