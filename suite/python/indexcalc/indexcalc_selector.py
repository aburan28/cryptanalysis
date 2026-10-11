"""Cost-sensitive, JSON-only solver selection for prepared fixed IC campaigns.

Train on matched natural-query panels produced by indexcalc_selector_bench.py.
No scalar, witness, solver result or post-query statistic is an input feature.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


FORMAT = 'fixed-ic-selector-v1'
ARMS = {'pairs': 0.0, 'sat-short': 0.1, 'sat-medium': 0.5}
FEATURES = ('x_weight', 'x_frobenius_distance', 'rank_fraction', 'direct_target')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def domain(campaign, seconds):
    p = campaign.params
    # Generator and target changes do not change the decomposition problem.
    return digest({'degree': p.onb.m, 'order': str(p.prime), 'summands': p.summands,
                   'base': [[p.onb.toCoords(x), p.onb.toCoords(y)] for x, y in campaign.points],
                   'seconds': float(seconds)})


def features(campaign, target, rank=0, direct=False):
    p = campaign.params
    x = 0 if target is None else p.onb.toCoords(target[0])
    squared = 0 if target is None else p.onb.toCoords(p.onb.frob(target[0], 1))
    return {'x_weight': x.bit_count(), 'x_frobenius_distance': (x ^ squared).bit_count(),
            'rank_fraction': rank / (len(campaign.reps) + int(direct)),
            'direct_target': int(direct)}


def orbit(campaign, target):
    p = campaign.params
    members = []
    for _ in range(p.onb.m):
        for q in (target, p.curve.neg(target)):
            members.append(None if q is None else [p.onb.toCoords(q[0]), p.onb.toCoords(q[1])])
        target = p.curve.frob(target)
    representative = min(members) if target is not None else None
    return digest([p.onb.m, str(p.prime), representative])


def split(orbit_id):
    return ('train', 'train', 'train', 'validation', 'confirmation')[int(orbit_id, 16) % 5]


def validateFeatures(values):
    require(isinstance(values, dict) and set(values) == set(FEATURES), 'invalid selector feature names')
    require(all(type(v) in (int, float) and math.isfinite(v) for v in values.values()),
            'selector features must be finite numbers')
    require(0 <= values['rank_fraction'] <= 1 and values['direct_target'] in (0, 1),
            'invalid matrix-state features')
    require(all(values[k] >= 0 for k in FEATURES[:2]), 'negative coordinate feature')


def leaf(arm):
    return {'arm': arm}


def route(tree, values):
    while 'arm' not in tree:
        tree = tree['left' if values[tree['feature']] <= tree['threshold'] else 'right']
    return tree['arm']


def validateTree(tree, depth=0):
    require(isinstance(tree, dict) and depth <= 3, 'invalid selector tree or depth')
    if set(tree) == {'arm'}:
        require(tree['arm'] in ARMS, 'unknown selector arm')
        return
    require(set(tree) == {'feature', 'threshold', 'left', 'right'}, 'invalid selector node')
    require(tree['feature'] in FEATURES and type(tree['threshold']) in (int, float)
            and math.isfinite(tree['threshold']), 'invalid selector split')
    validateTree(tree['left'], depth + 1)
    validateTree(tree['right'], depth + 1)


class Model:
    def __init__(self, document):
        require(isinstance(document, dict) and document.get('format') == FORMAT, 'unsupported selector model')
        require(document.get('arms') == ARMS and document.get('features') == list(FEATURES),
                'selector policy or feature schema mismatch')
        require(document.get('fallback') == 'pairs', 'selector fallback must be pairs')
        self.tree = document.get('tree')
        validateTree(self.tree)
        self.domains = document.get('domains')
        require(isinstance(self.domains, dict) and self.domains, 'model has no observed domains')
        for key, ranges in self.domains.items():
            require(isinstance(key, str) and len(key) == 64 and isinstance(ranges, dict) and set(ranges) == set(FEATURES),
                    'invalid model domain')
            for bounds in ranges.values():
                require(isinstance(bounds, list) and len(bounds) == 2
                        and all(type(x) in (int, float) and math.isfinite(x) for x in bounds)
                        and bounds[0] <= bounds[1], 'invalid model feature bounds')
        self.document = document
        self.hash = digest(document)

    def select(self, domain_id, values):
        validateFeatures(values)
        ranges = self.domains.get(domain_id)
        if ranges is None:
            return 'pairs', 'unseen_parameters_or_budget'
        if any(not ranges[k][0] <= values[k] <= ranges[k][1] for k in FEATURES):
            return 'pairs', 'unseen_feature_range'
        return route(self.tree, values), 'model'


def validateData(records):
    require(isinstance(records, list) and records, 'empty query dataset')
    seen = set()
    for r in records:
        require(r.get('format') == FORMAT and r.get('origin') in ('natural', 'planted'), 'invalid query record')
        require(r.get('split') == split(r['orbit']), 'incorrect orbit holdout assignment')
        validateFeatures(r['features'])
        key = r['domain'], r['query_id'], r['repetition']
        require(key not in seen, 'duplicate matched query')
        seen.add(key)
        require(set(r['outcomes']) == set(ARMS), 'every query must retain every policy outcome')
        for result in r['outcomes'].values():
            require(type(result.get('elapsed_ns')) is int and result['elapsed_ns'] > 0, 'invalid query cost')
            require(type(result.get('gain')) is int and result['gain'] in (0, 1), 'invalid rank gain')
            require(type(result.get('verified')) is bool and (not result['gain'] or result['verified']),
                    'rank gain requires a verified witness')
            require(result.get('status') != 'error', 'solver errors invalidate training; retain and fix the panel')


def loss(record, arm, penalty):
    o = record['outcomes'][arm]
    return o['elapsed_ns'] + penalty * (1 - o['gain'])


def bestArm(records, penalty):
    return min(ARMS, key=lambda arm: sum(loss(r, arm, penalty) for r in records))


def grow(records, penalty, depth=0):
    arm = bestArm(records, penalty)
    best = sum(loss(r, arm, penalty) for r in records)
    candidate = None
    if depth == 3 or len({r['orbit'] for r in records}) < 16:
        return leaf(arm)
    for feature in FEATURES:
        values = sorted(set(r['features'][feature] for r in records))
        for low, high in zip(values, values[1:]):
            threshold = (low + high) / 2
            left = [r for r in records if r['features'][feature] <= threshold]
            right = [r for r in records if r['features'][feature] > threshold]
            # Repeated measurements do not count as independent training cases.
            if min(len({r['orbit'] for r in part}) for part in (left, right)) < 8:
                continue
            score = sum(sum(loss(r, bestArm(part, penalty), penalty) for r in part) for part in (left, right))
            if score < best:
                best, candidate = score, (feature, threshold, left, right)
    if candidate is None:
        return leaf(arm)
    feature, threshold, left, right = candidate
    return {'feature': feature, 'threshold': threshold,
            'left': grow(left, penalty, depth + 1), 'right': grow(right, penalty, depth + 1)}


def metrics(records, policy, penalty):
    cost = gains = verified = 0
    score = 0.0
    for r in records:
        arm = policy(r)
        o = r['outcomes'][arm]
        cost += o['elapsed_ns']
        gains += o['gain']
        verified += o['verified']
        score += loss(r, arm, penalty)
    return {'queries': len(records), 'verified': verified, 'rank_gains': gains, 'elapsed_ns': cost,
            'ns_per_rank_gain': cost / gains if gains else None, 'penalized_loss_ns': score}


def train(records):
    validateData(records)
    natural = [r for r in records if r['origin'] == 'natural']
    training = [r for r in natural if r['split'] == 'train']
    validation = [r for r in natural if r['split'] == 'validation']
    require(training and validation, 'need nonempty orbit-disjoint training and validation panels')
    gains = {o['gain'] for r in training for o in r['outcomes'].values()}
    require(gains == {0, 1}, 'training needs both natural rank gains and non-gains; planted controls cannot supply labels')
    rates = []
    for arm in ARMS:
        gain = sum(r['outcomes'][arm]['gain'] for r in training)
        if gain:
            rates.append(sum(r['outcomes'][arm]['elapsed_ns'] for r in training) / gain)
    penalty = min(rates)
    static = bestArm(training, penalty)
    tree = grow(training, penalty)
    domains = {}
    for r in training:
        ranges = domains.setdefault(r['domain'], {k: [r['features'][k]] * 2 for k in FEATURES})
        for k in FEATURES:
            ranges[k] = [min(ranges[k][0], r['features'][k]), max(ranges[k][1], r['features'][k])]
    document = {'format': FORMAT, 'features': list(FEATURES), 'arms': ARMS, 'fallback': 'pairs',
                'domains': domains, 'tree': tree,
                'training': {'dataset_sha256': digest(records), 'natural_queries': len(training),
                             'natural_orbits': len({r['orbit'] for r in training}),
                             'planted_excluded': sum(r['origin'] == 'planted' for r in records),
                             'penalty_ns': penalty, 'best_static_arm': static}}
    proposed = Model(document)
    candidate = metrics(validation, lambda r: proposed.select(r['domain'], r['features'])[0], penalty)
    constant = Model(dict(document, tree=leaf(static)))
    control = metrics(validation, lambda r: constant.select(r['domain'], r['features'])[0], penalty)
    improvement = 1 - candidate['penalized_loss_ns'] / control['penalized_loss_ns']
    admitted = improvement >= .05
    if not admitted:
        document['tree'] = leaf(static)
    document['validation'] = {'tree_loss_improvement': improvement, 'gate': .05,
                              'decision': 'tree' if admitted else 'constant_no_routing_gain',
                              'candidate': candidate, 'constant': control}
    model = Model(document)
    report = {'format': FORMAT, 'model_sha256': model.hash, 'validation': document['validation'],
              'training': document['training'], 'splits': {}, 'common_ops': None, 'S': None,
              'rho_ratio': None, 'floor_ratio': None, 'performance_promoted': False}
    for name in ('train', 'validation', 'confirmation'):
        rows = [r for r in natural if r['split'] == name]
        report['splits'][name] = {arm: metrics(rows, lambda r, a=arm: a, penalty) for arm in ARMS}
        report['splits'][name]['selector'] = metrics(rows, lambda r: model.select(r['domain'], r['features'])[0], penalty)
        report['splits'][name]['hindsight_oracle'] = metrics(rows, lambda r: bestArm([r], penalty), penalty)
    return document, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', nargs='+', required=True, help='matched JSONL query panels')
    parser.add_argument('--out', required=True, help='model JSON; report saved alongside as .report.json')
    args = parser.parse_args()
    records = []
    for filename in args.data:
        records.extend(json.loads(line) for line in Path(filename).read_text().splitlines() if line.strip())
    model, report = train(records)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), 'model already exists; use a new output path to preserve locked models')
    path.write_text(json.dumps(model, indent=2, sort_keys=True) + '\n')
    path.with_suffix('.report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
