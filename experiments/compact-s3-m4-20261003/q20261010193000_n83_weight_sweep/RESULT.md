# Ordinary N83 S3 leaf-weight sweep reaches no model under frozen caps

Q20261010193000 rebuilt Q1408's ordinary weight-five XCNF **byte for
byte**, then varied only the normal-x Hamming bound on each of four leaves.
It retained the same `EC1N83Ckb1h876c2921cb64` curve, ordinary public
point, complete four-element raw-preimage coset, balanced S3 tree,
CryptoMiniSat binary, and one-thread seed-zero settings. The exact Q1325
weight-five base has **B=30,977,592** usable points and **K=186,612**
folded columns, digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The workload is `Wbab50a1e5f66` and `isogeny: "none"` (`ISO0`).

| Leaf weight bound | Variables | CNF clauses | XOR rows | End condition | Child CPU | Wall | Peak child RSS | Status |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| ≤5 | 65,221 | 189,928 | 1,245 | 180 s wall cap | 8.87 s | 180.07 s | 70.9 MB | `BOUNDED_UNKNOWN` |
| ≤6 | 65,549 | 190,580 | 1,245 | 180 s wall cap | 11.28 s | 180.10 s | 139.1 MB | `BOUNDED_UNKNOWN` |
| ≤7 | 65,877 | 191,232 | 1,245 | 180 s wall cap | 32.67 s | 180.05 s | 264.4 MB | `BOUNDED_UNKNOWN` |
| ≤8 | 66,205 | 191,884 | 1,245 | 100,002 conflicts | 30.13 s | 82.58 s | 287.0 MB | `BOUNDED_UNKNOWN` |

The formula and solver archive audit passed all four rows. A separate
stream audit found active restart/conflict search in each process. No cell
returned a four-point model within its own limit. Weights five through
seven were killed before final solver statistics, so their exact final
conflict counts are unavailable; they are **not** matched 100,000-conflict
measurements. The sharp differences between child CPU and wall time show
why the shared-host wall numbers cannot rank solver settings or provide a
cost per relation. The weight-eight cell alone reached its conflict cap.

For weights six through eight, the projected factor bases have not been
enumerated. Their actual `B`, folded `K`, and set digests remain null;
these are Q-stage formula/solver probes, not `IC1` candidates or an
`fb<B>` comparison. Existing Q1419/Q1408 known-solution controls validate
the balanced S3 encoding at weight five; increasing an at-most leaf bound
preserves those witness assignments. The ordinary cells here provide
censored search evidence and no natural relation-yield or rank estimate.

The weight-eight result rules out a quick model at 100,000 conflicts on
this public point, but does not rule out the larger base or establish a
growth law. A half-rational/no-collision planning count would put an N83
weight-nine base near `K≈2^31.06`, with a `4K²` sparse-matrix touch model
near `2^64.13`; that is a reason to charge matrix work before further
loosening, not a measured base count. The next algorithmic gate remains an
implicit solver that propagates exact S3 pair roots as soon as a partial
assignment fixes a pair, then returns an ordinary N83 relation on the
**exact** Q1325 base with independently checked rank novelty. The
complete degree-131 `2^x` projection remains unresolved.
