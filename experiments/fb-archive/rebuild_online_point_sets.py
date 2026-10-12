"""Bounded reconstruction of the nine recorded online point sets still missing.

Run larger reconstructions on a provisioned remote host. Outputs are staged in
their own directory; this tool never edits the repository archive index or debt.
An archive classified as large still needs durable placement before promotion.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import fbarchive

HERE = Path(__file__).resolve().parent
MANIFEST = HERE/'backfill-online-20261007.json'


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)


def sources():
    paths = [p for folder in (HERE, HERE.parent/'pdp-degree-heuristics')
             for p in folder.iterdir() if p.suffix in ('.py', '.c', '.h')]
    paths += [HERE.parent/'pdp-scaling/gf2n.py', MANIFEST]
    return {str(p.relative_to(HERE.parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def worker(digest, output):
    entries = json.loads(MANIFEST.read_text())['remaining_point_sets']
    entry = entries[digest]
    recipe = entry['recipe']
    doc = fbarchive.build(recipe['n'], recipe['family'], recipe['l'], recipe['seed'])
    assert doc['factor_base'] == entry['recorded_factor_base']
    assert doc['factor_base']['enumerated_set_sha256'] == digest
    # Isolate newly generated archives from the checkout's accepted index.
    fbarchive.HERE = output
    fbarchive.INDEX = output/'index.csv'
    row = fbarchive.store(doc, codec='xz', max_git_bytes=80*1024*1024)
    assert not fbarchive.verify_row(row, False, 0)
    record = dict(status='REBUILT_EXACT', point_set_sha256=digest, row=row,
                  recorded_factor_base_matched=True,
                  durable_placement_required=row['storage'] != 'git',
                  sources=sources())
    native = HERE.parent/'pdp-degree-heuristics/build'
    record['native'] = {str(p.relative_to(HERE.parents[1])):
                       hashlib.sha256(p.read_bytes()).hexdigest() for p in native.rglob('*.so')}
    save(output/(digest+'.json'), record)


def main(output, timeout):
    output.mkdir(parents=True, exist_ok=False)
    entries = json.loads(MANIFEST.read_text())['remaining_point_sets']
    assert len(entries) == 9
    record = dict(schema='online-point-set-reconstruction/1', status='RUNNING',
                  platform=platform.platform(), architecture=platform.machine(),
                  sources=sources(), records=[], timing_eligible=False,
                  qualified_speedup=None, complete_repository_refs_pass=False,
                  started=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(output/'reconstruction.json', record)
    start = time.monotonic()
    # A global wall limit leaves time for the remote runner to package partial
    # successes, failed worker logs and the final status before its own deadline.
    for digest, entry in sorted(entries.items(), key=lambda pair: (
            pair[1]['recipe']['n'], pair[1]['recipe']['l'], pair[0])):
        remaining = timeout-(time.monotonic()-start)
        row = dict(point_set_sha256=digest, recipe=entry['recipe'])
        if remaining <= 1:
            row.update(status='NOT_STARTED_GLOBAL_DEADLINE')
        else:
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', digest,
                       '--output', str(output.resolve())]
            with (output/(digest+'.log')).open('w') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                try:
                    code = process.wait(timeout=remaining)
                    row.update(status='REBUILT_EXACT' if code == 0 else 'WORKER_FAILURE', exit_code=code)
                except subprocess.TimeoutExpired:
                    process.kill()
                    row.update(status='TIMEOUT', exit_code=process.wait())
            if row['status'] == 'REBUILT_EXACT':
                result = json.loads((output/(digest+'.json')).read_text())
                assert result['point_set_sha256'] == digest and result['recorded_factor_base_matched']
                row['archive'] = result['row']
        record['records'].append(row)
        save(output/'reconstruction.json', record)
        print(row['status'], entry['recipe'], flush=True)
    record.update(status='ALL_REBUILT_PENDING_PLACEMENT' if all(
        r['status'] == 'REBUILT_EXACT' for r in record['records']) else 'PARTIAL_OR_FAILED',
        finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(output/'reconstruction.json', record)
    return 0 if record['status'] == 'ALL_REBUILT_PENDING_PLACEMENT' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=5400)
    parser.add_argument('--worker', choices=sorted(json.loads(MANIFEST.read_text())['remaining_point_sets']))
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.output)
    else:
        if args.timeout < 1:
            parser.error('--timeout must be positive')
        raise SystemExit(main(args.output, args.timeout))
