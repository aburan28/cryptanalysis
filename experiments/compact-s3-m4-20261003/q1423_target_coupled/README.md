# Q1423: target-coupled exact S3 roots in four-summand search

Q1423 extends Q1422's exact rational-leaf gate and Q1420's pair-root
propagator. The first two external S3 links compute the possible x-coordinates
of each leaf-pair sum. Q1420 leaves the last link
`S3(first_pair_x, second_pair_x, selected_target_x)=0` as Boolean CNF.
Q1423 also solves that last equation exactly whenever the first pair
intermediate and the target-preimage selector are assigned. It adds guarded
clauses forcing the second pair intermediate to one of its at most two roots.
The original Boolean last link remains in the CNF.

The guards contain the full first-intermediate and selector assignments.
For nonzero first intermediate, the root routine solves the exact S3
quadratic in the native binary field and checks each root by substitution.
When the first intermediate is zero, `S3(0,t,z)=t²z²+1`, so the sole root is
`z=t⁻¹` for the archived nonzero targets. Thus each added clause is a logical
consequence of the existing last link and cannot remove a valid solution.
The target list is reconstructed in exactly the order used by Q1420 and its
serialized hash is frozen for each workload. Q1422 already validated the
leaf-lift gate against checked Sage at both degrees.

The [frozen protocol](protocol.json) compares the new decision order and
target-coupled propagation against Q1422 on exactly the same Q1420 CNFs,
public targets, factor bases, and 60-second / one-million-conflict caps. The
four cells are a known-witness `free_mids` control and one ordinary unpinned
query at each degree. Q1301 N53 W≤3 has actual `B=24,062`, folded `K=227`,
and curve `EC1N53Ckb1hf77aab617904`; Q1325 N83 W≤5 has actual
`B=30,977,592`, folded `K=186,612`, and curve
`EC1N83Ckb1h876c2921cb64`. Base digests and stage `PS1...PDP4theory...`
IDs are in the protocol. `candidate_id` is null because this remains a
point-decomposition proposal, and `isogeny` is `none`.

The control cell tests correctness, not natural relation yield. An ordinary
query is a solver gate, not a rate estimate. All failed and capped attempts
remain in the archive with native field calls, SAT counters, memory, and raw
output. CPU wall times from this host are exploratory. The complete degree-131
`2^x` stays unknown until ordinary yield, useful-rank growth, final sparse
matrix work, descent, and replay are measured and charged.

## Reproduction

Use the checked repository Sage launcher for every Sage job:

```sh
python3 experiments/compact-s3-m4-20261003/q1423_target_coupled/build_binaries.py --rebuild
python3 experiments/compact-s3-m4-20261003/q1423_target_coupled/build_binaries.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1423_target_coupled/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1423_target_coupled/run_stage.py --degree 53 --cell free_mids
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1423_target_coupled/run_stage.py --degree 53 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1423_target_coupled/run_stage.py --degree 83 --cell free_mids
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1423_target_coupled/run_stage.py --degree 83 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1423_target_coupled/verify_archive.py --require-complete --emit
```

The runner refuses to overwrite existing rows. The frozen protocol was
committed and published as draft PR #245 before any ordinary cell ran.

## Frozen outcomes

The [four-cell archive verifier](verification.json) passed. Both `free_mids`
known-witness controls returned exact-base relations. Both ordinary queries
reached the synchronous 60-second wall cap without a model; the external
75-second safeguard did not fire. No ordinary relation was recovered.

| Degree | Ordinary status | Distinct leaf-pair assignments | Final-root calls | Conflicts | Field mul/sqr/inv | Peak RSS |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| 53 | capped, no relation | 62,269 | 1 | 127 | 2,004,733 / 11,505,062 / 149,409 | 665 MB |
| 83 | capped, no relation | 66,824 | 1 | 143 | 3,273,124 / 27,920,948 / 267,157 | 1,284 MB |

The matched Q1422 leaf-first ordinary cells reached 49 N53 pair roots and
2,645 N83 pair roots under the same caps. Q1423's pair count combines both
leaf-pair links; it does not establish which pair dominates. The
target-coupled final-root rule activates only once per ordinary query.
These counts do not demonstrate a speedup: solver policies differ, both runs
are censored, and the host is not isolated for CPU timing claims. The exact
final-root clauses are sound and exercised by the controls; their placement
in this search order is ineffective.

The next gate is a **target-dependent condition that fires before many full
leaf-pair assignments are enumerated**, or a different search that indexes
both pair outputs. It must preserve the archived controls and recover verified
ordinary N53 and N83 relations on frozen exact bases. Until then, no solve
growth fit, natural useful-row rate, or complete N131 `2^x` is justified.
