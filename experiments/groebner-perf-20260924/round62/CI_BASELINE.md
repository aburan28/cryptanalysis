# Exploratory Linux measurement of the preceding F4 changes

Re-evaluated on 2026-10-04 under the repository's CPU isolation gate: this
hosted runner has no auditable host-level isolation receipt. All wall-time
ratios below are exploratory; aggregate speedup and promotion eligibility are
unknown. The archived `qualified` labels mean only that the older load and
sampling gates passed. They do not establish exclusive physical cores, fixed
frequency, IRQ isolation or an eligible controlled speedup.

This is evidence for round 57's comparison of prior, checked-chain, reducer-filter,
combined chain/filter and evaluation paths. It is not a timing result for the
round 62 packed candidate.

The independently audited push run 37159417787 of PR #219 used source head
`d30e5d8eeb40822b6260b3d94c306c0325d6edda` on a hosted Linux x86-64 runner
reporting an AMD EPYC 9V74 and four logical CPUs. All 928 sequential query records
and 33 qualified trials were retained. All 15 primary case/trial comparisons
passed the frozen improvement gate; the further-2x gate did not pass.

| Six-variable fixture | Prior median query time across trials | Combined median query time across trials | Paired median speedup range | Lowest 95% lower bound vs prior |
| --- | ---: | ---: | ---: | ---: |
| Seed 1 | 7.628–7.668 ms | 5.286–5.308 ms | 1.442–1.450x | 1.435x |
| Seed 2 | 7.570–7.619 ms | 5.217–5.232 ms | 1.445–1.457x | 1.428x |
| Seed 3 | 5.224–5.237 ms | 4.741–4.782 ms | 1.101–1.104x | 1.082x |
| Seed 4 | 7.050–7.113 ms | 4.725–4.738 ms | 1.493–1.496x | 1.487x |
| Seed 5 | 7.059–7.094 ms | 4.720–4.727 ms | 1.497–1.504x | 1.490x |

Each trial contains seven measured pairs after a warmup. Intervals are the frozen
per-trial paired-bootstrap intervals; these repeated fixtures do not estimate
natural relation yield or provide a population/familywise guarantee. These are
complete PDP query times, including original-equation and curve checks, not
complete IC online solves or rho ratios.

Evaluation remains faster on these small fixtures: 2.429–3.826 ms across their
trial medians. It remains in the panel as a diagnostic comparison. The combined
F4 path's seed-1 exclusive phase medians are approximately 0.229 ms for descent,
2.448 ms for algebra plus certification, 1.330 ms for extraction/curve checking,
and 1.283 ms for reference replay. These separate medians must not be treated
as an exact additive query observation. They identify equation/curve replay as
an important next target after the packed matrix candidate; correctness checks
must remain charged and independent.

The paired macOS ARM64 push artifact also passes correctness/audit but admits no
timed queries under its three-CPU load gate. Its runner identifies itself as an
Apple M1 (Virtual), so it does not establish a macOS speedup or physical M4 result.
The PR-event artifacts and remaining CI checks are separate merge gates. The
measurement data and integrity receipts are preserved in
`results/round57-qualified-ci.json.gz`.
