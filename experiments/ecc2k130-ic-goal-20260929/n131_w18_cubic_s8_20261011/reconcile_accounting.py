"""One-time exact phase reconciliation of the two frozen solver receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = {
    'initial': 'e228695d345d2a55de816e6e8bfa7657b5b413b44c3b0950d6341f803e25fd7b',
    'trace_gate': 'bc6467df089965dca0bd4d1bbdb96c6ea76b624e9faf762dd47a36432f8a1fe7',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    for label, directory in (('initial', HERE), ('trace_gate', HERE/'trace_gate_variant')):
        path = directory/'query_result.json'
        old_sha = sha(path)
        assert old_sha == ORIGINAL[label]
        record = json.loads(path.read_text())
        phases = record['phase_seconds']
        assert 'post_solver_log_capture' not in phases
        missing = phases['total'] - sum(phases[key] for key in
                                        ('construction', 'write_and_hash', 'solver'))
        assert 0 < missing < 0.1
        phases['post_solver_log_capture'] = missing
        record['accounting_amendment'] = (
            'The process total already included log readback, gzip compression, and '
            'hashing after the solver interval. Their exact recorded-time residual '
            'is now an exclusive post_solver_log_capture phase; the source, target, '
            'solver interval, and process total are unchanged.')
        path.write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
        new_sha = sha(path)
        result = {'status': 'PASS_EXCLUSIVE_PHASE_RECONCILIATION',
                  'label': label, 'original_query_result_sha256': old_sha,
                  'amended_query_result_sha256': new_sha,
                  'post_solver_log_capture_seconds': missing,
                  'total_seconds_unchanged': phases['total'],
                  'solver_seconds_unchanged': phases['solver'],
                  'source_sha256': {'reconcile_accounting.py': sha(Path(__file__))}}
        (directory/'accounting_correction.json').write_text(
            json.dumps(result, sort_keys=True, indent=2)+'\n')
        print(json.dumps({'label': label, 'new_sha256': new_sha,
                          'post_solver_log_capture_seconds': missing}))


if __name__ == '__main__':
    main()
