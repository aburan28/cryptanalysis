"""Exercise the actual manifest helper without requiring Modal or a GPU."""
import ast
import hashlib
from pathlib import Path
import tempfile
import unittest


class SourceIdentityTests(unittest.TestCase):
    def test_checkout_ancestors_do_not_exclude_source(self):
        source = Path(__file__).resolve().parents[1] / 'polystate_audit.py'
        parsed = ast.parse(source.read_text())
        helper = next(node for node in parsed.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'source_identity')
        namespace = {'hashlib': hashlib}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), 'exec'), namespace)
        with tempfile.TemporaryDirectory() as directory:
            # Both excluded names are ancestors; only exclusions *inside* the
            # checkout should affect the uploaded-source comparison.
            root = Path(directory) / 'build' / '__pycache__' / 'checkout'
            for name in ('src/field.cu', 'Makefile', 'build/local-binary',
                         'codegen/__pycache__/helper.pyc', 'ecc2k130', 'ecc2k130-cpu'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            actual = namespace['source_identity'](root)
            expected = {name: hashlib.sha256(name.encode()).hexdigest()
                        for name in ('Makefile', 'src/field.cu')}
            self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
