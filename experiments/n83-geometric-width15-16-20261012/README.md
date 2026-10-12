# Shifted N83 width-15 and width-16 factor bases

Exhaustive enumeration on `EC1N83Ckb1h876c2921cb64` gives these exact
shifted affine bases. Each rational x seed in
`gamma_82 + span(gamma_1,...,gamma_d)` is projected by cofactor four and
closed under sign and 83 Frobenius powers.

| Width | Rational x lifts | Folded columns `K` | Usable points `B` | Distinct five-subset first moment |
| --- | ---: | ---: | ---: | ---: |
| 15 | 16,377 | 16,376 | 2,718,416 | 511,643.0698604108 |
| 16 | 32,652 | 32,648 | 5,419,568 | 16,114,307.72534703 |

The [frontier receipt](frontier.json) retains exact first moments, the
duplicate orbit counts, 83K² root-index states, deterministic payload
bounds, source hashes, and sorted canonical key files. The full root
payloads exceed the 8 GiB process cap; the paired five-summand SAT
experiments use the key sets without allocating those indexes. These
first moments describe uniform-target combinatorics and do not replace
measured relation yield or matrix rank.

The [independent Sage replay](independent_sage_replay.json) returned `PASS`
for both widths. It checked every x seed and projected subgroup point in
a separate polynomial-basis field, then checked canonical key bytes and
166 signed Frobenius variants per column. The checked Sage launcher
[runtime receipt](sage_runtime_info.json) was saved before both jobs.

Reproduce in a fresh experiment directory through the repository launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-width15-16-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-width15-16-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-width15-16-20261012/verify_sage.py
```

The [normalized five-summand follow-up](../n83-geometric-m5-normalized15-16-20261012/README.md)
holds the public target and solver limits fixed while testing these bases.
