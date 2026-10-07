# Held-out one-target unit-coordinate plane result

The fresh public `glv-j0-32` target `(1838303333, 4245449608)` was
frozen in commit `6b61d5ba` with an independent affine Python group law.
The fixture scalar is `3339527` relative to base
`(481899190, 1998487369)`, and the rho seed is
`7890756355620512173`. The solver arguments contained only the public
point and seed. Each invocation built an empty distinguished-point table.

All six serial Release solves and six serial UBSan solves recovered and
independently replayed the fixture scalar. The generic rho reference,
paired2-batch, and paired2-plane-batch modes each recorded 1,537
reference-equivalent rho operations, 40 distinguished-point entries,
eight multiplier-table evaluations, four restarts, and 829
reference-equivalent startup operations. The candidate modes each used
161 τ steps, 92 mixed additions, five output inversions, and the same
recodings and pair scores. The rho walk stayed paired.

| Target-dependent cost | Paired2 batch | Unit-plane batch |
| --- | ---: | ---: |
| Prepared object bytes | 1,104 | 1,392 |
| Preparation coordinate rotations | 0 | 36 |
| Evaluation coordinate rotations | 54 | 0 |
| Table output inversions | 1 | 1 |
| Restart output inversions | 4 | 4 |

The plane traded 288 additional prepared bytes and 36 preparation field
multiplications for 54 evaluation field multiplications, a net saving of
18 on this complete one-target solve. The prior target, used only during
development, had 80 evaluation rotations and the same 36 preparation
rotations. These are exact arithmetic counts for the implemented paths;
the preparation and batch-normalization costs are inside the online
interval. The plane is a representation change to the existing paired τ
scheme, and academic novelty is unproved.

Local Release `online_ms` values in the frozen order were `0.159,0.159`
for generic rho, `0.133,0.124` for paired2-batch, and `0.110,0.112`
for paired2-plane-batch. The intervals are short and the host lacks a
qualifying CPU isolation receipt. The raw `panel_local.json` and
`panel_ubsan.json` preserve every solve and keep `cpu_speedup_claim` and
`isolation_receipt` as `null`; no controlled CPU ratio is available.

`make_isolated_manifest.py` binds this target to the strict serial runner.
It can pair the plane with generic rho for the primary one-target question
or with paired2-batch to isolate the representation change. A passing
host-level isolation and noise receipt is required before enabling
automatic routing or claiming a wall-time speedup.
