# ECC2K-130 implicit orbit-closed W24 seed gate

The seed-plus-Frobenius representation passed its frozen correctness gate.
The pure-Python producer built all 131 conjugate W24 spans without
materializing the orbit-closed point set, returned exact `(exponent,mask)`
witnesses for all 56 planted field inputs, and returned no witness for the
64 fixed negative field inputs. A separately implemented, checked-Sage
verifier agreed on **all 120 field decisions and their complete witness
lists**. It also reconstructed eight actual source-curve points from W24
seeds, applied the cofactor-four map, and matched their archived subgroup
images after Frobenius. The verified status is
`PASS_INDEPENDENT_SAGE_FIELD_AND_GROUP_REPLAY` in
[`runs/R1/verification.json`](runs/R1/verification.json).

This is a **representation and correctness stage**, not a PDP result. The
56 positives were constructed from known seed masks; the fixed negatives
are field words, not ordinary group-sum targets. Their 0/64 membership
count says nothing about natural five-summand decomposition yield. No
relation, useful rank, matrix, target logarithm, rho comparison, or
ECC2K-130 speedup is claimed. `candidate_id` and the end-to-end costs
remain `null`.

| Exact gate quantity | R1 result |
| --- | ---: |
| Conjugate W24 subspaces built | 131, each rank 24 |
| Planted field controls / witnesses reconstructed | 56 / 56 |
| Witness multiplicities on those controls | 56 with exactly one |
| Fixed negative field inputs / returned witnesses | 64 / 0 |
| Source subgroup cofactor/Frobenius controls | 8 / 8 verified |
| Subspaces examined | 15,720 |
| Binary echelon XOR reductions | 127,792 |
| Producer wall, exploratory | 80.427 ms |
| Producer peak RSS | 24,346,624 B |
| Independent Sage wall, exploratory | 1,735.388 ms |
| Independent Sage peak RSS | 261,046,272 B |

The checked Sage launcher reported the accepted runtime in
[`runtime-info.json`](runs/R1/runtime-info.json), SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The producer's raw [`result.json`](runs/R1/result.json) has SHA-256
`1bfc3cecc51309926f4c801133b9b96ff1587d69d0a80c4460079fda52c83cdd`.
It binds the protocol config, source-control file, and producer code hashes;
the verifier binds those plus its own code and the runtime receipt. The
protocol commit `54587f106f06a4bde3e073cbf992b2b380b28b78` and
implementation commit `5c0914059dc5d7fb997adb0601f4c3f1fca24f10`
were pushed to [PR #363](https://github.com/aburan28/cryptanalysis/pull/363)
before R1. Both deliberate mutations—one field witness mask and one valid
but wrong group image—were rejected with nonzero Sage exits and no
verification output; see [`mutation-check.json`](runs/R1/mutation-check.json).
The [SHA-256 manifest](SHA256SUMS) covers all source, frozen parent inputs,
raw receipts, and the recorded failures.

The parent [exact orbit census](../ecc2k130-263-w24-orbit-columns-20261005/RESULT.md)
proves that closing the original source W24 set gives
2,198,485,492 subgroup points in 8,391,166 signed-Frobenius orbits. R1
does not re-enumerate that set. It proves that a field coordinate can be
recognized as a nonzero W24 seed in one or more Frobenius conjugates by
small, explicit binary subspace tables, and that the seed/exponent group
encoding works on the pinned projected controls. Recognizing an **arbitrary
subgroup point** as a member would additionally require accounting for
the four `[4]` preimages and their torsion translations; that operation is
not measured here. On the degree-263 descendant, coordinate squaring is
not a direct endomorphism, so transport and induced-action costs remain
separate. The host was not isolated; the wall numbers above are only
diagnostics for reproducing this gate.

There is a structural reason to keep the union implicit. The source-field
Frobenius has order 131 and fixes `F₂`. Since `ord₁₃₁(2)=130`, its
cyclotomic factor `Φ₁₃₁` is irreducible over `F₂`; the nontrivial invariant
summand has dimension 130. Thus its invariant linear-subspace dimensions
are only 0, 1, 130 and 131, never 24. A 24-dimensional linear W policy
cannot itself be Frobenius closed at this degree. The test suite checks
the exact modular-order certificate. The seed-plus-exponent union keeps
the small seed space while representing its nonlinear closure; it also
introduces exponent choices that a future PDP solver must pay for.

**Decision:** admit a bounded planted m5 summation-polynomial formulation
with W24 seed masks and Frobenius exponents as the next test. It must solve
for an unknown witness, not merely check supplied masks. Only after that
gate passes should a separately frozen ordinary-query panel estimate
verified relation yield and novel rank, paired against original W24/m6 and
W28/m5 on the same target law. This stage gives no reason to promote the
orbit-closed policy ahead of those alternatives yet.

Reproduce from this branch with fresh output paths:

```sh
python3 -m unittest discover -s experiments/ecc2k130-orbit-closed-w24-seed-20261006 -p test_orbit_seed.py
shasum -a 256 -c experiments/ecc2k130-orbit-closed-w24-seed-20261006/SHA256SUMS
python3 experiments/ecc2k130-orbit-closed-w24-seed-20261006/run.py --out /tmp/orbit-w24-result.json
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /tmp/orbit-w24-runtime.json
/Volumes/SSD990/cryptanalysis/sage -python "$PWD/experiments/ecc2k130-orbit-closed-w24-seed-20261006/verify_sage.py" --result /tmp/orbit-w24-result.json --runtime-info /tmp/orbit-w24-runtime.json --out /tmp/orbit-w24-verification.json
```

The last command uses the absolute path to this checkout's verifier; the
repository Sage launcher must remain the executable. Fresh
wall-time fields will vary. Run `mutation_check.py --run-dir <fresh-run-dir>`
only after placing the three expected filenames (`result.json`,
`runtime-info.json`, and a writable output directory) there.
