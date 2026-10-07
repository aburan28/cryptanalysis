# Native selective mixed-alphabet replay gate

Freeze `src/main.rs`, `src/selective.rs`, this protocol, and the
independent Sage seed generator before release replay. The new
`selective-seed-fixture.json` is generated after its source freeze and
contains all 12 coefficient seed points for each of 72 distinct bases
from the original and new selective panels. Its Sage arithmetic uses
the saved curve and `τP=P−ω(P)` independently of native point
preparation.

The native selector must independently compute the short scalar
representative, original baseline residues, and finite dynamic
program. Store candidate paths as arena backpointers and reconstruct
only the winning stream, without cloning an entire digit prefix on
every accepted state transition. Reproduce the saved per-case total,
preparation cost, used
and built seed sets, selected digit count, and state count. Verify the
carry bound and compare every built seed point with Sage. Evaluate
every selected digit stream with the native 12-seed path; compare all
64 original and 256 fresh scalar outputs with Sage. Recount paired τ
strides, solo τ steps, mixed/cached additions, and cache entries from
the executed point path, and require agreement with the saved source
count. Record exceptional additions and all raw exits. Also replay the
original 64-case native mode as a regression control.

The native `--benchmark-selective-case` interval starts after input
loading and static table initialization. It includes scalar parsing,
short-representative lattice reduction, baseline recoding, every
dynamic-program transition, selected-seed point preparation, orbit
construction, cached point evaluation, affine inversion, formatting,
and correctness comparison. A paired fixed-portfolio benchmark
requires the same frozen target, host, resource envelope, and full
operation interval. Host-isolated timing may be claimed only after
the repository's physical-host preflight and noise gates pass. This
protocol itself asserts no CPU speedup, constant-time suitability, or
academic novelty.
