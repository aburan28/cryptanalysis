"""Reproducibility, field-oracle and public-flag checks for the generated product."""
from pathlib import Path
import os
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

import genpackedproduct as generator

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / 'codegen' / 'genpackedproduct.py'
HEADER = ROOT / 'include' / 'packedgeneratedproduct131.h'
# Independent bit-polynomial multiplication/long division; no graph operators.
MODULUS = 0xd1d0d000d0000000d000000000000000d


def reference(a, b):
    product = 0
    for bit in range(131):
        if (b >> bit) & 1:
            product ^= a << bit
    for degree in range(260, 130, -1):
        if (product >> degree) & 1:
            product ^= MODULUS << (degree - 131)
    return product


def words(a, b):
    return [(value >> (32 * i)) & 0xffffffff for value in (a, b) for i in range(5)]


class GeneratedProductTests(unittest.TestCase):
    def test_header_is_reproducible_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'generated.h'
            runs = []
            for seed in ('1', '7721'):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                subprocess.run([sys.executable, str(GENERATOR), '--output', str(output)],
                               cwd=directory, env=env, check=True, capture_output=True, timeout=30)
                runs.append(output.read_bytes())
            self.assertEqual(runs[0], runs[1])
            self.assertEqual(runs[0], HEADER.read_bytes())

    def test_check_rejects_stale_or_missing_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'generated.h'
            command = [sys.executable, str(GENERATOR), '--check', '--output', str(output)]
            missing = subprocess.run(command, cwd=directory, capture_output=True, timeout=30)
            self.assertEqual(missing.returncode, 1)
            self.assertFalse(output.exists())
            output.write_bytes(HEADER.read_bytes())
            current = subprocess.run(command, cwd=directory, capture_output=True, timeout=30)
            self.assertEqual(current.returncode, 0)
            output.write_bytes(output.read_bytes() + b'// stale\n')
            before = output.read_bytes()
            stale = subprocess.run(command, cwd=directory, capture_output=True, timeout=30)
            self.assertEqual(stale.returncode, 1)
            self.assertEqual(output.read_bytes(), before)

    def test_fixed_products_and_live_dependencies(self):
        graph = generator.baseline()
        order = generator.schedule(graph)['events']
        self.assertEqual(len(graph.products), 144)
        self.assertEqual([node for node in order if graph.nodes[node]['op'] == 'wide'], graph.products)
        self.assertEqual(len(order), 562)
        available = set(range(10)) | {generator.ZERO}
        products = 0
        for node_id in order:
            node = graph.nodes[node_id]
            self.assertTrue(set(node['args']) <= available)
            if node['op'] == 'wide':
                self.assertEqual(len(node['out']), 2)
                products += 1
            if node['phase'] == 'tail':
                self.assertEqual(products, 144)
            available.update(node['out'])
        self.assertEqual(len(graph.outputs), 5)
        self.assertTrue(set(graph.outputs) <= available)

    def test_graph_against_independent_field_arithmetic(self):
        graph = generator.baseline()
        full = (1 << 131) - 1
        cases = [(1 << bit, full) for bit in range(131)]
        edges = (0, 1, 1 << 128, 7 << 128, (1 << 128) - 1, full)
        cases.extend((a, b) for a in edges for b in edges)
        rng = random.Random(0x131144)
        cases.extend((rng.getrandbits(131), rng.getrandbits(131)) for _ in range(64))
        for a, b in cases:
            result = graph.evaluate(words(a, b))
            self.assertEqual(result[4] & ~7, 0)
            self.assertEqual(sum(word << (32 * i) for i, word in enumerate(result)), reference(a, b))

    def test_default_tokens_and_invalid_flags(self):
        compiler = shlex.split(os.environ.get('CXX', 'c++'))
        if not compiler or shutil.which(compiler[0]) is None:
            self.skipTest('C++ preprocessor is unavailable')
        text = '#include "include/curveparams.h"\n#include "include/packed131.h"\n'

        def preprocess(*flags):
            return subprocess.run(compiler + ['-std=c++17', '-E', '-P', '-x', 'c++', '-I', str(ROOT),
                                  *flags, '-'], input=text, text=True, capture_output=True, timeout=30)

        absent = preprocess('-DECC_PACKED_DIRECT_REDUCE=1')
        disabled = preprocess('-DECC_PACKED_DIRECT_REDUCE=1', '-DECC_PACKED_GENERATED_PRODUCT=0')
        self.assertEqual(absent.returncode, 0, absent.stderr)
        self.assertEqual(disabled.returncode, 0, disabled.stderr)
        self.assertEqual(absent.stdout, disabled.stdout)
        enabled = preprocess('-DECC_PACKED_DIRECT_REDUCE=1', '-DECC_PACKED_GENERATED_PRODUCT=1')
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        self.assertIn('generatedProduct131(P131 a, P131 b)', enabled.stdout)
        for flags in [('-DECC_PACKED_DIRECT_REDUCE=1', '-DECC_PACKED_GENERATED_PRODUCT=-1'),
                      ('-DECC_PACKED_DIRECT_REDUCE=1', '-DECC_PACKED_GENERATED_PRODUCT=2'),
                      ('-DECC_PACKED_DIRECT_REDUCE=0', '-DECC_PACKED_GENERATED_PRODUCT=1')]:
            invalid = preprocess(*flags)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn('ECC_PACKED_GENERATED_PRODUCT', invalid.stderr)


if __name__ == '__main__':
    unittest.main()
