# Matched native screen of the full retained registry

The earlier focused native panel covered four screening leaders. This run
screened the remaining 65 curves in the union of the depth-three and widened
one-hop registries, so all 69 explicitly retained non-root curves now have a
matched native rho measurement against P-256.

## Screening design

- 65 candidates were divided into 11 root-controlled blocks of at most six.
- Each block used 0.5-second trials and one complete rotation through every
  timing position (seven trials for ten blocks, six for the final block).
- Every curve used the identical fixed-limb P-256 Montgomery field, complete
  general-`a` projective formulas, 64-way batch normalization, 16-entry
  r-adding table, and native `U256` coefficient tracking.
- Every post-trial rho linear relation verified.
- A lower endpoint above `1.0` in an unadjusted paired 95% interval was only a
  screening trigger and required a fresh holdout.

Two of 65 candidates triggered that rule:

| Path | Screening speed | Screening 95% CI |
|---|---:|---:|
| 17 | 1.0263x | 1.0097–1.0431x |
| 23 | 1.0229x | 1.0070–1.0392x |

## Fresh holdout

The two hits were retested together with P-256 using 30 fresh two-second trials
per curve and ten complete timing-position rotations.

| Path | Holdout speed | Holdout 95% CI |
|---|---:|---:|
| 17 | 1.0069x | 0.9923–1.0217x |
| 23 | 1.0030x | 0.9879–1.0183x |

Neither holdout interval excludes `1.0`. The two screening hits therefore do
not reproduce and no candidate advances.

## Combined result and limits

The complete explicit registry contains P-256 plus 69 neighbors. Four leaders
were tested in the prior 15-trial native panel; the other 65 were screened here,
and both unadjusted hits received a longer independent holdout. No candidate
shows a reproducible native rho iteration-rate advantage. All curves retain the
same prime order, automorphism order two, and absence of a useful low-norm
endomorphism established by the structural analysis.

This is complete only for the 70 explicitly reached curves, not for the entire
isogeny class. CPU isolation and frequency stability were not independently
verified, so the wall-time figures remain exploratory. A full P-256 collision
experiment remains unnecessary and infeasible; the benchmark tests generic
iteration cost and verifies rho state relations instead.
