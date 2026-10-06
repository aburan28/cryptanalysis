"""Projection lifecycle, reusable buffers and isolated complete-query factories."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from adapter import producer, Checker, ProjectionQuery, accepted_checker

HERE = Path(__file__).resolve().parent


class GPUConfigurationTests(unittest.TestCase):
    def test_accepted_factory_remains_separate(self):
        spec = importlib.util.spec_from_file_location('lazy51_prior49_test', HERE.parent / 'round49/adapter.py')
        previous = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(previous)
        # Restore this test directory after importing the accepted comparator.
        sys.path.insert(0, str(HERE))
        item = json.loads(gzip.decompress((HERE.parent / 'round40/fixtures/inputs.json.gz').read_bytes()))[0]
        shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
        for cls, folder in ((previous.ProjectionQuery, HERE.parent / 'round49'),
                            (ProjectionQuery, HERE), (previous.ProjectionQuery, HERE.parent / 'round49')):
            with cls(*shape) as query:
                self.assertEqual(query.basis.producer.path.parent.parent, folder)
                self.assertEqual(query.checker.path.parent.parent, HERE.parent / 'round48')

    def test_configuration_fresh_queries_and_thread_serialization(self):
        for backend in ['cpu'] + (['metal'] if os.environ.get('QUADRATIC_TEST_METAL') == '1' else []):
            with producer.Producer(2, 3, 3, backend=backend) as p, Checker(2, 3, 3, identity='factored_local') as c:
                for value in (0, 1, None, 'true'):
                    with self.assertRaises(ValueError):
                        p.configure_gpu_projection(value)
                self.assertEqual(p.lib.branch_gpu_projection_configure(p._handle, 2), -1)
                self.assertEqual(p.lib.branch_gpu_projection_configure(None, 0), -1)
                terms = [(4, 1), (24, 2), (0, 2)]
                packed = producer.Packed(5, 3, terms)
                off = on = None
                for enabled in (False, True, False, True):
                    self.assertEqual(p.configure_gpu_projection(enabled), enabled and backend == 'metal')
                    result = p.produce(packed, checker=c)
                    self.assertTrue(result['certificate']['verified'])
                    self.assertEqual(result['gpu_projection_stats']['enabled'], enabled and backend == 'metal')
                    if enabled:
                        on = result
                    else:
                        off = result
                self.assertEqual(on['basis'], off['basis'])
                self.assertEqual(on['roots'], off['roots'])
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(lambda _: p.produce(packed, checker=c), range(12)))
                for answer in results:
                    self.assertEqual(answer['proof_bytes'], on['proof_bytes'])
                    self.assertEqual(answer['gpu_projection_stats'], on['gpu_projection_stats'])
                # Change the equations between successful uses of the same buffers.
                changed = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 3)])
                middle = p.produce(changed, checker=c)
                self.assertTrue(middle['certificate']['verified'])
                self.assertNotEqual(middle['roots'], on['roots'])
                self.assertEqual(p.produce(packed, checker=c)['proof_bytes'], on['proof_bytes'])
            with self.assertRaises(RuntimeError):
                p.configure_gpu_projection(False)

    def test_factory_isolation(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('foreign constructor called')
        missing = object()
        previous = {name: sys.modules.get(name, missing) for name in ('checker_base', 'normalized', 'independent_checker')}
        try:
            sys.modules['checker_base'] = SimpleNamespace(Checker=forbidden, CheckStats=accepted_checker.CheckStats)
            sys.modules['normalized'] = SimpleNamespace(Basis=forbidden)
            sys.modules['independent_checker'] = SimpleNamespace(Checker=forbidden)
            spec = importlib.util.spec_from_file_location('isolated_lazy51_test', HERE / 'adapter.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            item = json.loads(gzip.decompress((HERE.parent / 'round40/fixtures/inputs.json.gz').read_bytes()))[0]
            with module.ProjectionQuery(*(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))) as q:
                self.assertEqual(q.basis.producer.path.parent.parent, HERE)
                self.assertEqual(q.checker.path.parent.parent, HERE.parent / 'round48')
        finally:
            for name, value in previous.items():
                if value is missing:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value

    def test_table_cap_and_explicit_cpu_shape_fallback(self):
        with self.assertRaisesRegex(ValueError, '64 MiB'):
            producer.Producer(20, 10, 31)
        if os.environ.get('QUADRATIC_TEST_METAL') != '1':
            return
        with producer.Producer(2, 3, 65, backend='metal') as p:
            self.assertIn('shape fallback', p.device)
            self.assertFalse(p.configure_gpu_projection(True))
            result = p.produce(producer.Packed(5, 65, [(4, 1), (24, 1 << 64), (0, 1 << 64)]))
            self.assertFalse(result['gpu_projection_stats']['enabled'])
            self.assertEqual(result['gpu_projection_stats']['output_bytes'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
