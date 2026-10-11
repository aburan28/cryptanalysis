"""Bind independent arithmetic and match each IC arm to its own rho checker."""
import sys

from replay_query import HERE, ROOT, Point, ARMS, sha256_hex, arithmetic_policy, rho_policy

_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round25'))
    import ic_identity as reference
    from ic_identity import no_floats, validate_run
finally:
    sys.path[:] = _path


def source_snapshot():
    snapshot = reference.source_snapshot()
    snapshot.update({str(p.relative_to(ROOT)): p.read_text() for p in HERE.glob('*.py')})
    return snapshot


def candidate(q, snapshot):
    _, record = reference.candidate(q, snapshot)
    policy = arithmetic_policy(q.replay_arm)
    record['target_descent']['independent_arithmetic'] = policy
    record['implementation'].update(arm=q.replay_arm, replay_arm=q.replay_arm,
        independent_arithmetic=policy,
        entry_point='round26.replay_query.PreparedIC; per-instance independent field inversion for IC and rho')
    no_floats(record)
    return (f'IC1N{q.curve.n}C{q.curve.tag}fb{q.fb.usable_points}PDP3evalRCsampleLAgaussTDpdpISO0h{sha256_hex(record)[:12]}', record)


def fixture(q, seed):
    prior_id, workload, scalar = reference.fixture(q, seed)
    workload.update(schema='round26-single-public-target/1', prior_workload_id=prior_id,
        basis_checker=q.verifier_arm,
        rho_reference={'pairing': 'same independent arithmetic as the selected IC candidate',
                       'policies': {arm: rho_policy(q.curve, Point(**workload['target']), arm) for arm in ARMS}})
    no_floats(workload)
    return sha256_hex(workload)[:12], workload, scalar


def receipt(q, cid, manifest, wid, workload, result, rho, run_number, elapsed_ns):
    policy = arithmetic_policy(q.replay_arm)
    if rho['reference_policy'] != workload['rho_reference']['policies'][q.replay_arm]:
        raise ValueError('IC and rho must use the same independent checker')
    row = reference.receipt(q, cid, manifest, wid, workload, result, rho, run_number, elapsed_ns)
    row['profile_id'] += '-replay-'+q.replay_arm
    row['resource_envelope']['independent_arithmetic'] = policy
    row['provenance']['resource_envelope_id'] = 'ENV1h'+sha256_hex(row['resource_envelope'])[:12]
    return validate_run(row)
