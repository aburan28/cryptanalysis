# Frozen protocol: the n = 131 reference walk (IDEA-20261015-c6f017)

Frozen on 2026-10-15, before any timing. The machine-readable form is
[`protocol.json`](protocol.json); its SHA-256 is recorded in every
`analysis.json`. Any change after the first timing row is a dated amendment
below, and both versions are reported.

**Question.** What does one step of a signed-Frobenius rho walk on ECC2K-130's
curve cost, for (a) Bailey's walk `P <- P + sigma^j(P)`, `j = 3 + ((HW(x)/2) mod 8)`,
canonicalized only at distinguished points, and (b) a canonicalizing adding
walk `P <- canon(P + R_h(P))` with `lift_scan`; and how many steps to a
collision does each selector need where walks complete (n = 83, a = 1)?

**Claim classes.**

| Statement | Class |
| --- | --- |
| field, point, canonical-form and walk arithmetic agree with f131.h / packed131.h and with independent Python | exact computation |
| every reported logarithm satisfies `[d]G = Q` | exact computation (checked twice: Rust, Python) |
| ns/step, ratios (a)/(b), canonicalization shares | comparative, Tier 1, this runner only |
| Ir/step | exact count for this binary on this runner's valgrind |
| steps/floor and the Bailey/canonical penalty at n = 83 | comparative (statistical, 128 solves/arm) |
| cycles/iteration beside the 2009 figure | conversion with an unobservable clock: a range, not a ratio |
| cost of an ECC2K-130 walk to collision | **model composition** (heuristic H1), never a measurement |

**Arms, controls, estimators, gates, power and runtime** are as stated in
`protocol.json`: A/A timing copies (`bailey_aa`, `canon_aa`) at their own
addresses, the exhaustive canonicalizer as the timing positive control, the
seed-0/seed-1 split as the completion A/A, and the Frobenius-only walk
(`canon32_noneg`, classes of size n instead of 2n, predicted sqrt(2)) as the
completion positive control. Known-log solves are the correctness positive
control and must pass before timing starts.

**Not established by this experiment.** Anything about solving ECC2K-130;
a host-isolated (Tier 0) timing; the transfer of the n = 83 penalty to
n = 131 beyond heuristic H1; a speedup of either design over crypto's own
tuned n = 83 walk (not run here).

## Amendments

None.
