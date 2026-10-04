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
    assert report['schema'] == 'shared-producer-transform-query-validation/1' and report['status'] == 'PASS'
    assert report['timing_eligible'] is False and report['online_speedup'] is None
    assert report['validator_sha256'] == sha(HERE/'validate_queries.py')
    runner = json.loads((evidence/'runner.json').read_text())
    receipt = json.loads((evidence/'native/round68/receipt.json').read_text())
    assert receipt['architecture'] == runner['architecture']
    assert report['metal']['requested'] == receipt['metal_enabled']
    bound = {}
    own_receipt = own_wrapper = False
    for raw, digest in report['executed_bindings'].items():
        path = mapped(raw, evidence)
        assert sha(path) == digest, path
        assert str(path) not in bound
        bound[str(path)] = digest
        own_receipt |= raw.endswith('/round68/build/receipt.json')
        own_wrapper |= raw.endswith('/round68/build/normalized.py')
    assert own_receipt and own_wrapper
    for name, digest in receipt['sources'].items():
        path = (ROOT if name.startswith('experiments/') else HERE.parent)/name
        assert sha(path) == digest, path
    for group in ('binaries', 'generated'):
        for name, digest in receipt[group].items():
            assert sha(evidence/'native/round68'/name) == digest, name
    unit_log=(evidence/'unit-tests.log').read_text()
    assert 'Ran 8 tests' in unit_log and '\nOK\n' in unit_log
    available = report['metal']['status'] == 'AVAILABLE'
    if available:
        for name in ('test-backend.log','test-backend-ubsan.log','test-backend-setup-failure.log'):
            assert 'PASS 192 shared-buffer controls;' in (evidence/name).read_text()
    # Bind every non-generated executed source/input to the exact Git snapshot.
    source_bindings=[]
    for raw,digest in report['executed_bindings'].items():
        path=mapped(raw,evidence)
        if path.is_relative_to(ROOT / 'experiments') and '/build/' not in raw:
            source_bindings.append((str(path.relative_to(ROOT)),digest))
    commit=report['source_commit']
    assert len(commit)==40 and all(c in '0123456789abcdef' for c in commit)
    requests=''.join(commit+':'+name+'\n' for name,_ in source_bindings).encode()
    blobs=subprocess.check_output(['git','cat-file','--batch'],input=requests,cwd=ROOT)
    offset=0
    for name,digest in source_bindings:
        end=blobs.index(b'\n',offset); header=blobs[offset:end].split()
        assert len(header)==3 and header[1]==b'blob',name
        size=int(header[2]); start=end+1
        assert hashlib.sha256(blobs[start:start+size]).hexdigest()==digest,name
        offset=start+size+1
    assert offset==len(blobs)
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
    rows = 756 if available else 108
    assert audit['status'] == 'PASS' and len(audit['records']) == rows
    assert len(report['queries']) == rows and audit['independent_proofs'] == (35 if available else 18)
    unsupported = 24 if available else 0
    verified = rows - unsupported
    assert sum(row['result']['verified'] for row in report['queries']) == verified
    result = {'status': 'PASS', 'rows': rows, 'verified': verified, 'inconclusive': 0,
              'unsupported': unsupported, 'rejected_setups': len(report['unsupported_setups']),
              'complete_pdp_successes': verified, 'bindings': len(bound), 'source_blob_bindings': len(source_bindings), 'metal': report['metal'],
              'original_anf_audit': audit, 'report_sha256': sha(report_path),
              'runner_sha256': sha(evidence/'runner.json'), 'auditor_sha256': sha(Path(__file__)),
              'native_artifacts_loaded': False, 'performance_claim': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('RETAINED_ARTIFACT_AUDIT_PASS', rows, len(bound), flush=True)


if __name__ == '__main__':
    main()
