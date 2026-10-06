# Result: Frobenius recoding accelerates Koblitz scalar calls

All ratios are signed-window parent time divided by tau-adic candidate
time for complete `Curve.mul` calls. Recoding, negation, all Frobenius maps,
and point additions are charged. Each warm number is a ratio of paired
twelve-round medians on an exact public point and scalar. Both the primary
and independent confirmation sets cover local ONB and the tracked IC
runner's `AuditField` at degrees 53 and 131.

| Phase | Curve copy / degree | 16-bit control | 32 bits | 64 bits | 131 bits |
| --- | --- | ---: | ---: | ---: | ---: |
| Primary | Local ONB / 53 | 1.010x | 1.609x | 1.632x | 1.604x |
| Primary | Tracked `AuditField` / 131 | 1.005x | 1.698x | 1.729x | 1.487x |
| Confirmation | Local ONB / 131 | 0.983x | 1.848x | 1.592x | 1.593x |
| Confirmation | Tracked `AuditField` / 53 | 1.023x | 1.524x | 1.649x | 1.575x |

The geometric mean across the six large-scalar cells is 1.625x primary
and 1.627x confirmation. All large-scalar first calls, measured with
independent fresh field contexts, also improved: their geometric means
were 1.492x and 1.468x, with the weakest first-call ratio 1.383x. The
16-bit path remains the previous binary loop and was within 2% in paired
warm measurements. Process peak RSS was 22.0–25.1 MiB, below the declared
512 MiB cap. Every timed output matched the parent and lay on the curve.

The endomorphism relation was checked directly on small-field and wide
points. Tau-adic division and reconstruction matched the signed-window
parent on exhaustive small-field scalars and through 256-bit scalars on
wide fields, including negative inputs and order-two points. Five selected
tracked runner arithmetic tests passed. For a separate 131-bit diagnostic
on the tracked `AuditField`, field inversions fell from 160 to 81 and field
multiplications from 320 to 162; Frobenius calls rose from 291 to 601.
These are logical calls, not calibrated end-to-end IC operations.

The runner invokes `Curve.mul` in setup, subgroup checks, relation work,
and recovery checks. This PR measures that arithmetic operation, not a
complete verified DLP. A frozen full IC run must charge all exclusive
phases, confirm the recovered logarithm, and compare with its declared
baseline before any IC speedup or rho-boundary claim.
