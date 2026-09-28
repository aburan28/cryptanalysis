"""Bind the target root policy without changing the frozen public workloads."""
import sys
from first_query import HERE, ROOT, sha256_hex

_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round20'))
    import identity as reference
    from identity import fixture, no_floats
    from receipts import receipt as reference_receipt, validate_run
finally:
    sys.path[:] = _path


def source_snapshot():
    snapshot = reference.source_snapshot()
    snapshot.update({str(p.relative_to(ROOT)):p.read_text() for p in HERE.glob('*.py')})
    return snapshot


def candidate(q, snapshot):
    _, record = reference.candidate(q, snapshot)
    record['point_decomposition']['curve_replay'] = (
        'independent native signed full-point replay; all collection roots, declared target root policy')
    record['target_descent']['root_policy'] = q.target_policy
    record['target_descent']['root_policy_definition'] = (
        'ascending certified assignments until first usable relation; continue rejected lifts/membership; full basis certificate retained'
        if q.target_policy == 'first-usable' else 'all certified assignments, first lexicographically sorted projected row')
    record['implementation'].update(arm=q.target_policy, verifier_arm='packed',
        entry_point='round21.first_query.PreparedIC wrapping unchanged round20 collection and recovery')
    no_floats(record)
    return (f'IC1N{q.curve.n}C{q.curve.tag}fb{q.fb.usable_points}PDP3evalRCsampleLAgaussTDpdpISO0h{sha256_hex(record)[:12]}', record)


def receipt(q, *args):
    row = reference_receipt(q, *args)
    row['profile_id'] += '-'+q.target_policy
    return validate_run(row)
