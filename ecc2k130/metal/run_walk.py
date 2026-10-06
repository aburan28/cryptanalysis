#!/usr/bin/env python3
"""Run and independently verify a bounded Metal walk on public synthetic data.

Uses the compact signed directions from the published table, not the giant
pair-sum payload. All selectors are evaluated from the current point.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import time
from urllib.parse import urljoin

from artifact_reference import Reference, STATE, REPORT, words, xy, MASK
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import table_store


def prepare(root, entry, catalog, base_url, artifact_dir, config):
    root.mkdir(parents=True, exist_ok=False)
    for name in ('directions.bin', 'coefficients.json'):
        item = next(f for f in entry['files'] if f['name'] == name)
        target = root / name
        if artifact_dir:
            source = artifact_dir / name
            if source.stat().st_size != item['bytes'] or table_store.digest(source) != item['sha256']:
                raise ValueError('local artifact identity mismatch: ' + name)
            shutil.copyfile(source, target)
        else:
            if not base_url: raise ValueError('no public artifact URL')
            table_store.download_file(item, urljoin(base_url, item['key']), target)
    coefficients = json.loads((root / 'coefficients.json').read_text())
    for key in ('ell', 'frobeniusEigenvalue', 'generatorPolynomial', 'targetPolynomial', 'knownScalar'):
        if coefficients[key] != catalog['domain'][key]:
            raise ValueError('artifact does not match the catalog domain')
    reference = Reference((root / 'directions.bin').read_bytes(), config['branches'])
    (root / 'selector.bin').write_bytes(reference.constants())
    (root / 'initial.bin').write_bytes(b''.join(reference.serialize(reference.initial(config['seed'] + lane)) for lane in range(config['lanes'])))
    (root / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    rng = random.Random(0x6d6574616c)
    cases = [(0, 0), (1, 1), ((1 << 131) - 1, (1 << 131) - 1)]
    cases += [(1 << bit, rng.getrandbits(131)) for bit in range(131)]
    cases += [(rng.getrandbits(131), rng.getrandbits(131)) for _ in range(64)]
    inputs, expected = [], []
    curve, field = reference.curve, reference.field
    for i, (a, b) in enumerate(cases):
        p, q = reference.points[(17 * i) % len(reference.points)], reference.points[(29 * i + 4) % len(reference.points)]
        if i % 8 == 0: p = None
        elif i % 8 == 1: q = None
        elif i % 8 == 2: q = p
        elif i % 8 == 3: q = curve.neg(p)
        elif i % 8 == 4: p, q = (0, 1), (0, 1)
        summed = curve.add(p, q)
        inputs.extend(words(a) + words(b) + xy(p) + xy(q) + [int(p is None), int(q is None)])
        expected.extend(words(field.mul(a, b)) + words(field.sqr(a)) + words(field.inv(a) if a else 0) + xy(summed) + [int(summed is None)])
    (root / 'arithmetic-in.bin').write_bytes(struct.pack('<%dI' % len(inputs), *inputs))
    (root / 'arithmetic-expected.bin').write_bytes(struct.pack('<%dI' % len(expected), *expected))
    return reference


def verify(root, reference, config, selected):
    states = (root / 'state.bin').read_bytes()
    data = (root / 'reports.bin').read_bytes()
    if len(states) != config['lanes'] * STATE.size or len(data) % REPORT.size:
        raise ValueError('incomplete state/report output')
    records = [data[i:i + REPORT.size] for i in range(0, len(data), REPORT.size)]
    by_lane = {}
    for record in records:
        values = REPORT.unpack(record)
        if values[2] >= config['lanes'] or values[-1] != 0:
            raise ValueError('invalid report lane/padding')
        by_lane.setdefault(values[2], []).append(record)
    checked_reports = 0
    for lane in selected:
        expected, reports = reference.replay(lane, config['lanes'], config['seed'],
                                             config['cycles'] * config['launches'], config['dpWeight'])
        actual = states[lane * STATE.size:(lane + 1) * STATE.size]
        if actual != expected:
            raise ValueError('CPU/GPU final state mismatch at lane %d\nactual=%s\nexpected=%s' % (lane, STATE.unpack(actual), STATE.unpack(expected)))
        if sorted(by_lane.get(lane, [])) != sorted(reports):
            raise ValueError('CPU/GPU report mismatch at lane %d' % lane)
        checked_reports += len(reports)
    totals = {'walkUpdates': 0, 'seedAdditions': 0, 'dpRecords': 0, 'haltedLanes': 0, 'exhaustedLanes': 0}
    for offset in range(0, len(states), STATE.size):
        row = STATE.unpack_from(states, offset)
        totals['walkUpdates'] += row[16]
        totals['seedAdditions'] += row[17]
        totals['dpRecords'] += row[20]
        totals['haltedLanes'] += row[13] == 2
        totals['exhaustedLanes'] += row[13] == 3
    if totals['dpRecords'] != len(records): raise ValueError('state/report counts disagree')
    return {'referenceLanes': len(selected), 'referenceReports': checked_reports,
            'stateSha256': hashlib.sha256(states).hexdigest(), 'reportSha256': hashlib.sha256(data).hexdigest(), **totals}


def validateRates(report):
    for name in ('gpuSeconds', 'dispatchWallSeconds', 'iterationsPerSecond',
                 'millionIterationsPerSecond', 'chargedGroupOperationsPerSecond',
                 'wallIterationsPerSecond'):
        value = report.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('invalid native throughput field: ' + name)
    gpu = report['gpuSeconds']
    wall = report['dispatchWallSeconds']
    expected = report['walkUpdates'] / gpu if gpu else 0
    charged = report['groupOperations'] / gpu if gpu else 0
    wallRate = report['walkUpdates'] / wall if wall else 0
    if (not math.isclose(report['iterationsPerSecond'], expected, rel_tol=1e-12) or
            not math.isclose(report['millionIterationsPerSecond'], expected / 1e6, rel_tol=1e-12) or
            not math.isclose(report['chargedGroupOperationsPerSecond'], charged, rel_tol=1e-12) or
            not math.isclose(report['wallIterationsPerSecond'], wallRate, rel_tol=1e-12)):
        raise ValueError('native throughput accounting mismatch')


def runNative(executable, inputRoot, outputRoot, logPath, shieldSignals=False):
    """Run the native driver while preserving its live progress stream."""
    command = [str(executable), str(inputRoot.resolve()), str(outputRoot.resolve())]
    with logPath.open('w') as log:
        process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, bufsize=1,
                                   start_new_session=shieldSignals)
        for line in process.stderr:
            print(line, end='', file=sys.stderr, flush=True)
            log.write(line)
            log.flush()
        output = process.stdout.read()
        code = process.wait()
        log.write(output)
    if code:
        raise RuntimeError(output or 'native walk exited %d' % code)
    report = json.loads(output)
    if report.get('status') != 'ok':
        raise RuntimeError(report.get('error', 'native walk failed'))
    validateRates(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--artifact-dir', type=Path, help='existing validated local pair-table directory; otherwise download directions/coefficients only')
    parser.add_argument('--catalog')
    parser.add_argument('--branches', type=int, choices=(128, 256), default=128)
    parser.add_argument('--lanes', type=int, default=128)
    parser.add_argument('--cycles', type=int, default=64)
    parser.add_argument('--launches', type=int, default=4)
    parser.add_argument('--batch', type=int, choices=(1, 4, 8, 16, 32), default=16)
    parser.add_argument('--dp-weight', type=int, default=32)
    parser.add_argument('--dp-cap', type=int, default=65536)
    parser.add_argument('--seed', type=int, default=20260921)
    parser.add_argument('--verify-lanes', type=int, default=16)
    parser.add_argument('--progress-every', type=int, default=1,
                        help='print live throughput after this many launches')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if (not 1 <= args.lanes <= 65536 or not 1 <= args.cycles <= 128 or not 1 <= args.launches <= 10000 or
            not -1 <= args.dp_weight <= 130 or not 1 <= args.dp_cap <= 1000000 or
            not 0 <= args.seed <= MASK - args.lanes + 1 or not 1 <= args.verify_lanes <= args.lanes or
            args.progress_every < 1):
        parser.error('invalid workload/seed bounds')
    config = {'lanes': args.lanes, 'cycles': args.cycles, 'launches': args.launches, 'branches': args.branches,
              'dpCap': args.dp_cap, 'batch': args.batch, 'dpWeight': args.dp_weight,
              'seed': args.seed, 'progressEvery': args.progress_every}
    catalog, base = table_store.load_catalog(args.catalog)
    entry = next(e for e in catalog['artifacts'] if e['branches'] == args.branches)
    start = time.perf_counter()
    reference = prepare(args.out, entry, catalog, base, args.artifact_dir, config)
    if args.prepare_only:
        print(json.dumps({'prepared': str(args.out), 'config': config})); return
    executable = ROOT / 'build/metal-artifact-walk'
    if not executable.is_file(): raise ValueError('build first: make -C %s' % (ROOT / 'metal'))
    report = runNative(executable, args.out, args.out, args.out / 'native.log')
    selected = sorted(set([0, args.lanes - 1] + random.Random(8191).sample(range(args.lanes), args.verify_lanes)))
    checks = verify(args.out, reference, config, selected)
    for key in ('walkUpdates', 'seedAdditions', 'dpRecords', 'haltedLanes', 'exhaustedLanes'):
        if checks[key] != report[key]: raise ValueError('native accounting mismatch: ' + key)
    sourcePaths = [ROOT / 'metal' / n for n in
                   ('artifact_walk.metal', 'artifact_walk.mm', 'artifact_reference.py', 'run_walk.py')]
    sourcePaths += [ROOT / 'scripts/mslgen.py', ROOT / 'table_store.py',
                    ROOT / 'research/step_table/pack.py', ROOT / 'research/step_table/table.py',
                    ROOT / 'codegen/field.py', ROOT / 'codegen/curves.py', ROOT / 'generated/eccF131.h']
    sourcePaths += sorted((ROOT / 'include').glob('*.h')) + sorted((ROOT / 'include').glob('*.cuh'))
    report.update({'config': config, 'validation': checks, 'wallSecondsIncludingPreparationAndReplay': time.perf_counter() - start,
                   'binarySha256': table_store.digest(executable), 'catalogDomain': catalog['domain'],
                   'sourceSha256': {str(p.relative_to(ROOT)): table_store.digest(p) for p in sourcePaths}})
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
