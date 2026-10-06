# Explicit mapping cost and matched native rho follow-up

This run closes the previously missing per-key cost category and retests the
three depth-two holdout leaders plus the strongest widened one-hop point
estimate in a fixed-limb native backend.

## Per-key path transfer

The frozen affine rational maps were parsed once and then evaluated on both
source points required for one ECDLP instance, `P` and `Q = kP`. Each result
reproduced the retained endpoint generator and preserved the discrete-log
relation.

| Path | Reusable map parsing | Mean P,Q evaluation | 95% CI | Native-rho-equivalent iterations |
|---|---:|---:|---:|---:|
| 3,11 | 0.183368 s | 955.920 us | 940.051–971.788 us | 670.2 |
| 3,13 | 0.018276 s | 972.114 us | 950.346–993.883 us | 680.3 |
| 5,13 | 0.020604 s | 954.284 us | 935.549–973.019 us | 669.0 |
| 47 | 0.052766 s | 654.552 us | 645.979–663.124 us | 454.0 |

The setup-time spread is dominated by Sage parsing and first-use effects, so it
is accounting rather than a curve-ranking metric. The per-key transfer is at
most 681 measured native rho iterations, negligible beside the generic
`sqrt(pi*n/2) = 2^128.326` expected iteration count. This observation does not
turn a null timing result into a speedup.

## Matched native Pollard rho

All five curves used the same fixed-limb P-256 Montgomery field arithmetic,
the same general-`a` complete projective formula, 64-way batch normalization,
the same 16-entry r-adding walk, and native `U256` coefficient tracking. The
15 one-second trials used rotating execution positions and three complete
position blocks. Every post-trial rho state retained its checked linear
relation.

| Path | Iterations/s | Paired relative speed | Paired 95% CI |
|---|---:|---:|---:|
| P-256 | 699,078 | 1.0000x | 1.0000–1.0000x |
| 3,11 | 701,138 | 1.0031x | 0.9847–1.0217x |
| 3,13 | 699,818 | 1.0011x | 0.9803–1.0222x |
| 5,13 | 701,087 | 1.0029x | 0.9804–1.0259x |
| 47 | 693,630 | 0.9919x | 0.9738–1.0104x |

No interval excludes `1.0`; none of the four candidates shows a significant
native iteration-rate advantage. Since the candidates have the same prime
group order and no extra automorphisms or low-norm endomorphisms, the measured
per-key map is only overhead and there is no end-to-end attack speedup in this
panel.

## Cost boundary and limits

- Discovery to the selected endpoints was 1.300 s, 1.473 s, 1.922 s, and
  18.178 s respectively in the retained searches; it is reusable.
- Retained-map parsing is reusable and reported separately above.
- P,Q path evaluation is paid for each public key.
- The ECDLP projection remains generic expected work, not a full P-256
  collision experiment.
- CPU isolation and frequency stability were not independently verified, so
  wall-time measurements remain exploratory.
- This is a focused native retest of four screening leaders, not an exhaustive
  class-group traversal or proof about every curve in the isogeny class.
