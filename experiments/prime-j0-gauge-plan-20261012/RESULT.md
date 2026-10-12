# Cached gauge plans for fixed-base secp256k1 multiplication

Format 172 precomputes the gauge-aware tree schedule for every feasible
gauge-count triple. On the frozen 4,096-scalar panel it removes **3,727,178
online pair-gauge score evaluations** from format 171 while preserving its
exact selected points, 12,886 gauge rotations, 528,972 nominal ordinary-path
field products, and 201,965 summed modeled product depth. The complete plan
table adds **28,560 bytes**; total retained table, constants, and plans are
**64,342,768 bytes**.

| Frozen panel measure | Format 171 dynamic tree | Format 172 cached plan |
| --- | ---: | ---: |
| Cases | 4,096 | 4,096 |
| Active terms | 57,343 | 57,343 |
| Online pair-gauge scores | 3,727,178 | 0 |
| Gauge rotations | 12,886 | 12,886 |
| Nominal field products | 528,972 | 528,972 |
| Sum of modeled product depth | 201,965 | 201,965 |
| Retained bytes | 64,314,208 | 64,342,768 |

The native release tests matched all 4,096 scalar records to format 171 and
the first 128 points to independent binary multiplication. The 680 feasible
gauge-count plans each matched a dynamic tree evaluated on real affine table
points, including point, rotations, and depth. The release CLI matched all
129 independent fixture cases. `screen.py` independently reconstructed the
frozen gauge counts and online selector-work total; `receipt.json` binds the
source, binary, inputs, test logs, and verifier by SHA-256.

The point-sum proof is inherited from the checked Lean tree theorem mapped
in `PROOF.md`. Source comparison counts and nominal field products are
algorithmic diagnostics. Recoding, point-table access, final inversion,
branch behavior, and memory hierarchy remain in the full online call. The
next gate is a paired mode-171/mode-172 complete-operation run on a host that
passes the isolated CPU preflight, with construction charged to preparation.
