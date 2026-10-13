# Exact N83 trace-zero z-coordinate factor-base census

The exact 11-dimensional `z=x+1/x^2` subspace has **2,016 signed-Frobenius
columns** and **334,656 usable subgroup points** after closing the seeds
under sign and Frobenius. Each of its 2,048 `z` values has exactly **one**
affine `x` root. This directly tests the proposed extra-fiber mechanism:
the three-root fibers do not occur in this frozen subspace. The existing
shifted width-12 `x`-base has 2,130 columns and 353,580 usable points, so
this particular `z`-base does not improve either geometric count.

| Exact geometry | `z in span(t,...,t^11)` | shifted width-12 `x` |
| --- | ---: | ---: |
| Coordinate dimension | 11 | 12 |
| Coordinate candidates | 2,048 | 4,096 |
| Affine `x` roots or usable `x` seeds | 2,048 | 2,130 |
| Nonidentity projected seeds | 2,047 | 2,130 |
| Signed-Frobenius columns `K` | 2,016 | 2,130 |
| Actual subgroup points `B` | 334,656 | 353,580 |
| Full-base five-subset first moment, `binom(B,5)/r` | 14.46669 | 19.04650 |

The right-hand values are the independently replayed [width-12 stage
reference](../n83-geometric-m5-gate-20261012/README.md). These bases have
different constructions, so the table is a geometry comparison. The
five-subset first moments use the entire signed-Frobenius-closed bases,
rather than the unrotated seed domains searched by an existing SAT formula.
The `z`-coordinate decomposition circuit, ordinary-query relation yield,
rank, final linear algebra, and single-target online interval remain
unmeasured. `candidate_id` remains null.

## Construction and exact checks

The field is `F_2[t]/(t^83+t^7+t^4+t^2+1)`, the curve is
`y^2+xy=x^3+1`, and the prime subgroup order is
`r=2417851639230796216685689` with cofactor 4. For `x != 0`, set
`u=y/x`. Dividing the curve equation by `x^2` gives
`u^2+u=x+1/x^2=z`, hence every rational point has trace-zero `z`.
The frozen [protocol](protocol.json) takes all 2,048 vectors in
`W=span_F2(t,t^2,...,t^11)`, solves `x^3+zx^2+1=0`, lifts each root,
and projects by 4.

The [producer](census.py) used the repository's checked Sage launcher and
saved the exact root and polynomial-coordinate orbit-key sets in
[roots.bin](roots.bin) and [keys.bin](keys.bin). Its [census](census.json)
records root histogram `{0: 0, 1: 2048, 3: 0}`, one projected identity,
31 repeated signed-Frobenius seed keys, and `K=2048-1-31=2016`.
The [independent Sage replay](independent_sage_replay.json) reads the frozen
root bytes and reconstructs all `z` values. For a known root `x`, it
checks that the remaining quadratic is `X^2+(z+x)X+1/x` and that
`Tr((1/x)/(z+x)^2)=1`, which certifies that no second or third root
exists. It also repeats curve and subgroup checks and computes the
signed-Frobenius orbit keys in the independent normal-basis encoding.
The full root and key sets are hash-bound to the census and replay records.

Every nonidentity subgroup point has a Frobenius orbit of length 83: a
shorter orbit would put it in `E(F_2)`, whose order is 4, while its order
divides odd prime `r`. Its sign is a disjoint orbit because an odd-order
point cannot equal its negative, and 83 is prime. Thus each folded
column contributes exactly 166 subgroup points and `B=166K=334656`.

The checked [runtime identity](sage_runtime_info.json) was saved before
the producer. The census's 496.91-second elapsed interval is a local,
unisolated construction diagnostic; it is outside any online target
interval. The direct `z`-SAT encoding would introduce an
`x in F_(2^83)` variable and its cubic constraint for each leaf.
Eliminating those variables might give a different circuit, so this
census alone does not establish a PDP cost ordering. A concrete follow-up
is to derive a sign-sensitive `u=y/x` relation circuit, count its Boolean
degree and gates, then pair an ordinary target solve with the width-12
`x` arm.

## Proof map and reproducibility

The coordinate identity follows by dividing the displayed curve equation
by `x^2`. The singleton-fiber assertion for this exact finite subspace
is certified by the producer's exhaustive enumeration and the independent
quadratic-trace check; the point and orbit counts have an independent Sage
replay. The [pinned Lean probe](lean-attempt.txt) records the installed
toolchain and unavailable field-algebra declarations. Lean formalization
of the finite-field irreducibility criterion,
all 2,048 fiber certificates, and the actual elliptic-curve subgroup/orbit
bridge is **open**. This repository's pinned Lean 4 environment has no
field algebra library; an arithmetic-only Lean lemma would not prove the
central finite-field assertion. The precise missing work is a verified
`GF(2^83)` model and checker for the root, trace, and subgroup certificates.
The written algebraic proof and executable finite enumeration are retained.

Audit the committed receipts from the repository root:

```sh
python3 experiments/n83-z-coordinate-base-20261012/verify.py
```

For full regeneration, use a disposable checkout with copies of this
protocol and the two Sage scripts and an empty output directory at the
same repository path. Save
`/Volumes/SSD990/cryptanalysis/sage --runtime-info` before running
`census.py` and `verify_sage.py` through that checked launcher. Both
scripts refuse to replace existing evidence files.
