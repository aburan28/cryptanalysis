"""Materialize a measured grouped-inversion candidate from its retained receipt.

Creates a new directory containing all required baseline build sources, the exact
measured patch and helper headers, a reproducible build target, and evidence.
Never overwrites an existing directory or changes the production source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import statistics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acceptance(result, candidate):
    """Assess only retained measured evidence, excluding every warmup."""
    variant = result['variants'][candidate]
    summary = result['summary'][candidate]
    samples = summary.get('samples', [])
    probes = result.get('probes', []) + result.get('zip_collective_probes', [])
    arithmetic_required = bool(result.get('poly_square_sources') or result.get('zip_square_sources'))
    arithmetic_probed = any(p.get('name') == candidate for p in result.get('probes', []))
    checks = {
        'certification_candidate': result.get('certification_candidate') == candidate,
        'no_run_error': not result.get('error'),
        'five_completed_samples': len(samples) == 5 and all(
            s.get('valid') and s.get('completed_iterations', 0) > 0
            and s['completed_iterations'] == s.get('expected_iterations') for s in samples),
        'median_at_least_22B': bool(samples) and statistics.median(s['rate'] for s in samples) >= 22000,
        'summary_valid': summary.get('valid', False),
        'arithmetic_probes': bool(probes) and all(
            p.get('build', {}).get('returncode') == 0 and p.get('check', {}).get('returncode') == 0
            for p in probes) and (not arithmetic_required or arithmetic_probed),
        'metadata_probe': result.get('probe_build', {}).get('returncode') == 0
            and result.get('probe', {}).get('returncode') == 0,
        'build_and_identity': variant.get('build', {}).get('returncode') == 0
            and len(variant.get('binary_sha256', '')) == 64
            and result.get('compiler', {}).get('returncode') == 0
            and 'RTX PRO 6000 Blackwell Server Edition' in result.get('gpu_before', {}).get('raw', ''),
        'replay_and_corpus': variant.get('reports_ok', False) and
            variant.get('corpus') == result['variants']['baseline'].get('corpus'),
        'checkpoint_continuation': bool(variant.get('resume_checks')) and
            all(r['ok'] for r in variant['resume_checks']),
        'collection_measured': variant.get('collection', {}).get('valid', False),
        'collection_corpus_matches': result.get('candidate_corpus_matches', False),
    }
    return {'accepted': all(checks.values()), 'checks': checks,
            'scope': 'Single RTX PRO 6000, completed scalar updates; no production deployment',
            'limitations': [
                'Compute Sanitizer could not run on this device/runtime; it did not pass.',
                'Inherited test-clmad suite has unresolved source/guard expectation failures.',
                'No S3/RDS or fleet end-to-end performance claim.']}


def materialize(receipt, candidate, baseline, output):
    result = json.loads(receipt.read_text())
    variant = result['variants'][candidate]
    if not candidate.startswith('warps') or 'goal22CollectiveInverse' not in variant['extra_header']:
        raise ValueError('This exporter supports the measured grouped-inversion family only')
    if not variant.get('reports_ok') or not result['summary'][candidate]['valid']:
        raise ValueError('Candidate lacks successful walk checks and valid timing samples')
    files = {name: value for name, value in result['source_manifest']['files'].items()
             if name == 'Makefile' or name.split('/')[0] in ('include', 'src', 'generated', 'codegen')}
    if not files or 'Makefile' not in files:
        raise ValueError('Missing baseline build manifest')
    for name, value in files.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Invalid manifest path')
        if digest(baseline / name) != value:
            raise ValueError('Baseline source hash mismatch: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    for name in files:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline / name, destination)
    patch = output / 'candidate.patch'
    patch.write_text(variant['patch'])
    subprocess.run(['git', 'apply', '--check', str(patch.resolve())], cwd=output, check=True)
    subprocess.run(['git', 'apply', str(patch.resolve())], cwd=output, check=True)
    (output / 'include/collective_inverse.cuh').write_text(variant['extra_header'])
    for key in ('metadata_sources', 'zip_square_sources', 'poly_square_sources'):
        for name, content in result.get(key, {}).items():
            if Path(name).name != name:
                raise ValueError('Invalid helper name')
            if Path(name).suffix in ('.h', '.cuh', '.inc'):
                (output / 'include' / name).write_text(content)
            elif Path(name).suffix == '.py':
                helpers = output / 'research'
                helpers.mkdir(exist_ok=True)
                (helpers / name).write_text(content)
    command = variant['build']['command']
    if command[:3] != ['make', '-B', 'ecc2k130']:
        raise ValueError('Unexpected build command')
    makefile = output / 'Makefile'
    makefile.write_text(makefile.read_text() + '\n.PHONY: gpu-goal22\ngpu-goal22:\n\t'
                        + '$(MAKE) ' + shlex.join(command[1:]) + '\n')
    shutil.copy2(receipt, output / 'measurement.json')
    assessment = acceptance(result, candidate)
    (output / 'acceptance.json').write_text(json.dumps(assessment, indent=2) + '\n')
    manifest = {'candidate': candidate, 'receipt_sha256': digest(receipt),
                'baseline_sources': files, 'build_command': command,
                'measured_binary_sha256': variant['binary_sha256'],
                'source_files': {str(p.relative_to(output)): digest(p)
                                 for p in sorted(output.rglob('*')) if p.is_file()
                                 and p.name not in ('measurement.json',)}}
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    summary = result['summary'][candidate]
    collection = variant.get('collection', {})
    (output / 'README.md').write_text(
        '# Measured ECC2K-130 GPU candidate\n\n'
        f'Candidate: `{candidate}`. Median: {summary["rate"] / 1000:.6f} billion '
        f'complete scalar updates/sec, {len(summary["samples"])} timing samples.\n\n'
        'Target hardware: one RTX PRO 6000 Blackwell Server Edition, sm_120.\n'
        'Compiler identity, raw output, replay/resume checks and timing counts '
        'are retained in `measurement.json`. '
        + ('The five-sample throughput and walk-validation acceptance checks passed.\n\n'
           if assessment['accepted'] else 'This receipt does not meet all acceptance checks.\n\n')
        + f'DP34 collection rate: {collection.get("rate", 0) / 1000:.6f} B/s '
        '(zero means not measured in this receipt).\n\n'
        'Build using the compiler recorded in the receipt:\n\n'
        '```sh\nmake gpu-goal22\n```\n\n'
        'This is an isolated research build. It does not update running workers. '
        'Batch geometry must match the campaign before any deployment.\n\n'
        'Validation limits are recorded in `acceptance.json`: Compute Sanitizer '
        'was unavailable, the inherited test-clmad suite is not fully green, '
        'and this is not a fleet/S3/RDS end-to-end measurement.\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--baseline', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'build/live-22b-baseline')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = materialize(args.receipt, args.candidate, args.baseline, args.output)
    print(f'Materialized {manifest["candidate"]} in {args.output}')
