# Native genus-two construction run

Question: construct a genus-two cover and a group-preserving Jacobian transfer
for both pinned a=0/a=1 elliptic curves over GF(2^83), in their exact
z^83+z^45+z²+z+1 basis. Run label: `run-20261014T1442Z`;
the n83 output was written 2026-10-14 14:47:07 UTC.

The [full report and written proof](../../REPORT.md),
[four-page PDF](../../report.pdf), [map diagram](../../figures/transfer.svg),
and [recorded-count graph](../../figures/counts.svg) cover this run.
Raw records, failures, compiler/environment data, source bindings and exact
commands are [in the run directory](../../runs/run-20261014T1442Z/).

Both requested variants completed. Each supplies an explicit genus-two
model, separable degree-three map, valid reduced D_P/D_Q, exact source and
image subgroup order, image-inverse round trips, eight scalar controls,
eight addition controls, and D_Q=37D_P. The two subgroup orders remain
2417851639230796216685689 and 8569786107849059. See `n83-final.json` for every
point, divisor, field and source/target identity.

Controls exhaustively enumerate rational curve points and ordered elliptic
addition pairs over field sizes 2,4,8,16, both a values. Their recorded
counts and graph have no sampling uncertainty. No n83 field/subgroup scan,
cost comparison or timing result is reported. All checks are local to one
managed host; independent-host replay is unperformed.

The native preflights and sparse-checkout build failures are retained. Missing
tracked fixtures were materialized; the native cover tests, CLI rejection
controls and exact-identity replay pass. Lean's central map-equation theorem
and axiom audit pass; genus and Picard geometry retain the explicit partial
formalization gap in the full report. Neither an unknown-log solve nor a
faster destination solver follows from these observations.

The whole `crypto` library run finishes with 4087 passed, two failed existing
JV F4 completion-threshold assertions, and 117 ignored. The two tests pass
in a serial diagnostic on the same binary; that does not discharge the full
gate. The report links the precise unresolved validation problem.
