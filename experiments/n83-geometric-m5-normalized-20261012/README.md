# Frobenius-normalized N83 five-summand search

This stage searches the full shifted width-13 factor base with one leaf fixed
to a rational affine seed. The other four leaves independently select any
of 83 Frobenius powers. The target selector ranges over all 83 rotations
of each of the public point's four raw cofactor preimages. The factor base
is the same **4,125-column, 684,750-point** base used by the
[orbit-complete parent](../n83-geometric-m5-orbit-20261012/README.md),
and the public workload remains `df4396f4d8fc`.

The formula has **76,858 AND gates, 327,039 CNF clauses, and 1,590 native
XOR rows**. Its parent has 82,668 gates, 334,247 clauses, and 1,660 XOR
rows. These are exact formula-shape counts, not solver-time ratios. A locked
control with first-leaf Frobenius power 17 returned SAT; exact point replay
rotated the relation back to the original public point. The independent
Sage polynomial-field verifier checks this replay again.

## Why the normalization covers the base

Write the original five-point relation as
`F^k(s) + P1 + P2 + P3 + P4 = T`, where `s` is an affine seed and `F` is
Frobenius. Applying `F^(-k)` gives
`s + F^(-k)(P1) + ... + F^(-k)(P4) = F^(-k)(T)`. Each transformed remaining
point stays in the Frobenius-complete base. Conversely, applying `F^k` to
a normalized relation recovers a relation for the original public target.
The runner performs that inverse rotation and verifies every point,
cofactor projection, base key, subgroup membership, sign, and public sum.
The parent [coverage receipt](../n83-geometric-m5-orbit-20261012/coverage.json)
exhaustively checks the complete signed base and canonical key file.

The conditional additive-group step is formalized in
[Normalization.lean](Normalization.lean). `normalize_five` and
`denormalize_five` preserve the full five-term equation under inverse
additive maps; `normalize_preserves_four_memberships` carries the four
remaining base memberships under closure. The pinned
[toolchain](lean-toolchain) is Lean 4.34.1. Running `lean Normalization.lean`
in this directory produced the committed [build output](lean-build.txt) and
`#print axioms` audit: the equation lemmas use only standard `propext`, and
the membership lemma has no axioms. The Lean module takes additive-map and
base-closure hypotheses explicitly. Definitions and proofs connecting those
hypotheses to the specific binary elliptic curve and Frobenius action remain
open; the formalization of that bridge is partial. Exact point replay and
independent Sage checks cover the executed instance.

| Result | Lean declaration | Exact hypotheses | Status |
| --- | --- | --- | --- |
| Five-term normalization | `N83Normalized.normalize_five` | Additive `I`, `I(F x)=x`, and the original five-term equality | Checked |
| Inverse recovery | `N83Normalized.denormalize_five` | Additive `F`, `F(I x)=x`, and the normalized five-term equality | Checked |
| Remaining leaves stay in the base | `N83Normalized.normalize_preserves_four_memberships` | Base closure under `I` and membership of four points | Checked |
| N83 curve and Frobenius bridge | — | Exact `GF(2^83)` curve, cofactor projection, and orbit closure | Partial; definitions and proof open |

## Frozen experiment

The [protocol](protocol.json) binds the same public target, key file,
source, solver, and resource limits as the parent: one CryptoMiniSat thread,
five million conflicts, a 600-second wall cap, a 4 GiB sampled solver-RSS
stop, and at most three models. The run receipt retains all attempts,
exclusive target-dependent phases, raw solver output, and compressed XCNF.
Times on the local unisolated host are exploratory.

The ordinary width-13 attempt completed its 600-second wall bound with
`external_timeout` and status `bounded_unknown`; sampled solver peak RSS
was 1,311,571,968 bytes. The receipt verifier passed source, input, XCNF,
solver-output, control, and exclusive phase checks. Independent Sage replay
passed the locked normalized control and recorded
`no_relation_to_replay` for the ordinary target. The exact width-14 and
width-15/16 follow-ups test whether larger bases raise natural solution
density enough to change this bounded solver outcome.

The follow-ups retain the same public workload:
[width 14](../n83-geometric-m5-normalized14-20261012/README.md),
[widths 15 and 16](../n83-geometric-m5-normalized15-16-20261012/README.md),
a [fixed relative-power width-16 slice](../n83-geometric-m5-fixedpowers16-20261012/README.md),
and an [aligned-power width-16 slice](../n83-geometric-m5-zeropowers16-20261012/README.md).

| Proposal | Base width | Folded `K` | Usable `B` | Five-subset first moment | AND gates | Ordinary target at 600 s |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Q2026101243, free powers | 13 | 4,125 | 684,750 | 518.851 | 76,858 | `bounded_unknown` |
| Q2026101244, free powers | 14 | 8,261 | 1,371,326 | 16,714.350 | 76,941 | `bounded_unknown` |
| Q2026101245, free powers | 15 | 16,376 | 2,718,416 | 511,643.070 | 77,024 | `bounded_unknown` |
| Q2026101245, free powers | 16 | 32,648 | 5,419,568 | 16,114,307.725 | 77,107 | `bounded_unknown` |
| Q2026101246, fixed relative powers | 16 | 32,648 | 5,419,568 | 16,114,307.725 | 54,545 | `bounded_unknown` |
| Q2026101247, aligned powers | 16 | 32,648 | 5,419,568 | 16,114,307.725 | 52,719 | `bounded_unknown` |

The first moment is an exact uniform-target combinatorial diagnostic for
the complete base, not the solution count of a restricted power slice.
All six ordinary attempts retained their `external_timeout` rows. Their
locked relation controls and independent Sage replays passed; the
ordinary-target statuses remain bounded by the 600-second solver interval.
CPU wall times on this shared host are exploratory. A separate
[canonical-x lookup](../n83-orbit-key-x-20261012/README.md) reduces the
target-independent base setup path and materializes its checked output.

From a fresh checkout, the checked Sage launcher is required for local
Sage work:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-normalized-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized-20261012/control.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-normalized-20261012/verify.py
```

Each producer refuses to overwrite terminal evidence. Replaying the
published workload uses the frozen protocol and public point; a fresh
target requires a new protocol and workload ID.
