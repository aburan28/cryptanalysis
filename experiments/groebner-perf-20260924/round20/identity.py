"""Immutable candidate/workload identities for the complete toy IC experiment."""
import hashlib
from pathlib import Path
import random
import sys

from ic_query import HERE, ROOT, point, sha256_hex, endomorphism_record, kernel


def source_snapshot():
    paths = set()
    for r in (2, 4, 14, 15, 17, 18, 20):
        folder = HERE.parent/f'round{r}'
        paths.update(p for p in folder.rglob('*') if p.suffix in ('.py', '.cpp', '.c', '.h')
                     and 'build' not in p.parts and '__pycache__' not in p.parts)
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT) and path.suffix == '.py':
                paths.add(path)
    for name in ('pdpkernel.c', 'kernel.py', 'opcount.py', 'toycurve.py', 'factor_base.py',
                 'monitor.py', 'relations.py', 'profile.py', 'descent.py', 'macaulay.py'):
        paths.add(ROOT/'experiments/pdp-degree-heuristics'/name)
    for name in ('gf2n.py', 'descend.py', 'sumpoly.py', 'boolean_certificate.cpp', 'boolean_certificate_native.py', 'boolean_basis.py'):
        paths.add(ROOT/'experiments/pdp-scaling'/name)
    paths.add(ROOT/'experiments/ic-bench/bench.py')
    for name in ('measurement_contract.json', 'isogeny_routes.json'):
        paths.add(ROOT/'experiments/ic-candidate-catalog'/name)
    return {str(p.relative_to(ROOT)): p.read_text() for p in sorted(paths)}


def no_floats(value):
    if isinstance(value, float):
        raise ValueError('identity records cannot contain floats')
    if isinstance(value, dict):
        for v in value.values(): no_floats(v)
    elif isinstance(value, (list, tuple)):
        for v in value: no_floats(v)


def candidate(prepared, snapshot):
    q, fb, C = prepared, prepared.fb, prepared.curve
    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in snapshot.items()}
    record = {
        'schema': 'ic-candidate/1', 'field': C.field_record(),
        'curve': {**C.curve_record(), 'curve_id': C.curve_id},
        'isogeny': 'none', 'endomorphism': endomorphism_record(C),
        'factor_base': {**fb.record(), 'geometric_points_and_projection': q.base_points,
                        'column_representatives': [list(p) for p in fb.column_reps]},
        'point_decomposition': {
            'stage_code': 'PDP3eval', 'summands': 3, 'solver_family': 'eval',
            'algorithm': 'Boolean evaluation and Buchberger-Moeller basis construction',
            'summation_polynomial': 'direct S4 for y^2+xy=x^3+1; native prefix-basis Weil descent',
            'monomial_order': 'graded reverse lexicographic: higher degree, then smaller integer mask leads',
            'equation_order': 'polynomial-basis field bits 0 through n-1',
            'internal_matrix_kernel': 'native bit-packed GF(2) linear algebra',
            'certificate': 'ordered independent direct ANF' if q.arm == 'baseline' else 'independent packed bit-sliced zeta',
            'direct_equation_replay': 'Python original ANF' if q.arm == 'baseline' else 'independent native packed ANF',
            'curve_replay': 'independent native signed full-point replay, all certified roots examined',
            'limits': {'variables': 20, 'producer_roots': 256, 'equations': 128},
            'cache_policy': 'fixed ring layouts and buffers; fresh numerical data on every query; no answer reuse'},
        'relation_collection': {
            'stage_code': 'RCsample', 'query_law': 'uniform nonzero [k]G; stream fixed in workload',
            'rows': 'one first native signed witness per certified root; exact geometric-base membership; cofactor projection',
            'duplicates': 'unique projected rows per query, sorted deterministically',
            'dependencies': 'incremental Gaussian elimination modulo subgroup order',
            'stop': 'full column rank or max_collection attempts', 'max_collection': q.max_collection,
            'verification': 'independent original-equation and curve checks; independent projection and column-log replay'},
        'relation_linear_algebra': {
            'stage_code': 'LAgauss', 'solver': 'monitor.RankTracker', 'modulus': C.r,
            'rank_criterion': 'full effective column rank', 'free_columns': 'reject incomplete preparation',
            'block_parameters': 'none', 'preconditioner': 'none'},
        'target_descent': {
            'stage_code': 'TDpdp', 'policy': 'Q+[a]G for uniform nonzero a until a usable relation or attempt limit',
            'identity_relation': 'Q+[a]G=O gives -a modulo r, independently replayed',
            'recursive_solvers': 'none', 'max_attempts': q.max_target,
            'success': 'independent Python [scalar]G equals the complete public point',
            'single_target': True, 'target_answer_cache': 'none',
            'unseen_rule': 'reject preparation query points and their negatives, generator and known projected base columns'},
        'implementation': {'sources_sha256': hashes, 'arm': q.arm,
                           'native_build_policy': 'pinned round4/14/15/17/18 build scripts; optimized CPU producer/descent',
                           'kernel_cflags': kernel.CFLAGS,
                           'checker_and_replay_sanitizer': q.sanitizer,
                           'binary_and_compiler_receipts': 'retained in each measured report',
                           'entry_point': 'round20.ic_query.PreparedIC; actual solver family is evaluation, not F4/F5'}
    }
    no_floats(record)
    cid = f'IC1N{C.n}C{C.tag}fb{fb.usable_points}PDP3evalRCsampleLAgaussTDpdpISO0h{sha256_hex(record)[:12]}'
    return cid, record


def fixture(prepared, seed):
    """External fixture construction; the returned secret never enters recovery."""
    rng = random.Random(f'round20-public-fixture|{prepared.curve.curve_id}|{seed}')
    for draws in range(1, 100001):
        scalar, Q = prepared.curve.random_subgroup_point(rng)
        if point(Q) not in prepared.seen_points:
            break
    else:
        raise RuntimeError('no unseen fixture within declared draw cap')
    excluded = sorted((p.x, p.y, p.inf) for p in prepared.seen_points)
    record = {
        'schema': 'round20-single-public-target/1', 'curve_id': prepared.curve.curve_id,
        'factor_base_policy': {'family': 'prefix', 'ell': prepared.ell,
                               'record_sha256': prepared.fb.digest},
        'target': vars(point(Q)), 'target_count': 1, 'seed': seed,
        'target_law': 'uniform nonzero subgroup point conditioned on exclusion of already-seen preparation points',
        'fixture_draws': draws, 'excluded_points_sha256': sha256_hex(excluded),
        'collection_seed': prepared.collection_seed,
        'rerandomization_seed': f'round20-rerandomization|{prepared.curve.curve_id}|{seed}',
        'cache_state': 'fresh single-target context after reusable preparation',
        'resource_limits': {'max_collection': prepared.max_collection, 'max_target': prepared.max_target,
                            'processes': 1, 'hard_per_query_timeout': False},
        'rho_reference': {'algorithm': 'ic-bench measured three-set Floyd rho', 'max_restarts': 32,
                          'steps_per_restart': '20*floor(sqrt(r))+100',
                          'seed': f'{prepared.curve.curve_id}|{Q[0]}|{Q[1]}',
                          'independent_validation_and_scalar_replay': 'charged Python polynomial-field arithmetic'}
    }
    no_floats(record)
    return sha256_hex(record)[:12], record, scalar
