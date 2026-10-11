"""Audit a retained runner artifact without loading any native binary from it."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapped(raw, evidence):
    marker = '/experiments/'
    if marker not in raw: raise ValueError('unrecognized executed path: '+raw)
    relative = Path('experiments') / raw.split(marker, 1)[1]
    if '..' in relative.parts: raise ValueError('noncanonical executed path')
    parts = relative.parts
    if parts[1] == 'groebner-perf-20260924' and len(parts) > 4 and parts[3] == 'build':
        return evidence/'native'/parts[2]/Path(*parts[4:])
    if parts[1] == 'pdp-degree-heuristics' and len(parts) > 3 and parts[2] == 'build':
        return evidence/'native/pdp-degree-heuristics'/Path(*parts[3:])
    return ROOT/relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    if args.output.exists(): raise FileExistsError(args.output)
    report_path = evidence/'correctness.json.gz'
    report = json.loads(gzip.decompress(report_path.read_bytes()))
    assert report['schema'] == 'constant-identity-query-validation/1' and report['status'] == 'PASS'
    assert report['timing_eligible'] is False and report['online_speedup'] is None
    assert report['validator_sha256'] == sha(HERE/'validate_queries.py')
    runner = json.loads((evidence/'runner.json').read_text())
    receipt = json.loads((evidence/'native/round66/native-receipt.json').read_text())
    kernel_receipt = json.loads((evidence/'native/round66/receipt.json').read_text())
    assert receipt['architecture'] == runner['architecture']
    assert kernel_receipt['architecture'] == runner['architecture']
    assert report['metal']['requested'] == receipt['metal_enabled']
    bound = {}
    own_receipt = own_wrapper = False
    for raw, digest in report['executed_bindings'].items():
        path = mapped(raw, evidence)
        assert sha(path) == digest, path
        assert str(path) not in bound
        bound[str(path)] = digest
        own_receipt |= raw.endswith('/round66/build/native-receipt.json')
        own_wrapper |= raw.endswith('/round66/independent_checker.py')
    assert own_receipt and own_wrapper
    for name, digest in receipt['sources'].items():
        path = (ROOT if name.startswith('experiments/') else HERE.parent)/name
        assert sha(path) == digest, path
    for group in ('binaries', 'generated'):
        for name, digest in receipt[group].items():
            assert sha(evidence/'native/round66'/name) == digest, name
    for name, digest in kernel_receipt['sources'].items():
        assert sha(HERE/name) == digest, name
    for name, digest in kernel_receipt['binaries'].items():
        assert sha(evidence/'native/round66'/name) == digest, name
    assert 'Ran 9 tests' in (evidence/'unit-tests.log').read_text()
    assert '\nOK\n' in (evidence/'unit-tests.log').read_text()
    for name in ('test-constant.log', 'test-constant-ubsan.log'):
        assert 'CONSTANT_IDENTITY_CONTROLS_PASS 6480' in (evidence/name).read_text()
    available = report['metal']['status'] == 'AVAILABLE'
    assert report['constant_modes'] == ['original', 'prepared', 'folded']
    # Only path prefixes are rewritten. Proofs, answers, source hashes and device
    # metadata are unchanged; archive binaries are read for hashing, never loaded.
    replay = args.output.parent/(args.output.stem+'-original-anf')
    replay.mkdir(parents=True, exist_ok=False)
    report['executed_bindings'] = bound
    rebased = replay/'input.json.gz'
    rebased.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    output = replay/'audit.json'
    subprocess.run([sys.executable, str(HERE/'audit_queries.py'), '--input', str(rebased), '--output', str(output)], check=True)
    audit = json.loads(output.read_text())
    rows = 972 if available else 324
    assert audit['status'] == 'PASS' and len(audit['records']) == rows
    assert len(report['queries']) == rows and audit['independent_proofs'] == (35 if available else 18)
    result = {'status': 'PASS', 'rows': rows, 'verified': rows, 'inconclusive': 0,
              'complete_pdp_successes': rows, 'bindings': len(bound), 'metal': report['metal'],
              'original_anf_audit': audit, 'report_sha256': sha(report_path),
              'runner_sha256': sha(evidence/'runner.json'), 'auditor_sha256': sha(Path(__file__)),
              'native_artifacts_loaded': False, 'performance_claim': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('RETAINED_ARTIFACT_AUDIT_PASS', rows, len(bound), flush=True)


if __name__ == '__main__':
    main()
