"""Bind each decomposition strategy and a target unseen by every preparation."""
from types import SimpleNamespace
import sys

from conditional_ic import HERE, ROOT, ARMS, SUMMANDS, Point, sha256_hex
from conditional_ic import arithmetic_policy, rho_policy

_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round26'))
    import replay_identity as reference
    from replay_identity import no_floats, validate_run
    from identity import fixture as original_fixture
finally:
    sys.path[:] = _path


def source_snapshot():
    snapshot = reference.source_snapshot()
    for folder in (HERE, HERE.parent/'round27'):
        snapshot.update({str(p.relative_to(ROOT)): p.read_text() for p in folder.iterdir()
                         if p.suffix in ('.py', '.cpp', '.hpp', '.h')})
    return snapshot


def candidate(q, snapshot):
    _, record = reference.candidate(q, snapshot)
    pdp = record['point_decomposition']
    conditional = q.ic_arm == 'two-conditional'
    solver = 'cond' if conditional else 'eval'
    stage = f'PDP{q.summands}{solver}'
    pdp.update(stage_code=stage, summands=q.summands, solver_family=solver,
        summation_polynomial=f'direct S{q.summands+1} for y^2+xy=x^3+1; native prefix-basis Weil descent')
    if conditional:
        pdp.update(algorithm='conditional linear columns and Buchberger-Moeller basis construction',
            internal_matrix_kernel='Gray-code equation-column elimination over GF(2)',
            certificate='independent equation-row branch counts and exact Boolean staircase',
            certificate_policy={'collection_and_target':True, 'independent_input_roots':True,
                'exact_ideal_equality':True, 'blocks':[q.ell,q.ell], 'root_and_standard_list_bound':256,
                'divisibility_budget':1000000, 'fallback':'none; unsupported or exhausted work is a failed attempt',
                'test_only_budget_build':False})
    record['implementation'].update(arm=q.ic_arm, decomposition_arm=q.ic_arm,
        replay_arm='euclid', verifier_arm='conditional' if conditional else q.verifier_arm,
        native_build_policy='round20 dependencies plus round23 sparse proof and round27 independent producer/checker',
        entry_point='round28.conditional_ic.PreparedIC; explicit two/three-summand collection and recovery')
    no_floats(record)
    cid = f'IC1N{q.curve.n}C{q.curve.tag}fb{q.fb.usable_points}{stage}RCsampleLAgaussTDpdpISO0h{sha256_hex(record)[:12]}'
    return cid, record


def fixture(prepared, seed):
    if set(prepared) != set(ARMS):
        raise ValueError('fixture requires every independently prepared arm')
    first = prepared[ARMS[0]]
    for q in prepared.values():
        if (q.curve.curve_id,q.fb.digest,q.ell,q.collection_seed,q.max_collection,q.max_target) != (
                first.curve.curve_id,first.fb.digest,first.ell,first.collection_seed,first.max_collection,first.max_target):
            raise ValueError('unpaired curve, base, collection stream or limits')
    seen = set().union(*(q.seen_points for q in prepared.values()))
    common = SimpleNamespace(curve=first.curve, fb=first.fb, ell=first.ell,
        seen_points=seen, collection_seed=first.collection_seed,
        max_collection=first.max_collection, max_target=first.max_target)
    prior, workload, scalar = original_fixture(common, seed)
    workload.update(schema='round28-conditional-single-public-target/1', prior_workload_id=prior,
        target_law='uniform nonzero subgroup point conditioned on exclusion of the union of all three preparation sets',
        excluded_points_by_arm={arm:sha256_hex(sorted((p.x,p.y,p.inf) for p in q.seen_points))
                                for arm,q in prepared.items()},
        decomposition_comparison={arm:SUMMANDS[arm] for arm in ARMS},
        rho_reference=rho_policy(first.curve,Point(**workload['target']),'euclid'))
    no_floats(workload)
    return sha256_hex(workload)[:12], workload, scalar


def receipt(q, cid, manifest, wid, workload, result, rho, run_number, elapsed_ns):
    if rho['reference_policy'] != workload['rho_reference']:
        raise ValueError('IC and rho must use the same independent checker')
    # The frozen receipt constructor reads numerical facts, not the old
    # three-summand candidate labels. Replace its descriptive profile below.
    row = reference.reference.receipt(q,cid,manifest,wid,workload,result,rho,run_number,elapsed_ns)
    row['profile_id'] = f'round28-n{q.curve.n}-m{q.summands}-ell{q.ell}-{q.ic_arm}'
    row['resource_envelope']['independent_arithmetic'] = arithmetic_policy('euclid')
    row['provenance']['resource_envelope_id'] = 'ENV1h'+sha256_hex(row['resource_envelope'])[:12]
    return validate_run(row)
