"""Verify portable source/evidence hashes; historical local binaries stay external."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OLD_ROOT = Path('/Volumes/SSD990/cryptanalysis')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checked = 0
    external = set()
    archive = HERE/'round3'
    for name, digest in json.loads((archive/'results/artifact-manifest.json').read_text())['sha256'].items():
        path = Path(name)
        if 'build' in path.parts:
            external.add(str(path))
            continue
        assert sha(archive/path) == digest, name
        checked += 1
    for name, key in [('certificate-benchmark.json','sha256'), ('gpu-run.json','source_sha256'),
                      ('query-check.json','sha256'), ('packing-benchmark.json','sha256')]:
        for name, digest in json.loads((archive/'results'/name).read_text())[key].items():
            original = Path(name)
            if not original.is_relative_to(OLD_ROOT) or 'build' in original.parts:
                external.add(str(original))
                continue
            path = ROOT/original.relative_to(OLD_ROOT)
            assert sha(path) == digest, name
            checked += 1
    distribution = HERE/'distribution-manifest.json'
    for name, digest in json.loads(distribution.read_text())['sha256'].items():
        path = Path(name)
        assert not path.is_absolute() and '..' not in path.parts
        assert sha(ROOT/path) == digest, name
        checked += 1
    print(json.dumps({'status':'PASS','hash_checks':checked,'historical_binaries_not_distributed':sorted(external),
                      'scope':'Checks shipped bytes; rebuilt binaries are validated separately, not asserted byte-identical to the measured Mac binaries'}))


if __name__ == '__main__':
    main()
