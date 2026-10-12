# Q1421: exact normal-weight-four source-base census

The frozen ECC2K-130 normal-weight-four policy has **11,743,888 usable
subgroup points** before sign/Frobenius folding and **44,824 potential
signed-Frobenius relation columns**. A second implementation in checked Sage
replayed every orbit decision and digest, then verified 128 projected subgroup
points and 512 Frobenius images. The policy passes its preregistered size and
column gates, so the next experiment is an ordinary-query six-summand PDP
comparison at equal actual base size. This is proposal `Q1421`; its complete
IC candidate remains unresolved (`candidate_id: null`).

## Exact input and count

The field is `GF(2^131)` in polynomial basis with modulus
`t^131+t^13+t^2+t+1`; the source curve is
`EC1N131Ckb1h136f03e58c98`, `y^2+xy=x^3+1`, with subgroup order
`680564733841876926932320129493409985129` and cofactor four. The
[protocol](PROTOCOL.md) binds the 131 normal-basis words to parent result
SHA-256 `7b45cc0a5c6b1299bccf4b79c514fb26cffebdd51ab21be6ec2c8a8dfbf83b54`.
The producer enumerated every lexicographically least four-gap representative,
using exactly one of the 131 cyclic rotations of each weight-four normal word.
Rationality is `Tr(1/w)=0`; in-base reciprocal partners identify signed
classes. The previously established cofactor-four projection law gives two
subgroup points per signed class.

| Count or diagnostic | Exact result |
| --- | ---: |
| Raw weight-four field parameters `C(131,4)` | 11,716,640 |
| Canonical length-131 Frobenius orbits | 89,440 |
| Rational orbits `R` | 44,824 |
| Rational orbits with an in-base reciprocal partner `P` | 0 |
| Signed source classes `C=131(R-P/2)` | 5,871,944 |
| Actual usable subgroup points `B=2C` | 11,743,888 |
| Potential signed-Frobenius matrix columns `K=R-P/2` | 44,824 |
| Formal unordered six-summand multiset mean `C(B+5,6)/(r-1)` | 5.353897128996899 |
| Ordinary-query PDP attempts; verified novel rank; target online time | 0; null; null |

The complete canonical-representative stream hashes to
`611baade8561bd3007d6b84c32715423823a7519af283b650434c2b3dac80088`;
the rational stream hashes to
`91717b52d6b48827ddb3e5368fa33cdec4adae31e1ed3d9cd578d869c6955456`.
The rationality/reciprocal flag stream hashes to
`05e27accc0b5d1cc458480bc86765747e9e634d2d38939658a3191570dd1f789`.
All streams use the protocol's canonical gap order and little-endian 17-byte
normal-coordinate masks.

## Independent replay and resource record

[`runs/R1/manifest.json`](runs/R1/manifest.json) binds the exact source
commit `8e5510b7c6a1e83084b35f65a01dbc1ac40352f6`, config, parent,
executables, runtime and result receipts by SHA-256. The independent
[`verification.json`](runs/R1/verification.json) matches all count and
stream-digest fields of [`producer.json`](runs/R1/producer.json), using Sage
field inversion, trace, and an independently reconstructed inverse conversion
matrix. Its 128 fixed sampled points are nonidentity after cofactor-four
projection and killed by the subgroup order. Each of four nontrivial
Frobenius exponents was checked on every sampled point. The exact census has
no in-base reciprocal partner orbit, so the protocol's reciprocal-point
sample is empty. The frozen [`sage_runtime.json`](runs/R1/sage_runtime.json)
records the checked local launcher and installed modules.

| Stage | Status | Wall (s) | CPU (s) | Peak RSS (MiB) |
| --- | --- | ---: | ---: | ---: |
| Complete producer | `PRODUCED_PENDING_INDEPENDENT_SAGE_REPLAY` | 5.768 | 4.545 | 27.55 |
| Full independent Sage replay and point controls | `PASS_FULL_SAGE_ORBIT_AND_POINT_REPLAY` | 12.356 | 9.828 | 256.70 |

Both stages used one worker and completed inside their separate 900-second,
4-GiB envelopes. The host has no qualifying CPU-isolation receipt, so these
wall times are reproducibility diagnostics. The
[`mutation_controls.json`](runs/R1/mutation_controls.json) records rejection
of a changed normal-basis word by the parent hash binding and of one flipped
rationality decision bit by the independent full replay. The generator is
[`mutation_controls.py`](runs/R1/mutation_controls.py); both mutated verifier
invocations exited nonzero without emitting a passing receipt.

## Decision and next measured gate

`B=11,743,888` exceeds the frozen necessary m6 support threshold
`4,121,293`; `K=44,824` is below the frozen 83,843-column limit. Relative to
the published W24 source ledger (`B=16,772,828`, `K=8,384,348`), this policy
retains 70.017% of the base points and has 0.535% as many potential folded
columns, a factor of 187.05 in column count. The formal multiset mean is a
counting diagnostic; the ordinary-query yield and rank are the next measured
quantities.

Freeze deterministic `B=11,743,888` subsets of the original, descendant-native,
transported, and pullback geometries, with exact point digests, map checks,
and one common ordinary-query law. Measure six-summand PDP attempts including
failures, verified relation yield, novel rank, matrix construction and solving,
and target descent. Promote a complete IC candidate ID only after its solver,
collection, LA, and target policies are fixed. Pair any resulting verified
single-target online recovery with rho on the same point and resource envelope.
