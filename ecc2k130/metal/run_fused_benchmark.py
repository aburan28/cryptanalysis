#!/usr/bin/env python3
"""Run, validate, and bind one exact fused-selector Metal A/B receipt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        while True:
            block = source.read(8 << 20)
            if not block:
                return value.hexdigest()
            value.update(block)


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--pairs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--binary', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'build/metal-fused-benchmark')
    args = parser.parse_args()
    command = [str(args.binary.resolve()), str(args.input.resolve()),
               str(args.pairs.resolve())]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout or result.stderr)
    report = json.loads(result.stdout)
    if report.get('status') != 'passed' or report.get('correctResults') != report.get('cases'):
        raise ValueError('fused benchmark did not pass every exact result')
    baseline = report['baseline']['medianSeconds']
    fused = report['fused']['medianSeconds']
    logical = report['cases'] * report['logicalUpdatesPerCase'] * report['innerIterationsPerSample']
    if (not close(report['fusedToBaselineTimeRatio'], fused / baseline) or
            not close(report['fusedSpeedup'], baseline / fused) or
            not close(report['baselineLogicalUpdatesPerSecond'], logical / baseline) or
            not close(report['fusedLogicalUpdatesPerSecond'], logical / fused)):
        raise ValueError('fused benchmark rate accounting mismatch')
    if (report['runtimeAdditionsPerCase'] != 2 or report['pairLookupsPerCase'] != 1 or
            report.get('pairTableLoaded') is not True or
            report['pairTableBytes'] != args.pairs.stat().st_size or
            report['input']['pairPayloadSha256'] !=
            '809ae24f958e97f9d6f8854322ccd8ea62dc5660759619d32001a150be4e5a65'):
        raise ValueError('fused benchmark identity/charge mismatch')
    root = Path(__file__).resolve().parents[1]
    sources = [root / 'metal/fused_benchmark.mm',
               root / 'metal/fused_benchmark_extra.metal',
               root / 'metal/fused_reference.py',
               root / 'metal/prepare_fused_benchmark.py',
               root / 'metal/run_fused_benchmark.py',
               root / 'metal/artifact_walk.metal',
               root / 'metal/artifact_reference.py',
               root / 'scripts/mslgen.py']
    report['identity'] = {
        'binarySha256': digest(args.binary),
        'inputConfigSha256': digest(args.input / 'fused-config.json'),
        'inputBytesSha256': digest(args.input / 'fused-input.bin'),
        'expectedBytesSha256': digest(args.input / 'fused-expected.bin'),
        'sourceSha256': {str(path.relative_to(root)): digest(path) for path in sources}}
    report['command'] = ['metal-fused-benchmark', 'INPUT_DIRECTORY', 'PAIRS_FILE']
    report['claimBoundary'] = (
        'Matched exact-selector microbenchmark with two runtime additions in both paths; '
        'not a complete collection walk, DP campaign, or reduction in charged group operations.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
