"""Build and run the bounded GF(2^23) group-operation experiment.

Trials share starts across modes; table seeds are independent replicates.  A
censored or exceptional run cannot win a comparison.  Raw rows, source hashes,
table identities, build command and charged setup costs are retained.
"""

import argparse
import hashlib
import json
import math
import pathlib
import platform
import random
import statistics
import subprocess
import time

import table

HERE = pathlib.Path(__file__).resolve().parent
MODES = ('legacy', 'weight8', 'orbit8', 'weight16', 'orbit16', 'orbit32', 'orbit64')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrapRatio(groups, baseline, candidate):
    """Paired cluster bootstrap over independent table/selector seeds.

    Do not treat thousands of trails in the same deterministic functional
    graph as independent table experiments. Return candidate/baseline work.
    """
    rng = random.Random(71123)
    ratios = []
    for _ in range(4000):
        picks = [groups[rng.randrange(len(groups))] for _ in groups]
        ratios.append(sum(x[candidate] for x in picks) / sum(x[baseline] for x in picks))
    ratios.sort()
    return [ratios[100], ratios[3899]]


def summarize(rows, tableCosts, trials):
    summaries = {}
    groups = []
    for seed in sorted(tableCosts):
        groups.append({mode: statistics.mean(r['walkGroupOps'] + r['startGroupOps']
                                            for r in rows if r['seed'] == seed and r['mode'] == mode)
                       + tableCosts[seed].get(mode, 0) / trials for mode in MODES})
    for mode in MODES:
        selected = [r for r in rows if r['mode'] == mode]
        useful = sum(r['useful'] for r in selected)
        walk = [r['walkGroupOps'] for r in selected]
        histogram = [sum(r['branches'][h] for r in selected) for h in range(len(selected[0]['branches']))]
        total = sum(histogram)
        summaries[mode] = {
            'trials': len(selected), 'usefulCollisions': useful,
            'censored': sum(r['censored'] for r in selected),
            'exceptional': sum(r['exceptional'] for r in selected),
            'meanWalkGroupOpsIncludingCensored': statistics.mean(walk),
            'medianWalkGroupOpsIncludingCensored': statistics.median(walk),
            'meanStartGroupOps': statistics.mean(r['startGroupOps'] for r in selected),
            'meanChargedGroupOps': statistics.mean(g[mode] for g in groups),
            'setupGroupOpsPerSeed': [tableCosts[s].get(mode, 0) for s in sorted(tableCosts)],
            'cycleAvoidance': sum(r['cycleAvoidance'] for r in selected),
            'restarts': sum(r['restarts'] for r in selected),
            'fruitlessCollisions': sum(r['fruitlessCollisions'] for r in selected),
            'observedEffectiveBranches': total * total / sum(v * v for v in histogram),
            'branchHistogram': histogram,
            'eligibleForComparison': useful == len(selected),
        }
    comparisons = []
    for baseline in ('legacy', 'weight8'):
        for candidate in ('orbit8', 'orbit16', 'orbit32', 'orbit64'):
            eligible = all(summaries[m]['eligibleForComparison'] for m in (baseline, candidate))
            comparisons.append({'baseline': baseline, 'candidate': candidate, 'eligible': eligible,
                                'chargedGroupOpsRatio': summaries[candidate]['meanChargedGroupOps'] /
                                                       summaries[baseline]['meanChargedGroupOps'] if eligible else None,
                                'tableClusterBootstrap95': bootstrapRatio(groups, baseline, candidate) if eligible else None})
    return {'modes': summaries, 'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--table-seeds', type=int, default=8)
    parser.add_argument('--trials', type=int, default=256)
    parser.add_argument('--cap', type=int, default=4096)
    parser.add_argument('--seed', type=int, default=20260921)
    parser.add_argument('--cxx', default='clang++')
    args = parser.parse_args()
    if not (2 <= args.table_seeds <= 128 and 1 <= args.trials <= 100000 and 1 <= args.cap <= 100000):
        parser.error('bounds: 2..128 table seeds, 1..100000 trials/cap')
    args.out.mkdir(parents=True, exist_ok=False)
    sourcePaths = [HERE / name for name in ('table.py', 'bench.cpp', 'run.py')]
    sourcePaths += [table.ROOT / p for p in ('codegen/field.py', 'codegen/curves.py',
                                           'include/bitslice.h', 'generated/eccF23.h')]
    before = {str(p.relative_to(table.ROOT)): digest(p) for p in sourcePaths}
    binary = args.out / 'bench'
    command = [args.cxx, '-O3', '-std=c++17', '-Wall', '-Wextra', '-Wno-unknown-pragmas',
               str(HERE / 'bench.cpp'), '-o', str(binary)]
    compiled = subprocess.run(command, text=True, capture_output=True, timeout=120)
    (args.out / 'build.log').write_text(compiled.stdout + compiled.stderr)
    compiled.check_returncode()
    rows, costs, identities = [], {}, []
    start = time.perf_counter()
    for index in range(args.table_seeds):
        seed = args.seed + index
        built = table.build(m=23, branches=64, seed=seed)
        identities.append(built['identitySha256'])
        (args.out / ('table-%d.json' % seed)).write_text(json.dumps(built, indent=2) + '\n')
        textPath = args.out / ('table-%d.txt' % seed)
        with textPath.open('x') as out:
            print(*built['generator'], *built['target'], file=out)
            for row in built['rows']:
                print(row['a'], row['b'], row['x'], row['y'], file=out)
        # Charge each table prefix's actual scalar-addition construction. This
        # excludes independent audit arithmetic and the optional extra rows.
        costs[seed] = {}
        for h in (8, 16, 32, 64):
            # Account for rejected rows too, recorded by their deterministic
            # attempt counters. The same arithmetic is used as in build().
            field, curve, base, target, ell, _ = table.instance(23)
            beforeOps = curve.groupOps
            for row in built['rows'][:h]:
                for attempt in range(row['attempt'] + 1):
                    a = table.coefficient(seed, row['branch'], 0, attempt, ell)
                    b = table.coefficient(seed, row['branch'], 1, attempt, ell)
                    curve.add(curve.mul(base, a), curve.mul(target, b))
            cost = curve.groupOps - beforeOps
            costs[seed]['orbit%d' % h] = cost
            costs[seed]['weight%d' % h] = cost
        rawPath = args.out / ('trials-%d.jsonl' % seed)
        runCommand = [str(binary.resolve()), str(textPath.resolve()), str(args.trials), str(args.cap), str(seed)]
        with rawPath.open('x') as out:
            result = subprocess.run(runCommand, text=True, stdout=out, stderr=subprocess.PIPE, timeout=600)
        (args.out / ('stderr-%d.log' % seed)).write_text(result.stderr)
        result.check_returncode()
        current = [json.loads(line) for line in rawPath.read_text().splitlines()]
        if len(current) != args.trials * len(MODES):
            raise RuntimeError('incomplete benchmark')
        pairs = {(r['mode'], r['trial']) for r in current}
        if pairs != {(mode, trial) for mode in MODES for trial in range(args.trials)}:
            raise RuntimeError('duplicate or missing trial')
        for row in current:
            if (sum(row['branches']) != row['steps'] or row['walkGroupOps'] != row['steps'] or
                    sum(bool(row[k]) for k in ('useful', 'exceptional', 'censored')) != 1):
                raise RuntimeError('inconsistent operation/termination accounting')
            row['seed'] = seed
        rows.extend(current)
        print('finished table %d/%d, %d trial rows' % (index + 1, args.table_seeds, len(current)), flush=True)
    after = {str(p.relative_to(table.ROOT)): digest(p) for p in sourcePaths}
    if before != after:
        raise RuntimeError('source changed during the experiment')
    report = {'schema': 'ecc2k-step-work-v1', 'scope': 'finite-GF(2^23)-synthetic',
              'gpuMeasured': False, 'm': 23, 'ell': 2095853, 'knownScalar': table.KNOWN,
              'orbitStates': (2095853 - 1) // 46,
              'idealBirthdayMean': math.sqrt(math.pi * ((2095853 - 1) / 46) / 2),
              'parameters': vars(args) | {'out': str(args.out)}, 'tableIdentities': identities,
              'sourceSha256': before, 'binarySha256': digest(binary), 'compileCommand': command,
              'compiler': subprocess.run([args.cxx, '--version'], capture_output=True, text=True, check=True).stdout,
              'platform': platform.platform(), 'wallSeconds': time.perf_counter() - start,
              'costDefinition': 'walk + start + table setup / trials; independent audits excluded',
              'walkLanesPerTrial': 8,
              'limitations': ['eight interleaved trails, all points retained; no distinguished-point transport/replay',
                              'history-based avoidance is not proof of coalescence for distributed walks',
                              'reference CPU elapsed time is not a GPU throughput comparison',
                              'finite subgroup/selector behavior cannot establish ECC2K-130 collision scaling'],
              **summarize(rows, costs, args.trials)}
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    for mode, item in report['modes'].items():
        print('%-8s walk=%8.3f charged=%8.3f useful=%d/%d effective-branches=%.3f' %
              (mode, item['meanWalkGroupOpsIncludingCensored'], item['meanChargedGroupOps'],
               item['usefulCollisions'], item['trials'], item['observedEffectiveBranches']))


if __name__ == '__main__':
    main()
