"""Persistent index calculus for fixed K_0 parameters in a type-II normal basis.

Python integers retain the full field width. SQLite transactions preserve pair
construction, probe cursors and verified relations across process restarts.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import time

import curves
import decomp
import indexcalc_e2e as engine
import indexcalc_selector as selector


FORMAT = 'fixed-koblitz-ic-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def integer(value):
    require(type(value) in (int, str), 'integers must be decimal or hexadecimal strings or JSON integers')
    try:
        result = int(value, 16 if value.lower().startswith('0x') else 10) if isinstance(value, str) else value
    except ValueError as error:
        raise ValueError('invalid integer') from error
    require(result >= 0, 'negative coordinates or scalars are invalid')
    return result


def keys(value, required, optional=()):
    require(isinstance(value, dict), 'expected an object')
    require(set(required) <= value.keys() and value.keys() <= set(required) | set(optional),
            'missing or unknown fields: expected ' + ', '.join(required))


def readJson(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    with open(path) as stream:
        return json.load(stream, object_pairs_hook=unique)


class Parameters:
    def __init__(self, document, ledger):
        keys(document, ['schema_version', 'curve', 'generator', 'factor_base', 'summands', 'targets'], ['name'])
        require(type(document['schema_version']) is int and document['schema_version'] == 1,
                'unsupported parameter schema')
        spec = document['curve']
        keys(spec, ['family', 'degree', 'basis', 'subgroup_order', 'cofactor'], ['polynomial', 'onb_root'])
        require(spec['family'] == 'koblitz-a0', 'supported family: y^2 + xy = x^3 + 1')
        m = integer(spec['degree'])
        require(3 <= m <= 131 and m % 2 == 1, 'degree must be odd, between 3 and 131')
        self.onb = engine.AuditField(m, ledger)
        self.curve = engine.AuditCurve(self.onb, ledger)
        self.prime = integer(spec['subgroup_order'])
        require(integer(spec['cofactor']) == 4 and curves.curveOrder(m) == 4 * self.prime
                and curves.isPrimeBig(self.prime), 'expected curve order = 4 * prime subgroup order')
        self.images = None
        require(spec['basis'] in ('type-ii-onb', 'polynomial'), 'unknown coordinate basis')
        if spec['basis'] == 'polynomial':
            require('polynomial' in spec and 'onb_root' in spec,
                    'polynomial coordinates require polynomial and onb_root')
            polynomial = integer(spec['polynomial'])
            require(polynomial.bit_length() == m + 1 and polynomial & 1,
                    'invalid degree-m binary polynomial')
            root = self.coordinate(spec['onb_root'])
            power, images = self.onb.one(), []
            value = 0
            for i in range(m + 1):
                if polynomial >> i & 1:
                    value = self.onb.add(value, power)
                if i < m:
                    images.append(self.onb.toCoords(power))
                power = self.onb.mul(power, root)
            require(value == 0, 'onb_root is not a root of the declared polynomial')
            pivots = {}
            for image in images:
                while image:
                    pivot = image.bit_length() - 1
                    if pivot not in pivots:
                        pivots[pivot] = image
                        break
                    image ^= pivots[pivot]
            require(len(pivots) == m, 'basis conversion is singular')
            self.images = images
        else:
            require('polynomial' not in spec and 'onb_root' not in spec,
                    'polynomial fields do not apply to ONB coordinates')
        self.generator = self.point(document['generator'])
        self.eigen = curves.frobeniusEigenvalue(self.curve, self.generator, self.prime)
        require(pow(self.eigen, m, self.prime) == 1, 'invalid Frobenius eigenvalue')
        base = document['factor_base']
        require(isinstance(base, dict), 'factor_base must be an object')
        if base.get('kind') == 'hamming-weight':
            keys(base, ['kind', 'weight'])
            self.weight = integer(base['weight'])
            require(1 <= self.weight <= (2 if m > 31 else 4),
                    'materialized Hamming bases allow weight <=2 above degree 31, <=4 otherwise')
            self.explicit = None
        else:
            keys(base, ['kind', 'representatives'])
            require(base['kind'] == 'explicit-orbits', 'unknown factor-base kind')
            require(isinstance(base['representatives'], list) and 0 < len(base['representatives']) <= 4096,
                    'supply between 1 and 4096 explicit orbit representatives')
            self.explicit = [self.point(p) for p in base['representatives']]
            self.weight = None
        self.summands = integer(document['summands'])
        require(self.summands in (2, 3), 'fixed workflow supports two or three summands')
        require(isinstance(document['targets'], list), 'targets must be an array')
        self.targets = {}
        for target in document['targets']:
            keys(target, ['id', 'x', 'y'])
            name = target['id']
            require(isinstance(name, str) and 0 < len(name) <= 128 and name not in self.targets,
                    'target IDs must be unique nonempty strings of at most 128 characters')
            self.targets[name] = self.point({'x': target['x'], 'y': target['y']})
        # Target-independent precomputation survives adding or removing targets.
        identity = {k: document[k] for k in ('schema_version', 'curve', 'generator', 'factor_base', 'summands')}
        self.identity = digest([FORMAT, identity])
        self.document = document

    def coordinate(self, value):
        value = integer(value)
        require(value < 1 << self.onb.m, 'coordinate exceeds the declared field width')
        return self.onb.fromCoords(value)

    def point(self, value):
        keys(value, ['x', 'y'])
        coordinates = []
        for axis in ('x', 'y'):
            number = integer(value[axis])
            require(number < 1 << self.onb.m, 'coordinate exceeds the declared field width')
            if self.images is not None:
                mapped = 0
                for i, image in enumerate(self.images):
                    if number >> i & 1:
                        mapped ^= image
                number = mapped
            coordinates.append(self.onb.fromCoords(number))
        point = tuple(coordinates)
        require(self.curve.onCurve(point), 'point is not on the declared curve')
        require(self.curve.mul(point, self.prime) is None, 'point is outside the declared prime subgroup')
        return point


def pointKey(point):
    return 'identity' if point is None else format(point[0], 'x') + ':' + format(point[1], 'x')


class Campaign:
    def __init__(self, document, directory, solver='pairs', memory=False, selectorModel=None):
        require(__debug__, 'run without Python -O; the shared arithmetic engine uses assertions')
        self.ledger = engine.Ledger()
        self.uses = Counter()
        self.started = time.perf_counter_ns()
        self.db = None
        self.lock = None
        try:
            with self.ledger.phase('parameter_validation'):
                self.params = Parameters(document, self.ledger)
            require(solver in ('pairs', 'sat', 'learned'), 'unknown decomposition solver')
            require((solver == 'learned') == (selectorModel is not None),
                    '--selector-model is required exactly when --solver learned is used')
            require(solver != 'sat' or self.params.weight is not None,
                    'SAT requires the Hamming-weight factor-base recipe')
            self.solver = solver
            path = Path(directory)
            if not memory:
                import fcntl
                path.mkdir(parents=True, exist_ok=True)
                self.lock = open(path / 'campaign.lock', 'a')
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise ValueError('campaign is in use; use one writer per directory') from error
            self.db = sqlite3.connect(':memory:' if memory else path / 'campaign.sqlite3')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pairs (serial INTEGER PRIMARY KEY, point TEXT NOT NULL,
                    first INTEGER NOT NULL, second INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS pair_lookup ON pairs(point);
                CREATE TABLE IF NOT EXISTS attempts (stream TEXT NOT NULL, number INTEGER NOT NULL,
                    result TEXT NOT NULL, PRIMARY KEY(stream,number));
                CREATE TABLE IF NOT EXISTS relations (stream TEXT NOT NULL, number INTEGER NOT NULL,
                    witness TEXT NOT NULL, coefficients TEXT NOT NULL, a TEXT NOT NULL, b TEXT NOT NULL,
                    PRIMARY KEY(stream,number));
                CREATE TABLE IF NOT EXISTS targets (id TEXT PRIMARY KEY, point TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS solutions (id TEXT PRIMARY KEY, scalar TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS invocations (number INTEGER PRIMARY KEY, report TEXT NOT NULL);
            ''')
            with self.db:
                saved = self.meta('identity')
                require(saved is None or saved == self.params.identity,
                        'campaign parameters differ; use a new directory for a different curve or factor base')
                self.put('identity', self.params.identity)
                self.put('parameters', {k: v for k, v in document.items() if k != 'targets'})
                for name, point in self.params.targets.items():
                    prior = self.db.execute('SELECT point FROM targets WHERE id=?', (name,)).fetchone()
                    require(prior is None or prior[0] == pointKey(point), 'target ID was already bound to another point')
                    self.db.execute('INSERT OR IGNORE INTO targets VALUES (?,?)', (name, pointKey(point)))
            self.base()
            self.context = None
            self.selector = None
            self.selectorDomains = {}
            self.queryRank, self.queryDirect = 0, False
            if solver == 'learned':
                with self.ledger.phase('selector_load'):
                    self.selector = selector.Model(readJson(selectorModel))
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.lock is not None:
            self.lock.close()
            self.lock = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def meta(self, name):
        row = self.db.execute('SELECT value FROM metadata WHERE name=?', (name,)).fetchone()
        return None if row is None else json.loads(row[0])

    def put(self, name, value):
        self.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', (name, canonical(value)))

    def base(self):
        p = self.params
        with self.ledger.phase('factor_base'):
            saved = self.meta('base')
            if saved is None:
                if p.explicit is None:
                    reps, _ = engine.subgroupBase(p.onb, p.curve, p.prime, p.eigen, p.weight)
                else:
                    reps = p.explicit
                payload = [[hex(p.onb.toCoords(x)), hex(p.onb.toCoords(y))] for x, y in reps]
                with self.db:
                    self.put('base', {'points': payload, 'hash': digest(payload)})
                self.uses['base_builds'] += 1
            else:
                require(digest(saved['points']) == saved['hash'], 'factor-base checksum mismatch')
                reps = [tuple(p.coordinate(v) for v in point) for point in saved['points']]
                self.uses['base_loads'] += 1
            self.reps, self.lookup = reps, {}
            require(bool(reps), 'empty factor base')
            for column, rep in enumerate(reps):
                require(p.curve.onCurve(rep) and p.curve.mul(rep, p.prime) is None,
                        'invalid factor-base subgroup point')
                if p.weight is not None:
                    require(0 < p.onb.toCoords(rep[0]).bit_count() <= p.weight,
                            'factor-base point violates its Hamming-weight recipe')
                point, coefficient = rep, 1
                for _ in range(p.onb.m):
                    for signed, coeff in ((point, coefficient), (p.curve.neg(point), -coefficient % p.prime)):
                        old = self.lookup.get(signed)
                        require(old is None or old == (column, coeff), 'overlapping or inconsistent Frobenius orbits')
                        self.lookup[signed] = (column, coeff)
                    point = p.curve.frob(point)
                    coefficient = coefficient * p.eigen % p.prime
            self.points = sorted(self.lookup)
            self.index = {point: i for i, point in enumerate(self.points)}
            self.baseHash = digest([pointKey(point) for point in self.points])
            require(self.meta('base_order') in (None, self.baseHash), 'factor-base ordering changed')
            with self.db:
                self.put('base_order', self.baseHash)

    def buildPairs(self, budget):
        """Build at most budget candidate pairs; each chunk and cursor commit together."""
        require(type(budget) is int and budget >= 0, 'pair budget must be nonnegative')
        size = len(self.points)
        with self.ledger.phase('pair_table'):
            state = self.meta('pair_state') or {'i': 0, 'j': 0, 'serial': 0, 'hash': '0' * 64}
            self.checkPairs(state)
            if state['i'] == size:
                self.uses['pair_table_loads'] += 1
                return True
            done = 0
            while done < budget and state['i'] < size:
                with self.db:
                    for _ in range(min(256, budget - done)):
                        i, j = state['i'], state['j']
                        if i == size:
                            break
                        left, right = self.points[i], self.points[j]
                        if left != self.params.curve.neg(right):
                            key = pointKey(self.params.curve.add(left, right))
                            serial = state['serial']
                            self.db.execute('INSERT INTO pairs VALUES (?,?,?,?)', (serial, key, i, j))
                            state['hash'] = digest([state['hash'], serial, key, i, j])
                            state['serial'] += 1
                        state['j'] += 1
                        if state['j'] == size:
                            state['i'] += 1
                            state['j'] = state['i']
                        done += 1
                        self.uses['pair_candidates_built'] += 1
                    self.put('pair_state', state)
            return state['i'] == size

    def checkPairs(self, state):
        size = len(self.points)
        require(0 <= state['i'] <= size and state['i'] <= state['j'] <= size,
                'invalid pair-table cursor')
        value, count = '0' * 64, 0
        for serial, key, i, j in self.db.execute('SELECT serial,point,first,second FROM pairs ORDER BY serial'):
            require(serial == count and 0 <= i <= j < size, 'invalid pair-table record')
            value = digest([value, serial, key, i, j])
            count += 1
        considered = state['i'] * size - state['i'] * (state['i'] - 1) // 2 + state['j'] - state['i']
        excluded = sum(1 for i, point in enumerate(self.points)
                       if i <= self.index[self.params.curve.neg(point)] and
                       (i < state['i'] or (i == state['i'] and self.index[self.params.curve.neg(point)] < state['j'])))
        require(count == considered - excluded, 'pair-table cursor does not match its records')
        require(count == state['serial'] and value == state['hash'], 'pair-table checksum mismatch')
        require(self.meta('pair_state') is not None or count == 0, 'pair table has no checkpoint')

    def verify(self, witness, target):
        require(isinstance(witness, list) and len(witness) == self.params.summands,
                'invalid decomposition witness length')
        require(all(type(i) is int and 0 <= i < len(self.points) for i in witness), 'invalid witness point index')
        actual = [self.points[i] for i in witness]
        require(engine.proper(actual, [1] * len(actual), self.params.curve), 'inverse-cancelling relation')
        total, row = None, [0] * len(self.reps)
        for point in actual:
            total = self.params.curve.add(total, point)
            column, coeff = self.lookup[point]
            row[column] = (row[column] + coeff) % self.params.prime
        require(total == target, 'decomposition does not sum to the target')
        transported = None
        for coeff, point in zip(row, self.reps):
            transported = self.params.curve.add(transported, self.params.curve.mul(point, coeff))
        require(transported == target, 'orbit coefficients do not reconstruct the target')
        return row

    def prepareSat(self):
        require(self.params.weight is not None, 'SAT requires the Hamming-weight factor-base recipe')
        if self.context is None:
            with self.ledger.phase('symbolic_setup'):
                p = self.params
                prog, roots = decomp.buildSystem(p.onb.m, p.onb.n, p.summands, 12)
                self.context = (p.onb, p.curve, p.prime, p.generator, p.eigen,
                                self.reps, self.lookup, prog, roots)

    def decomposePolicy(self, target, seconds, arm):
        require(arm in selector.ARMS, 'unknown solver policy')
        fraction = selector.ARMS[arm]
        trace = []
        witness = None
        if fraction:
            started = time.perf_counter_ns()
            witness, details = self.decomposeExact(target, seconds * fraction, 'sat')
            trace.append({'solver': 'sat', 'budget_seconds': seconds * fraction,
                          'elapsed_ns': time.perf_counter_ns() - started, 'result': details})
        if witness is None:
            started = time.perf_counter_ns()
            witness, details = self.decomposeExact(target, seconds * (1 - fraction), 'pairs')
            trace.append({'solver': 'pairs', 'budget_seconds': seconds * (1 - fraction),
                          'elapsed_ns': time.perf_counter_ns() - started, 'result': details})
        return witness, {'status': 'verified' if witness is not None else details['status'],
                         'policy': arm, 'calls': trace}

    def decompose(self, target, seconds):
        if self.selector is None:
            return self.decomposeExact(target, seconds, self.solver)
        started = time.perf_counter_ns()
        with self.ledger.phase('selector_inference'):
            if seconds not in self.selectorDomains:
                self.selectorDomains[seconds] = selector.domain(self, seconds)
            values = selector.features(self, target, self.queryRank, self.queryDirect)
            arm, reason = self.selector.select(self.selectorDomains[seconds], values)
            if self.params.weight is None and arm != 'pairs':
                arm, reason = 'pairs', 'sat_unavailable_for_explicit_base'
        inference = time.perf_counter_ns() - started
        self.uses['selector_queries'] += 1
        self.uses['selector_policy_' + arm] += 1
        self.uses['selector_reason_' + reason] += 1
        witness, details = self.decomposePolicy(target, seconds, arm)
        details['selector'] = {'model_sha256': self.selector.hash, 'features': values,
                               'reason': reason, 'inference_ns': inference}
        return witness, details

    def decomposeExact(self, target, seconds, solver):
        require(solver in ('pairs', 'sat'), 'unknown exact solver')
        if target is None:
            return None, {'status': 'identity_excluded'}
        if solver == 'sat':
            self.prepareSat()
            row, details = engine.decompose(self.context, target, self.params.summands,
                self.params.weight, 'candidate', self.ledger, budget=seconds)
            if row is None:
                return None, details
            with self.ledger.phase('witness_verification'):
                lifted = engine.strictLift(self.params.onb, self.params.curve,
                    details['x_coordinates'], target, self.lookup)
                require(lifted is not None, 'SAT result failed independent lifting')
                actual, signs = lifted
                witness = [self.index[self.params.curve.neg(point) if sign < 0 else point]
                           for point, sign in zip(actual, signs)]
                require(self.verify(witness, target) == row, 'SAT row and witness disagree')
            return witness, details
        state = self.meta('pair_state')
        require(state is not None and state['i'] == len(self.points), 'pair table is incomplete')
        deadline = time.monotonic() + seconds
        with self.ledger.phase('decomposition'):
            prefixes = [(None, None)] if self.params.summands == 2 else enumerate(self.points)
            for first, point in prefixes:
                if time.monotonic() >= deadline:
                    return None, {'status': 'budget'}
                residual = target if first is None else self.params.curve.add(target, self.params.curve.neg(point))
                self.ledger.counts['pairs.lookups'] += 1
                for i, j in self.db.execute('SELECT first,second FROM pairs WHERE point=? ORDER BY serial',
                                             (pointKey(residual),)):
                    if time.monotonic() >= deadline:
                        return None, {'status': 'budget'}
                    witness = [i, j] if first is None else [first, i, j]
                    actual = [self.points[index] for index in witness]
                    if engine.proper(actual, [1] * len(actual), self.params.curve):
                        self.verify(witness, target)
                        return witness, {'status': 'verified'}
            return None, {'status': 'unsat'}

    def probe(self, stream, number):
        # Rejection sampling avoids modulo bias; the immutable stream/counter
        # makes an interrupted probe reproducible without saving PRNG internals.
        def scalar(label):
            counter = 0
            size = (self.params.prime.bit_length() + 7) // 8
            while True:
                value = int.from_bytes(hashlib.shake_256(canonical(
                    [FORMAT, self.params.identity, stream, number, label, counter]).encode()).digest(size), 'big')
                value &= (1 << self.params.prime.bit_length()) - 1
                if 0 < value < self.params.prime:
                    return value
                counter += 1
        a, b = scalar('a'), 0 if stream == 'precompute' else scalar('b')
        target = self.params.curve.mul(self.params.generator, a)
        if b:
            target = self.params.curve.add(target, self.params.curve.mul(self.params.targets[stream[7:]], b))
        return a, b, target

    def matrix(self, targetName=None):
        size = len(self.reps) + (targetName is not None)
        matrix = engine.RelationMatrix(size, self.params.prime, self.ledger)
        streams = ['precompute'] + ([] if targetName is None else ['target:' + targetName])
        with self.ledger.phase('relation_replay'):
            for stream in streams:
                for number, encoded, coefficients, a, b in self.db.execute(
                        'SELECT number,witness,coefficients,a,b FROM relations WHERE stream=? ORDER BY number', (stream,)):
                    expectedA, expectedB, target = self.probe(stream, number)
                    require(integer(a) == expectedA and integer(b) == expectedB, 'relation probe coefficients changed')
                    row = self.verify(json.loads(encoded), target)
                    require(row == json.loads(coefficients), 'saved relation coefficients changed')
                    self.push(matrix, row, expectedA, expectedB, targetName is not None)
                    self.uses['relations_replayed'] += 1
        return matrix

    def push(self, matrix, row, a, b, direct):
        try:
            return matrix.push(row + ([-b % self.params.prime] if direct else []), a)
        except AssertionError as error:
            raise ValueError('inconsistent relation matrix') from error

    def collect(self, attempts, seconds, targetName=None, matrix=None):
        stream = 'precompute' if targetName is None else 'target:' + targetName
        matrix = self.matrix(targetName) if matrix is None else matrix
        cursor = self.db.execute('SELECT COALESCE(MAX(number)+1,0) FROM attempts WHERE stream=?', (stream,)).fetchone()[0]
        for _ in range(attempts):
            if (targetName is None and matrix.solution() is not None) or (
                    targetName is not None and len(self.reps) in matrix.rows):
                break
            with self.ledger.phase('probe_generation'):
                a, b, target = self.probe(stream, cursor)
            self.queryRank, self.queryDirect = len(matrix.rows), targetName is not None
            witness, details = self.decompose(target, seconds)
            details['solver'] = self.solver
            with self.ledger.phase('relation_commit'):
                with self.db:
                    if witness is not None:
                        row = self.verify(witness, target)
                        independent = self.push(matrix, row, a, b, targetName is not None)
                        details['independent'] = independent
                        self.db.execute('INSERT INTO relations VALUES (?,?,?,?,?,?)',
                            (stream, cursor, canonical(witness), canonical(row), str(a), str(b)))
                        self.uses['new_relations'] += 1
                        self.uses['new_independent_relations'] += int(independent)
                    self.db.execute('INSERT INTO attempts VALUES (?,?,?)', (stream, cursor, canonical(details)))
                self.uses['new_attempts'] += 1
            cursor += 1
        return matrix

    def logs(self, matrix=None):
        with self.ledger.phase('log_load'):
            logs = self.meta('logs')
            if logs is not None:
                self.certifyLogs(logs)
                self.uses['log_database_loads'] += 1
                return logs
        matrix = self.matrix() if matrix is None else matrix
        logs = matrix.solution()
        if logs is not None:
            with self.ledger.phase('log_certification'):
                self.certifyLogs(logs)
                with self.db:
                    self.put('logs', logs)
                self.uses['log_database_builds'] += 1
        return logs

    def certifyLogs(self, logs):
        require(isinstance(logs, list) and len(logs) == len(self.reps), 'invalid logarithm database size')
        for value, point in zip(logs, self.reps):
            require(type(value) is int and 0 <= value < self.params.prime and
                    self.params.curve.mul(self.params.generator, value) == point,
                    'factor-base logarithm certificate failed')

    def solve(self, attempts, seconds, logs):
        results = {}
        for name, target in self.params.targets.items():
            saved = self.db.execute('SELECT scalar FROM solutions WHERE id=?', (name,)).fetchone()
            if saved is not None:
                value = integer(saved[0])
                with self.ledger.phase('solution_replay'):
                    self.certifySolution(value, target)
                results[name] = {'status': 'complete', 'scalar': str(value), 'verified': True, 'reused': True}
                continue
            if logs is None:
                matrix = self.collect(attempts, seconds, name)
                pinned = matrix.rows.get(len(self.reps))
                value = pinned[-1] if pinned is not None else None
            else:
                # Existing target relations can complete descent after a crash
                # between saving the relation and saving the scalar.
                value = None
                self.matrix(name)  # Verify every reused witness and coefficient.
                for coefficients, a, b in self.db.execute(
                        'SELECT coefficients,a,b FROM relations WHERE stream=? ORDER BY number', ('target:' + name,)):
                    row = json.loads(coefficients)
                    value = (sum(x * y for x, y in zip(row, logs)) - integer(a)) * pow(integer(b), -1, self.params.prime) % self.params.prime
                    break
                if value is None:
                    # One relation suffices once the base logs are known. Seed
                    # the reduced matrix with those already certified values.
                    matrix = self.matrix(name)
                    with self.ledger.phase('known_logs_matrix'):
                        for column, log in enumerate(logs):
                            row = [int(i == column) for i in range(len(self.reps))]
                            self.push(matrix, row, log, 0, True)
                    matrix = self.collect(attempts, seconds, name, matrix)
                    pinned = matrix.rows.get(len(self.reps))
                    value = pinned[-1] if pinned is not None else None
            if value is None:
                results[name] = {'status': 'insufficient_relations', 'verified': False}
            else:
                with self.ledger.phase('scalar_certification'):
                    self.certifySolution(value, target)
                    with self.db:
                        self.db.execute('INSERT INTO solutions VALUES (?,?)', (name, str(value)))
                results[name] = {'status': 'complete', 'scalar': str(value), 'verified': True, 'reused': False}
        return results

    def certifySolution(self, value, target):
        require(0 <= value < self.params.prime and self.params.curve.mul(self.params.generator, value) == target,
                'scalar certificate failed')

    def run(self, stage='all', attempts=32, pairBudget=10000, seconds=.25):
        require(stage in ('select', 'pairs', 'collect', 'logs', 'solve', 'all', 'status'), 'invalid stage')
        require(type(attempts) is int and 0 <= attempts <= 1000000, 'attempt budget must be between 0 and 1000000')
        require(math.isfinite(seconds) and 0 < seconds <= 3600, 'solver budget must be between 0 and 3600 seconds')
        require(type(pairBudget) is int and 0 <= pairBudget <= 10000000, 'pair budget must be between 0 and 10000000')
        report = {'schema_version': 1, 'operation': 'fixed', 'stage': stage,
                  'status': 'stopped', 'identity': self.params.identity, 'degree': self.params.onb.m,
                  'subgroup_order': str(self.params.prime), 'orbit_columns': len(self.reps),
                  'signed_base_points': len(self.points), 'solver': self.solver, 'targets': {}}
        count = math.comb(len(self.points) + self.params.summands - 1, self.params.summands)
        denominator = self.params.prime - 1
        report['coverage_ceiling'] = {'numerator': str(min(count, denominator)), 'denominator': str(denominator),
            'fraction': min(1.0, count / denominator), 'kind': 'counting_bound_on_uniform_nonzero_targets'}
        ready = True
        savedTargets = bool(self.params.targets) and all(self.db.execute(
            'SELECT 1 FROM solutions WHERE id=?', (name,)).fetchone() is not None for name in self.params.targets)
        replayOnly = stage in ('solve', 'all') and savedTargets
        if self.solver in ('pairs', 'learned') and not replayOnly and stage not in ('select', 'status', 'logs'):
            ready = self.buildPairs(pairBudget)
            if not ready:
                report['status'] = 'pair_budget'
        if ready:
            matrix = None
            if not replayOnly and stage in ('all', 'collect') and self.logs() is None:
                matrix = self.collect(attempts, seconds)
            logs = self.logs(matrix) if stage in ('all', 'collect', 'logs', 'solve') else None
            if stage in ('collect', 'logs'):
                report['status'] = 'complete' if logs is not None else 'insufficient_relations'
            if stage in ('all', 'solve'):
                report['targets'] = self.solve(attempts, seconds, logs)
                complete = bool(report['targets']) and all(t['verified'] for t in report['targets'].values())
                report['status'] = 'complete' if complete or (not report['targets'] and logs is not None) else 'insufficient_relations'
            if stage == 'pairs':
                report['status'] = 'complete'
        report['selector_model_sha256'] = None if self.selector is None else self.selector.hash
        report['pair_table'] = self.meta('pair_state')
        report['logs_available'] = self.meta('logs') is not None
        report['relations_saved'] = self.db.execute('SELECT COUNT(*) FROM relations').fetchone()[0]
        report['attempts_saved'] = self.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        report['reuse'] = dict(self.uses)
        report['accounting'] = self.ledger.report()
        report['accounting']['scope'] = 'through result assembly, including artifact reads, work commits and certificate checks; excludes final report archival/output and connection close; external benchmark wall time includes these'
        report['cumulative_measured_ns'] = report['accounting']['elapsed_ns'] + sum(
            json.loads(row[0])['accounting']['elapsed_ns'] for row in self.db.execute('SELECT report FROM invocations'))
        report['source_sha256'] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                  for name in ('indexcalc_fixed.py', 'indexcalc_selector.py', 'indexcalc_e2e.py', 'field.py', 'curves.py', 'decomp.py', 'cnf.py')}
        report['previous_invocations'] = self.db.execute('SELECT COUNT(*) FROM invocations').fetchone()[0]
        with self.db:
            self.db.execute('INSERT INTO invocations(report) VALUES (?)', (canonical(report),))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--params', required=True)
    parser.add_argument('--dir', required=True)
    parser.add_argument('--stage', choices=['select', 'pairs', 'collect', 'logs', 'solve', 'all', 'status'], default='all')
    parser.add_argument('--solver', choices=['pairs', 'sat', 'learned'], default='pairs')
    parser.add_argument('--selector-model', help='JSON model trained on matched natural-query panels')
    parser.add_argument('--attempts', type=int, default=32)
    parser.add_argument('--pair-budget', type=int, default=10000)
    parser.add_argument('--query-seconds', type=float, default=.25)
    args = parser.parse_args()
    try:
        with Campaign(readJson(args.params), args.dir, args.solver, selectorModel=args.selector_model) as campaign:
            report = campaign.run(args.stage, args.attempts, args.pair_budget, args.query_seconds)
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as error:
        report = {'schema_version': 1, 'operation': 'fixed', 'status': 'error', 'message': str(error)}
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] in ('complete', 'stopped') else 2


if __name__ == '__main__':
    sys.exit(main())
