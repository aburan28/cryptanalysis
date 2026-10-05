# Q1438: exact denser N53/N83 projected bases

Q1438 changes only the normal-basis sparse-x weight limit on the archived
curves: N53 W≤3 becomes W≤4, and N83 W≤5 becomes W≤6. These are separate
factor-base designs, so their point-decomposition results must be compared
with the changed base stated explicitly. The exact curve IDs, field records,
subgroup orders, and cofactors come from the parent compact-S3 protocol.
N53 uses cofactor **428**; N83 uses cofactor **4**.

The [frozen protocol](protocol.json) fixes the code, Sage runtime, curve
records, and enumeration order before either base is measured. The enumerator
visits every nonzero sparse-x Frobenius orbit once, tests rationality,
projects to the named subgroup, discards identity, and hashes the sorted
canonical projected x keys. It checks the entire old N53 W≤3 point set for
equality and checks the entire old N83 W≤5 set by its exact digest. The
independent verifier replays sampled x classifications and subgroup
projections with Sage's group law. The full exact-base computation has one
enumeration pass per degree, not two independent full enumerations.

This is proposal `Q1438`, with `candidate_id: null` and `isogeny: "none"`.
Actual `fb<B>` counts and folded columns will be assigned from the new
complete enumeration receipts. No `IC1` identifier is assigned until the
complete point-decomposition, collection, matrix, and target policy is fixed.
Base construction is kept separate from the single-target online interval.

## Matched solver cells

The [solver protocol](solver_protocol.json) uses Q1436's identical native
compact-S3/affine-pair binary, decision policy, public target point, target
preimages, one-million-conflict cap, and 60-second internal wall cap at each
degree. The only mathematical change is the exact denser factor base and its
weight constraint. Its stage IDs use the actual new decimal `fb<B>` values;
`candidate_id` remains null. The [formula validation](formula_validation.json)
rebuilds all four old-weight control and ordinary CNFs and variable maps
byte for byte against Q1426 before the new-weight runs.

Run order is N53 known-witness control, N53 unpinned ordinary query, N83
known-witness control, and N83 unpinned ordinary query. Controls keep the
archived first leaf and pair intermediates pinned while freeing both partner
leaves. Ordinary queries have no witness pins. Preserve every capped or failed
attempt and independently replay any returned relation. Since the factor
base changes, these are paired method-design comparisons, not solver-only
CPU speed ratios. Host wall times remain exploratory without an isolation
receipt.

Use the checked Sage launcher for every job:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1438_dense_base/sage_runtime_info.json
python3 experiments/compact-s3-m4-20261003/q1438_dense_base/freeze_protocol.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/enumerate_base.py --degree 53
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/enumerate_base.py --degree 83
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/verify_base.py --emit
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/validate_formula.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/freeze_solver_protocol.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/run_solver.py --degree 53 --cell free_partner
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/run_solver.py --degree 53 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/run_solver.py --degree 83 --cell free_partner
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/run_solver.py --degree 83 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1438_dense_base/verify_solver.py --emit
```

The scripts refuse to overwrite evidence. Use a scratch checkout for replay.
