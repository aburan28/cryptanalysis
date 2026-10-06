# Q1460: fixed-state target-x support of the bounded joint join

Q1458's exact joint `S3` rule evaluates only partial four-leaf states whose
two sparse-pair completion products are each at most 4,096. Q1459's exact
leaf-lift filter admits one additional archived N83 state but did not run a
changed solver. Q1460 measures how many **distinct pair-intermediate x
coordinates** those admitted fixed states can represent. It is an analytic
screen and a native midpoint-set measurement, not a new point-decomposition
solve.

The [frozen protocol](protocol.json) retains the Q1459 N53 W≤4 and N83 W≤6
curve IDs, actual usable factor-base sizes and folded columns, enumerated-set
digests, frozen ordinary workloads, 4,096-pair cap, source and binary hashes,
and a checked Sage runtime receipt. This is proposal `Q1460`, with
`candidate_id: null`, `run_id: null`, `isogeny: "none"`, and stage code
`PDP4hybrid`. The protocol and implementation were committed before
`result.json` was emitted.

## Exact fixed-state bound

For one fixed partial state, let `P0` and `P1` be its two numbers of leaf-pair
completions and let `M0` and `M1` be the sets of distinct `S3` midpoint x
roots. Each completed pair has at most two roots, so `|Mi| ≤ 2Pi`. A raw
target x satisfying the final link for some `u ∈ M0`, `v ∈ M1` is a root
of

`(u+v)^2 t^2 + uv t + (uv)^2 + 1 = 0`.

This polynomial has at most two field roots for every `u,v`; when both are
zero it is the constant one. Hence one **fixed state** supports at most
`2|M0||M1| ≤ 8P0P1` raw target x values. The 4,096 cap gives the generic
ceiling `2^27`. These are bounds on x-only chains: curve point signs,
subgroup projection, distinct columns, and relation verification can only
remove candidates.

The [native result](result.json) enumerates both midpoint sets for every
Q1459 archived state admitted under the raw or lift-filtered cap. The
[independent Sage audit](verification.json) replays all pair roots on the
smallest N53 raw and N83 lift states, and checks every result row and its
formula against the frozen inputs.

| Archived input | Raw / lift-admitted states | Largest raw-state support bound | Largest lift-state support bound | Best stated lift-state fraction of all raw field x values |
| --- | ---: | ---: | ---: | ---: |
| N53 known-satisfiable selected preimage | 6 / 6 | 3,385,202 | 781,250 | at most `2^-33.424` per fixed state |
| N53 full ordinary public target | 6 / 6 | 3,385,202 | 781,250 | at most `2^-33.424` per fixed state |
| N83 full ordinary public target | 1 / 2 | 4,626,882 | 4,626,882 | at most `2^-60.858` per fixed state |

The N83 state newly admitted by Q1459 has 1,521 liftable pair inputs on each
side and exactly 1,521 distinct midpoint x values on each side. Its
fixed-state raw-target support is therefore at most 4,626,882 x values.
This is much smaller than `2^83`, but it is **not** a success probability for
the existing SAT solver: its partial states and target selector are affected
by the target-dependent CNF. It is also not a bound on an adaptive
target-guided algorithm, a public-subgroup target yield, or the chance that
the frozen target has a representation.

## Post-result N83 overlap audit

The primary result showed equal midpoint **counts** for the new N83
lift-admitted state 20 and the previously admitted raw state 22. A
separately [frozen post-result audit](overlap_protocol.json) compares the
actual sets with independent Sage roots. Its [result](overlap_result.json)
finds identical 1,521-element midpoint sets on **both** sides for state
20 lift, state 22 raw, and state 22 lift; each set has the same SHA-256
digest under the declared fixed-width ONB encoding. Consequently, the
new archived admission adds no x-only final-link target support beyond
the already admitted raw state. An earlier rejection on a changed solver
trail could still affect search work; this audit does not measure that.
The follow-up was selected after the primary Q1460 counts were visible,
and its source/protocol were committed before the exact-set comparison.

The screen supplies no new verified relation or successful-decomposition
cost. The complete N131 `2^x` remains unknown, and the challenge stays
closed. The result strengthens the case for a rule that reasons about large
partial domains with the target and both pairs still coupled; another
small-domain admission alone does not establish useful target coverage.

Reproduce using the accepted Sage launcher for the independent replay:

```sh
python3 experiments/compact-s3-m4-20261003/q1460_fixed_state_support/rebuild.py
python3 experiments/compact-s3-m4-20261003/q1460_fixed_state_support/freeze_protocol.py --check
python3 experiments/compact-s3-m4-20261003/q1460_fixed_state_support/screen.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1460_fixed_state_support/verify_archive.py --check
python3 experiments/compact-s3-m4-20261003/q1460_fixed_state_support/freeze_overlap_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1460_fixed_state_support/audit_overlap.py --check
```
