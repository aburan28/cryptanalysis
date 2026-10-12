"""Fresh portable builds with unchanged numerical sources and bound transport code."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('build102_for103', P/'round102/build.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
previous.HERE = previous.previous.HERE = previous.previous.baseline.HERE = previous.previous.baseline.native.HERE = HERE
original_sources = previous.source_paths


def source_paths():
    paths = [p for p in original_sources() if p != HERE/'dense_values.inc']
    paths += [P/'round102'/name for name in ('build.py','generate.py','query.py','dense_values.inc')]
    return list(dict.fromkeys(paths))


previous.previous.baseline.native.source_paths = source_paths


def build():
    previous.build()
    path = HERE/'build/receipt.json'
    receipt = json.loads(path.read_text())
    receipt['schema'] = 'owned-proof-build/1'
    path.write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    build()
