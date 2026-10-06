# Attempted one-hop extension through degree 199

Every rational prime degree at most 199 classified as ramified or split by the
P-256 Frobenius discriminant was attempted. Independent Sage 10.6 panels
successfully retained both horizontal neighbors at degrees 59, 97, 101, and
103. Together with the prior completed degrees through 47, the one-hop
registry now contains P-256 plus 28 neighbors. Its union with the depth-three
registry contains 78 unique curves, eight more than before.

Every retained curve has an explicit path from P-256, the same prime group
order, and geometric automorphism order two. No exceptional `j`-invariant or
low-norm endomorphism was found.

## Resource boundary

The extension is not a complete enumeration through 199. The exact status is:

- completed: 59, 97, 101, and 103;
- failed from PARI stack exhaustion at 8 GiB: 137, 149, and 151;
- interrupted while retrying 157 after those three consecutive 8 GiB failures;
- not retried at 8 GiB: 163, 179, 181, 191, 197, and 199; each had already
  failed independently at 4 GiB.

The two independent panels consumed 4,165.75 seconds (69.43 minutes) of wall
time, including failed work. Successful new-degree computations account for
661.02 seconds. Earlier monolithic 1 GiB and 4 GiB attempts also failed from
stack exhaustion, but their raw console logs and elapsed times were not
retained; they are disclosed but excluded from the measured total. The raw
per-degree tracebacks are preserved in the panel status artifacts.

## Matched native rho screen

The eight new neighbors and P-256 received nine 0.5-second trials apiece, one
complete rotation through all timing positions. The implementation was
identical across curves: fixed-limb Montgomery arithmetic, complete general-`a`
projective formulas, 64-way batch normalization, a 16-entry r-adding table,
and native coefficient tracking. Every post-trial linear relation verified.

| Degree | Endpoint suffix | Relative speed | Paired 95% CI |
|---:|---|---:|---:|
| 59 | `5bebf0310fb7` | 0.9903x | 0.9503–1.0321x |
| 59 | `89ce0f994d48` | 1.0062x | 0.9605–1.0540x |
| 97 | `2edfcf9b90fe` | 1.0084x | 0.9770–1.0409x |
| 97 | `3bd2c2392489` | 0.9797x | 0.9200–1.0431x |
| 101 | `58127df8f732` | 0.9916x | 0.9541–1.0305x |
| 101 | `6571da91cf00` | 1.0005x | 0.9680–1.0340x |
| 103 | `3ca756d78fbf` | 0.9915x | 0.9449–1.0403x |
| 103 | `8556979e75fd` | 1.0049x | 0.9766–1.0340x |

Every interval includes `1.0`, so no candidate triggered a fresh holdout. With
the earlier screens, all 77 explicitly retained non-root curves now have a
matched native measurement and none has a reproducible advantage.

Discovery/precomputation cost is reported above. Per-key evaluation of these
new higher-degree maps was not timed, so no amortized end-to-end attack cost is
claimed. The wall-time screen is exploratory because CPU isolation and
frequency stability were not independently verified. It measures generic rho
iteration cost, not a full P-256 collision experiment, and says nothing about
the unresolved degree-137-and-higher endpoints or the rest of the isogeny
class.
