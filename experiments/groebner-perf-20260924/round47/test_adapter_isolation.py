"""A comparator imported earlier must not select either native constructor."""
import gzip
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from test_symmetry import accepted_checker

HERE = Path(__file__).resolve().parent


class AdapterIsolationTests(unittest.TestCase):
    def test_preimported_checker_and_basis_do_not_change_factories(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('another experiment selected the workspace constructor')
        missing = object()
        previous = {name: sys.modules.get(name, missing) for name in ('checker_base', 'normalized', 'independent_checker')}
        try:
            sys.modules['checker_base'] = SimpleNamespace(Checker=forbidden, CheckStats=accepted_checker.CheckStats)
            sys.modules['independent_checker'] = SimpleNamespace(Checker=forbidden)
            sys.modules['normalized'] = SimpleNamespace(Basis=forbidden)
            spec = importlib.util.spec_from_file_location('isolated_symmetry_adapter_test', HERE / 'adapter.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            fixtures = json.loads(gzip.decompress((HERE.parent / 'round40/fixtures/inputs.json.gz').read_bytes()))
            item = fixtures[0]
            with module.SymmetryQuery(*(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))) as workspace:
                self.assertEqual(workspace.basis.producer.path.parent.parent, HERE.parent / 'round44')
                self.assertEqual(workspace.basis.checker.path.parent.parent, HERE)
                self.assertIs(workspace.checker, workspace.basis.checker)
        finally:
            for name, value in previous.items():
                if value is missing:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value


if __name__ == '__main__':
    unittest.main(verbosity=2)
