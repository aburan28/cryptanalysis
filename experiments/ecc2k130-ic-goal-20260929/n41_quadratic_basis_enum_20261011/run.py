"""Run the frozen native enumeration with a one-worker wall and RSS guard."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    assert protocol['status'] == 'FROZEN_BEFORE_HALFTRACE_BASIS_COMPARISON'
    for name, path in {'source': HERE/'basis_compare.cpp',
                       'binary': HERE/'basis_compare_native',
                       'targets': HERE/'targets.txt',
                       'runner': Path(__file__)}.items():
        assert sha(path) == protocol['sha256'][name]
    output = HERE/'receipt.json'
    terminal = HERE/'execution.json'
    if output.exists() or terminal.exists():
        raise FileExistsError('frozen output already exists')
    begun = time.monotonic()
    with (HERE/'run.stdout').open('xb') as stdout, (HERE/'run.stderr').open('xb') as stderr:
        process = subprocess.Popen([str(HERE/'basis_compare_native'),
                                    str(HERE/'targets.txt'), str(output)],
                                   cwd=HERE, stdout=stdout, stderr=stderr)
        child, parent = psutil.Process(process.pid), psutil.Process()
        peak = 0
        stopped = None
        while process.poll() is None:
            try:
                rss = child.memory_info().rss + parent.memory_info().rss
            except psutil.NoSuchProcess:
                rss = parent.memory_info().rss
            peak = max(peak, rss)
            if rss > protocol['limits']['rss_bytes']:
                stopped = 'RESOURCE_GATE_EXCEEDED'
                process.kill()
            elif time.monotonic() - begun > protocol['limits']['wall_seconds']:
                stopped = 'CENSORED_TIME'
                process.kill()
            time.sleep(0.02)
        returncode = process.wait()
    elapsed = time.monotonic() - begun
    result = json.loads(output.read_text()) if output.exists() and returncode == 0 else None
    status = stopped or ('COMPLETE' if returncode == 0 and result and
                         result['status'] == 'PASS_EXACT_BASIS_QUADRATIC_ENUMERATION'
                         else 'PRODUCER_FAILURE')
    record = {'status': status, 'returncode': returncode, 'wall_seconds': elapsed,
              'peak_combined_rss_bytes': peak,
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json')},
              'stdout_sha256': sha(HERE/'run.stdout'),
              'stderr_sha256': sha(HERE/'run.stderr'),
              'receipt_sha256': sha(output) if output.exists() else None}
    terminal.write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': status, 'wall_seconds': elapsed,
                      'peak_combined_rss_bytes': peak}))


if __name__ == '__main__':
    main()
