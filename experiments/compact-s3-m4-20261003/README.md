# Compact four-summand S3-chain probe

This experiment tests one point-decomposition stage of ECC2K-130 index
calculus. It uses three compact S3 links and two free intermediate x
coordinates, so it does not expand S5. The experiment is **not** a complete
ECDLP solver. The frozen ordinary n=53 and n=83 SAT queries both exhausted a
20-second target-PDP cap without a model. Consequently there is no measured
degree-131 complete-solve work exponent, and no sub-\(2^{61}\) claim.

## Identity and comparable inputs

[`protocol.json`](protocol.json) freezes each curve, subgroup, weight-base
policy, one-target ordinary workload, and SAT cap. The exact enumerated bases
are in `bases/`. Their compact archives contain every canonical signed-
Frobenius x-orbit key and its length, allowing reconstruction of the actual
point set and its pre-fold size. [`verify_weight_base.py`](verify_weight_base.py)
checks the archive structure, orbit arithmetic, counts, and sampled subgroup
membership. The n=53 pair-table comparator also recomputes the orbit-key
digest independently from the prior full-base enumerator.

| Proposal | Exact curve ID | Weight bound | Actual usable points \(B\) | Folded columns | Base-key SHA-256 prefix |
| --- | --- | ---: | ---: | ---: | --- |
| Q1301 | `EC1N53Ckb1hf77aab617904` | 3 | 24,062 | 227 | `05b75578ee58` |
| Q1302 | `EC1N83Ckb1h876c2921cb64` | 4 | 1,934,066 | 11,651 | `800a59307125` |
| Q1303 | `EC1N131Ckb1h6816f880945e` | proposed 6 | unknown | unknown | unknown |

The exact n=53 curve cofactor is **428**; the n=83 cofactor is **4**.
These values are read from the curve manifests when constructing raw target
preimages and subgroup points. All three designs use `isogeny: "none"`. They
remain `Q` proposals with `candidate_id: null` because relation collection,
final relation-matrix LA, target descent, and complete recovery are not wired
or measured. A base size or nominal weight bound is not an `IC1` candidate ID.

## Compact SAT stage

[`chain_s3.py`](chain_s3.py) emits a native-XOR XCNF for three S3 links:
\((uv+uw+vw)^2+uvw+1=0\). Leaf x coordinates have normal-basis Hamming
weight at most the frozen bound; two intermediate x coordinates are free.
The runner tries curve lifts and sign choices, and checks the raw four-point
sum and cofactor-projected public target before accepting a relation.

The n=5 planted control solves and its four lifted points sum to its target.
At n=53 and n=83, the runner independently checks that each planted witness
satisfies the S3 equations, then both planted and ordinary formulas time out.
Thus the full-size planted tests check formula construction but do not show
that CryptoMiniSat can recover a witness at those sizes. All ordinary results
are single-target stage diagnostics, not online DLP timings.

| Curve | Workload ID for ordinary query | Planted status | Ordinary status | Ordinary formula (vars / CNF / XOR) | Charged target-PDP wall |
| --- | --- | --- | --- | --- | ---: |
| n=53 | `74f2979b3e68` | censored at 20 s | censored at 20 s | 26,860 / 77,292 / 795 | 20.071 s |
| n=83 | `bab50a1e5f66` | censored at 20 s | censored at 20 s | 64,808 / 188,944 / 1,245 | 20.168 s |

The four frozen receipts, gzip-archived XCNFs, and solver logs are in `runs/`
with names `n{53,83}_{planted,ordinary}_frozen.*`. The archive verifier
decompresses each formula and checks its exact SHA-256 and byte count against
the receipt. A timeout is neither UNSAT nor an
observed zero natural-relation rate. The solver produced no model and no
field-operation count before the cap. Failed attempts are charged to the
target-PDP stage. The checked Sage runtime snapshot used for measured local
jobs is [`sage_runtime_info.json`](sage_runtime_info.json).

## Matched pair-table stage

[`matched_n53_pair_table.py`](matched_n53_pair_table.py) reuses the prior
signed-Frobenius pair search on **the exact same n=53 base and public target**.
It recomputes the full base's canonical x-orbit digest and confirms the
24,062-point, 227-column set matches the compressed archive. It found one
verified four-point relation after 500,000 table samples and 171,218 query
samples: \(671{,}218=2^{19.356}\) logical pair samples. In the source-bound
run, its base enumeration took 32.78 s; table construction took 41.69 s;
target-query sampling took 22.34 s. The relation is checked to sum to the
public target. It does not
recover the target scalar, determine base logs, or measure matrix rank.

[`matched_n83_pair_sample.py`](matched_n83_pair_sample.py) samples the exact
n=83 base and ordinary public target with a lazy, cached reconstruction of
orbit points. In the source-bound run, its 20,000 table samples took 6.48 s
and 20,000 query samples took 5.83 s. It saw no quotient-key hit, as expected at this small sample
size. These times include lazy representative lifting in the table phase.
They are a throughput diagnostic, not a complete pair-table search or a
relation-yield estimate.

## Work accounting and decision

[`work_ledger.json`](work_ledger.json) separates the measured pair counts
from the unknown complete cost. Under a simple independent, uniform
pair-sum-orbit model, a balanced random quotient pair table at n=131 would
need roughly \(2^{61.48}\) *logical pair samples* for one expected match.
This is a heuristic for the sampled pair-table method, not a measured lower
bound, a field-operation conversion, or a projection for the SAT solver.
It already excludes base construction, final LA, and target recovery.

The complete n=131 work exponent remains **unknown**. The SAT stage is
censored at both measured field degrees; natural relation yield, novel rank,
cost per useful row, final matrix solving, target descent, and independent
scalar replay are absent. There is therefore no defensible complete-solve
upper projection below \(2^{61}\), and the degree-131 challenge gate remains
closed. Existing complete ECDLP claims cannot be inferred from a relation
stage or a planted witness.

The next useful goal is a **noncensored, operation-metered ordinary S3
decomposition**, first at n=53 and then at n=83, on these frozen bases and
targets. Keep all failed attempts; collect enough independent ordinary
queries to estimate useful relation and novel-rank rates with uncertainty.
Only then fit an n=131 stage cost and add matrix, descent, and replay charges.
If the fitted complete cost is credibly below \(2^{61}\) in a named operation
unit, the challenge run is justified; otherwise the experiment is a no-go
for this solver family.

## Reproduction

From this repository worktree, first save checked runtime information:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/sage_runtime_info.json
python3 -m unittest discover -s experiments/compact-s3-m4-20261003 -p test_chain_s3.py -v
python3 experiments/compact-s3-m4-20261003/freeze_protocol.py --check
python3 experiments/compact-s3-m4-20261003/verify_frozen_artifacts.py
python3 -c 'import sys; sys.path.insert(0, "experiments/compact-s3-m4-20261003"); from verify_weight_base import verify; assert verify("experiments/compact-s3-m4-20261003/bases/n53_weight3_orbits.json.gz")["pass"]'
python3 -c 'import sys; sys.path.insert(0, "experiments/compact-s3-m4-20261003"); from verify_weight_base import verify; assert verify("experiments/compact-s3-m4-20261003/bases/n83_weight4_orbits.json.gz")["pass"]'
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```

All new or resumed local Sage jobs use the repository's checked launcher.
For the frozen SAT runs, see the exact seeds, bounds, and source hashes in
`protocol.json` and the `runs/*_frozen.json` receipts. The recorded wall
interval begins at formula construction and includes every target-dependent
attempt; fixture construction and launcher startup are excluded.
