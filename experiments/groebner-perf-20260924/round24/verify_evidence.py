"""Verify tracked mapped-Metal evidence and bind its executed sources."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from audit import audit
from build import ROOT, HERE


def main():
    directory = HERE / 'results'
    inventory = json.loads((directory / 'inventory.json').read_text())
    tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines())
    for name, expected in inventory['files'].items():
        path = directory / name
        assert path.resolve().is_relative_to(directory.resolve())
        raw = path.read_bytes()
        assert len(raw) == expected['bytes'], name
        assert hashlib.sha256(raw).hexdigest() == expected['sha256'], name
        assert str(path.relative_to(ROOT)) in tracked, name
    for name in inventory['reports'] + inventory['historical_reports']:
        path = directory / name
        report = json.loads(gzip.decompress(path.read_bytes()))
        changed = {filename for filename, source in report['source_snapshot'].items()
                   if (ROOT / filename).read_text() != source}
        if name in inventory['historical_reports']:
            # The initial and confirmation measurements preceded stricter
            # receipt-key validation. Every numerical implementation, native
            # generator, benchmark and wrapper remains byte-for-byte identical.
            assert changed == {'experiments/groebner-perf-20260924/round24/audit.py'}, changed
        else:
            assert not changed, changed
        checked = audit(path)
        assert all(c['all_attempts_verified'] for c in checked['controls'])
        assert sum(checked['statuses'].values()) == 16 * 5 * (report['repetitions']+1)
        print(name, checked['statuses'], 'eligible:', checked['timing_admission_eligible'])
    print('Verified', len(inventory['files']), 'tracked artifacts and declared source bindings')


if __name__ == '__main__':
    main()
