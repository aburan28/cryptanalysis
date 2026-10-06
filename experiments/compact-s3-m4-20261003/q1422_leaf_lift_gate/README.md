# Q1422: exact rational-leaf gate in compact four-summand search

Q1422 adds one sound algebraic clause family to Q1421's leaf-first exact-root
solver. For every nonzero raw leaf x on `y² + x*y = x³ + 1`, write `y=x*z`.
Then `z²+z=x+x⁻²`, which has a binary-field solution exactly when its trace
is zero. Since trace is unchanged by squaring, this is equivalent to
`Tr(x+x⁻¹)=0`. In the exact normal-basis encoding, field trace is coordinate
parity. A fully assigned leaf failing this test is forbidden by a guarded
clause. At maximum permitted Hamming weight, its positive support alone
determines x under the existing at-most-weight CNF; otherwise the guard is
the full bit assignment. Thus the added clause excludes only an x that has
no curve point and cannot remove a valid decomposition.

The checked-Sage/native [N53](n53_lift_validation.json) and
[N83](n83_lift_validation.json) receipts match on 64 deterministic sparse
values, 64 full-range values, and all archived witness leaves per degree.
Each successful sampled predicate is replayed as an actual curve point;
trace obstruction certifies the failures. The prior Q1420 native field
validation covers the ONB/polynomial bridge used by this gate.

The [frozen protocol](protocol.json) compares Q1422 with the already frozen
Q1421 `leaf_first` cells on identical Q1420 CNFs, caps, targets, curves,
and exact bases. It runs a known-witness `free_mids` control and an unpinned
ordinary query at each of N53 and N83. Q1301 N53 W≤3 uses actual
`B=24,062`, folded `K=227`, curve `EC1N53Ckb1hf77aab617904`; Q1325 N83
W≤5 uses `B=30,977,592`, `K=186,612`, curve
`EC1N83Ckb1h876c2921cb64`. The exact base digests and matched baseline
receipt hashes are in the protocol. Each new configuration has a distinct
`PS1...PDP4theory...` ID. `candidate_id` stays null and `isogeny` is
`none`.

The gate proves raw x rationality, which is necessary but does not by
itself prove that cofactor projection is nonidentity or that the projected
point is in the enumerated factor base. Successful SAT models must still
pass the exact-base group-law verifier. One ordinary query per degree is a
method gate, not a natural relation-yield estimate. Failed queries, timeouts,
field operations, memory, and raw solver output are retained. Wall times on
this unisolated host are exploratory. A complete degree-131 `2^x` remains
unknown until useful-row yield, matrix, descent, and replay are charged.

## Reproduction

Run all Sage scripts through the checked repository launcher. The build and
validation receipts pin native code, the accepted runtime, and exact inputs:

```sh
python3 experiments/compact-s3-m4-20261003/q1422_leaf_lift_gate/build_binaries.py --rebuild
python3 experiments/compact-s3-m4-20261003/q1422_leaf_lift_gate/build_binaries.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1422_leaf_lift_gate/validate_lift_gate.py --degree 53 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1422_leaf_lift_gate/validate_lift_gate.py --degree 83 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1422_leaf_lift_gate/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1422_leaf_lift_gate/verify_archive.py --require-complete --emit
```

The frozen cells run through `run_stage.py --degree N --cell CELL` in the
protocol's order. The runner refuses to overwrite a result.

## Frozen outcomes

The [four-cell archive verifier](verification.json) passed. Both `free_mids`
known-witness controls return exact-base relations. Both unpinned ordinary
queries stop at the synchronous 60-second wall cap with no model. Every
solver process returned its counters; the external safeguard never fired.

| Degree | Ordinary status | Completed leaf x values | Rejected nonrational x | Pair-root calls | Conflicts | Field mul/sqr/inv | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 53 | capped, no relation | 109 | 58 | 49 | 94,810 | 2,263 / 13,484 / 205 | 291 MB |
| 83 | capped, no relation | 5,269 | 2,622 | 2,645 | 22,248 | 129,384 / 1,103,548 / 10,557 | 516 MB |

The matched Q1421 leaf-first ordinary cells reached 62 pair roots and
111,577 conflicts at N53, and 5,167 pair roots and 21,900 conflicts at
N83. Q1422 removes many nonrational leaves and roughly halves N83 pair-root
calls, but it does not recover a relation. The N83 conflict count is
similar, and the native gate adds field inversions. Process wall times are
about 60 seconds by design and do not establish a CPU speedup on this
unisolated host. Counts cover solver field calls; target-dependent Q1420
formula construction remains a separate charged term.

The exact rationality test is sound and useful as a filter, but the next
solver must make stronger use of the public target before enumerating large
numbers of sparse leaf candidates. These censored runs cannot yield a
solve-growth fit, natural useful-row rate, or complete N131 `2^x`.
