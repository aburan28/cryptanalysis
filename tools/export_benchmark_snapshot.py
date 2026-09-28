"""Export archived toy benchmark metadata without importing any execution code."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from curve_identity import digest, inspect_manifest


def export(repo, archive='experiments/ic-bench/baseline/primary.jsonl'):
    repo = Path(repo).resolve()
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    sources = {}

    def read(path):
        resolved = (repo / path).resolve()
        if not resolved.is_relative_to(repo) or resolved.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('Source outside repository or too large.')
        raw = resolved.read_bytes()
        # Source URLs must identify these exact bytes, including in a dirty checkout.
        committed = subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{path}'])
        if committed != raw:
            raise ValueError('Archive input differs from the committed source.')
        sources[path] = {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(),
                         'url': f'https://github.com/aburan28/cryptanalysis/blob/{commit}/{path}'}
        return raw

    records = [json.loads(line) for line in read(archive).splitlines() if line.strip()]
    if len(records) > 1000:
        raise ValueError('Archive exceeds 1000 rows.')
    rows, identities = [], {}
    for number, r in enumerate(records, 1):
        cid, wid = r['candidate_id'], r['workload_id']
        if not re.fullmatch(r'IC1[A-Za-z0-9]+h[a-f0-9]{12,64}', cid) or not re.fullmatch(r'[a-f0-9]{12,64}', wid):
            raise ValueError('Unsupported candidate/workload identifier.')
        cp, wp = f'experiments/ic-bench/candidates/{cid}.json', f'experiments/ic-bench/workloads/{wid}.json'
        m, w = json.loads(read(cp)), json.loads(read(wp))
        ident = inspect_manifest(m)
        if not digest(m).startswith(cid.rsplit('h', 1)[1]) or not digest(w).startswith(wid):
            raise ValueError('Candidate/workload hash does not match.')
        if r['source_curve_ref'] != ident['curve_id'] or w['curve_id'] != ident['curve_id']:
            raise ValueError('Receipt/manifest/workload curve mismatch.')
        if r['provenance']['workload_fixture_sha256'] != digest(w):
            raise ValueError('Receipt workload binding mismatch.')
        if not re.fullmatch(re.escape(cid + 'W' + wid) + r'R[1-9][0-9]*', r['run_id']):
            raise ValueError('Run identifier binding mismatch.')
        counts = r.get('counts', {})
        if counts.get('targets') != w['target_count']:
            raise ValueError('Receipt workload target count mismatch.')
        identities[ident['curve_uid']] = {**ident, 'field': m['field'], 'curve': m['curve']}
        online = r.get('online') or {}
        # No scalar, coordinates, executable config, raw logs, hostnames or ratio claims.
        rows.append({'id': f'{commit}:{archive}:{number}', 'run_id': r['run_id'],
            'candidate_id': cid, 'candidate_sha256': digest(m), 'workload_id': wid,
            'workload_sha256': digest(w), 'curve_uid': ident['curve_uid'], 'curve_id': ident['curve_id'],
            'method': 'index-calculus', 'suite': r.get('suite'), 'status': r.get('status', 'unknown'),
            'verification': 'recorded_verified' if r.get('verified_scalar') is True else 'unknown',
            'target_count': counts.get('targets'), 'targets_verified': counts.get('targets_verified'),
            'factor_base_sha256': m['factor_base'].get('enumerated_set_sha256'),
            'factor_base_points': m['factor_base'].get('actual_usable_point_count'),
            'receipt_factor_base_sha256': r.get('stage', {}).get('factor_base_sha256'),
            'isogeny': r.get('isogeny_route_ref'), 'operation_unit': r.get('operation_unit'),
            'total_operations': r.get('total_operations'), 'wall_ns': r.get('wall_ns'),
            'ic_online_ns': online.get('ic_online_ns'), 'rho_online_ns': online.get('rho_online_ns'),
            'online_boundary': online.get('interval'), 'calibration_id': r['provenance'].get('calibration_id'),
            'resource_envelope_id': r['provenance'].get('resource_envelope_id'),
            'scope': 'archived full_dlp receipt; total accounting as recorded; online interval separately labelled',
            'sources': [archive, cp, wp], 'source_line': number})
    return {'schema': 1, 'source_repository': 'aburan28/cryptanalysis', 'source_commit': commit,
            'coverage': f'All {len(rows)} rows in {archive}; other archives and historical runs are not included.',
            'identities': identities, 'sources': sources, 'rows': rows}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--archive', default='experiments/ic-bench/baseline/primary.jsonl')
    args = p.parse_args()
    print(json.dumps(export(args.repo, args.archive), ensure_ascii=False, indent=2, allow_nan=False))
