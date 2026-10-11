"""Bind the selected exact verifier and an explicit same-point rho policy."""
import sys

from sparse_ic import HERE, ROOT, Point, sha256_hex, rho_policy

_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round21'))
    import first_identity as reference
    from first_identity import no_floats, validate_run
finally:
    sys.path[:] = _path


def source_snapshot():
    snapshot = reference.source_snapshot()
    paths = list(HERE.glob('*.py'))
    paths += [p for ext in ('*.py', '*.hpp') for p in (HERE.parent/'round23').glob(ext)]
    snapshot.update({str(p.relative_to(ROOT)): p.read_text() for p in paths})
    return snapshot


def candidate(q, snapshot):
    _, record = reference.candidate(q, snapshot)
    sparse = q.verifier_arm == 'sparse'
    record['point_decomposition']['certificate'] = (
        'independent packed bit-sliced zeta with compact roots and bounded exact sparse staircase proof'
        if sparse else 'independent packed bit-sliced zeta with frozen dense exact proof')
    record['point_decomposition']['certificate_policy'] = {
        'collection_and_target': True, 'mode': 2 if sparse else 'frozen',
        'independent_input_roots': True, 'exact_ideal_equality': True,
        'root_and_standard_list_bound': 256 if sparse else None,
        'divisibility_budget': (8 if q.budget_test else 65536) if sparse else None,
        'fallback': 'original exact dense proof; all attempted work charged' if sparse else 'none',
        'test_only_budget_build': q.budget_test}
    record['implementation'].update(arm=q.verifier_arm, verifier_arm=q.verifier_arm,
        native_build_policy='round20 dependency receipt plus independently built round23 sparse proof',
        entry_point='round25.sparse_ic.PreparedIC; unchanged collection, first-usable target recovery and rho')
    no_floats(record)
    return (f'IC1N{q.curve.n}C{q.curve.tag}fb{q.fb.usable_points}PDP3evalRCsampleLAgaussTDpdpISO0h{sha256_hex(record)[:12]}', record)


def fixture(q, seed):
    previous_id, workload, scalar = reference.fixture(q, seed)
    workload.update(schema='round25-single-public-target/1', prior_workload_id=previous_id,
                    rho_reference=rho_policy(q.curve, Point(**workload['target'])))
    no_floats(workload)
    return sha256_hex(workload)[:12], workload, scalar


def receipt(q, *args):
    row = reference.receipt(q, *args)
    row['profile_id'] += '-verifier-'+q.verifier_arm
    row['resource_envelope']['rho_workers'] = 1
    row['resource_envelope']['rho_distinguished_point_memory_bytes'] = 0
    row['provenance']['resource_envelope_id'] = 'ENV1h'+sha256_hex(row['resource_envelope'])[:12]
    return validate_run(row)
