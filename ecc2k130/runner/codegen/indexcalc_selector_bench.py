"""Collect bounded, matched natural-query panels for the fixed IC selector.

All policies see the same target and pre-query matrix. Planted controls are
retained separately and excluded by the trainer. Whole signed Frobenius orbits
share one split, including across generators, bases, seeds and repetitions.
"""
import argparse
import json
from pathlib import Path
import random
import sys
import time

import indexcalc_fixed as fixed
import indexcalc_selector as selector


def rank(rows, prime):
    pivots = {}
    for original in rows:
        row = [x % prime for x in original]
        for i in range(len(row)):
            value = row[i]
            if not value:
                continue
            if i in pivots:
                row = [(a - value * b) % prime for a, b in zip(row, pivots[i])]
            else:
                inverse = pow(value, -1, prime)
                pivots[i] = [a * inverse % prime for a in row]
                break
    return len(pivots)


def encode(campaign, point):
    return None if point is None else [campaign.params.onb.toCoords(x) for x in point]


def collect(document, output, queries=64, seed=1701, repetitions=1,
            pairBudget=100000, seconds=.25, controls=4):
    fixed.require(1 <= queries <= 100000 and 1 <= repetitions <= 20 and 0 <= controls <= 1000,
                  'invalid panel bounds')
    fixed.require(0 < seconds <= 10, 'panel query budget must be between 0 and 10 seconds')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter_ns()
    with fixed.Campaign(document, output / 'campaign') as campaign:
        fixed.require(campaign.params.weight is not None, 'portfolio panel requires a Hamming-weight base')
        p = campaign.params
        ready = campaign.buildPairs(pairBudget)
        summary = {'format': selector.FORMAT, 'seed': seed, 'queries_requested': queries,
                   'repetitions': repetitions, 'pair_budget': pairBudget, 'query_seconds': seconds,
                   'common_ops': None, 'S': None, 'rho_ratio': None, 'floor_ratio': None,
                   'performance_promoted': False, 'status': 'pair_budget' if not ready else 'running'}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        if not ready:
            return summary
        campaign.prepareSat()
        summary['setup_ns'] = time.perf_counter_ns() - started
        domain_id = selector.domain(campaign, seconds)
        fixture = {'parameters': document, 'domain': domain_id,
                   'generator_onb': encode(campaign, p.generator),
                   'prime': str(p.prime), 'eigen': str(p.eigen),
                   'base': [encode(campaign, q) for q in campaign.points],
                   'representatives': [encode(campaign, q) for q in campaign.reps]}
        (output / 'fixture.json').write_text(json.dumps(fixture, indent=2) + '\n')
        histories = {name: [] for name in ('train', 'validation', 'confirmation')}
        rng = random.Random(seed)
        records = successes = 0
        with (output / 'queries.jsonl').open('w') as stream:
            for number in range(queries + controls):
                origin = 'natural' if number < queries else 'planted'
                generation = time.perf_counter_ns()
                if origin == 'natural':
                    target = p.curve.mul(p.generator, rng.randrange(1, p.prime))
                else:
                    for _ in range(1000):
                        ids = [rng.randrange(len(campaign.points)) for _ in range(p.summands)]
                        actual = [campaign.points[i] for i in ids]
                        if not fixed.engine.proper(actual, [1] * p.summands, p.curve):
                            continue
                        target = None
                        for q in actual:
                            target = p.curve.add(target, q)
                        if target is not None:
                            break
                    else:
                        raise ValueError('could not construct a nontrivial planted control')
                generation = time.perf_counter_ns() - generation
                orbit_id = selector.orbit(campaign, target)
                history = histories[selector.split(orbit_id)]
                direct = number % 2 == 1
                wanted = number % (len(campaign.reps) + int(direct))
                prior = history[:wanted]
                prior_rows = [r['row'] + ([0] if direct else []) for r in prior]
                before = rank(prior_rows, p.prime)
                feature_start = time.perf_counter_ns()
                values = selector.features(campaign, target, before, direct)
                feature_ns = time.perf_counter_ns() - feature_start
                canonical = None
                for repetition in range(repetitions):
                    outcomes = {}
                    arms = list(selector.ARMS)
                    # Rotate order so no policy always inherits the first-call effects.
                    offset = (number + repetition) % len(arms)
                    for arm in arms[offset:] + arms[:offset]:
                        tick = time.perf_counter_ns()
                        try:
                            witness, details = campaign.decomposePolicy(target, seconds, arm)
                            row = None if witness is None else campaign.verify(witness, target)
                            gain = int(row is not None and rank(prior_rows + [row + ([-1 % p.prime] if direct else [])], p.prime) > before)
                            result = {'status': details['status'], 'verified': witness is not None,
                                      'gain': gain, 'witness': witness, 'row': row, 'details': details}
                            if arm == 'pairs' and row is not None:
                                canonical = {'row': row, 'witness': witness, 'target': encode(campaign, target)}
                        except Exception as error:
                            result = {'status': 'error', 'verified': False, 'gain': 0,
                                      'message': str(error), 'exception': type(error).__name__}
                        result['elapsed_ns'] = time.perf_counter_ns() - tick + feature_ns
                        outcomes[arm] = result
                    record = {'format': selector.FORMAT, 'domain': domain_id,
                              'query_id': selector.digest([seed, number, encode(campaign, target)]),
                              'number': number, 'repetition': repetition, 'origin': origin,
                              'orbit': orbit_id, 'split': selector.split(orbit_id),
                              'target': encode(campaign, target), 'features': values,
                              'prior_relations': prior, 'rank_before': before,
                              'generation_ns': generation, 'feature_ns': feature_ns, 'outcomes': outcomes}
                    stream.write(json.dumps(record, sort_keys=True) + '\n')
                    stream.flush()
                    records += 1
                    successes += int(outcomes['pairs']['verified'])
                # Controls never supply natural-query matrix history.
                if origin == 'natural' and canonical is not None and rank([r['row'] for r in history] + [canonical['row']], p.prime) > len(history):
                    history.append(canonical)
                if (number + 1) % 16 == 0:
                    print(f'{output.name}: {number + 1}/{queries + controls} queries', file=sys.stderr, flush=True)
        summary.update(status='complete', records=records, pair_verified=successes,
                       accounting=campaign.ledger.report())
    summary['full_collection_ns'] = time.perf_counter_ns() - started
    summary['cost_scope'] = 'full collection includes validation, pair/circuit setup, all policy calls, feature extraction, labels, serialization and DB close; query elapsed is warm diagnostic only'
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--params', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--queries', type=int, default=64)
    parser.add_argument('--seed', type=int, default=1701)
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--pair-budget', type=int, default=100000)
    parser.add_argument('--query-seconds', type=float, default=.25)
    parser.add_argument('--controls', type=int, default=4)
    args = parser.parse_args()
    result = collect(fixed.readJson(args.params), args.out, args.queries, args.seed,
                     args.repetitions, args.pair_budget, args.query_seconds, args.controls)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'complete' else 2


if __name__ == '__main__':
    sys.exit(main())
