# Equal-size W24 orbit columns and descendant Frobenius

This **retrospective** exact reanalysis uses the full W24 orbit partition in
parent PR #301 and the equal-size source-prefix selection published in
[PR #305](https://github.com/aburan28/cryptanalysis/pull/305). Both inputs
were visible before this audit. Its result changes the structural matrix
comparison, but it measures no PDP, relation rank, final matrix, DLP, or
speedup. Proposal `Q1420` retains `candidate_id: null`.

| Policy | Actual usable points `B` | Sign-only classes | Potential classes after direct source Frobenius folding |
| --- | ---: | ---: | ---: |
| Source W24 prefix | 16,772,828 | 8,386,414 | **8,384,348** |
| Transported source prefix | 16,772,828 | 8,386,414 | **8,384,348** abstract classes; transport and recognition unpriced |
| Native descendant W24 | 16,772,828 | 8,386,414 | Direct coordinate Frobenius is unavailable; induced quotient unknown |
| Pullback of native W24 | 16,772,828 | 8,386,414 | Source-Frobenius intersection not measured |

The selected source stream has SHA-256
`1372e1938950a4b6e6d2003732ac04102b8f794606669eeffcc5918360484aeb`
and ends at mask `16763440`. Every one of the full source base's 4,104
nontrivial orbit members lies inside that prefix; there are 2,038 distinct
nontrivial representatives, leaving `4,104 − 2,038 = 2,066` saved
potential columns. The saving is **0.0246351%** of the selected signed base,
far below a 1% material threshold of 83,865 columns. A packed 17-byte log
vector alone would save 35,122 bytes. These are potential log-variable
counts, not actual relation-matrix dimensions or measured matrix costs.

[`analysis.json`](analysis.json) rechecks the full source and descendant
gzip/raw mask hashes, the selected-prefix hash and cutoff, the exact W24
base receipt, and the parent full-orbit map and verification hashes. The
independent [`verification.json`](verification.json) recomputes all direct
Frobenius overlaps from GF(2) nullspaces for powers 1–65 and recovers the
same 2,066-column prefix partition without using the component map as an
input. It does **not** independently recompute the reciprocal-overlap
channel: the parent full scan's native and portable backends both found zero
reciprocal hits, so this selected subset has zero as well.

The exact descendant codomain has coefficients `[1,0,0,A,a6]` and a
previously proved endomorphism-order conductor of 263, one `V263` level below
the source's conductor-one surface. Its normalized constant is
`b=a6+A²=1747379673771491065504088712547138692381`. In this
characteristic-two model, `j=1/b`. Checked Sage found
`j=586960249075303795058305401016131957337` and
`j²=206407388974054826092136043365289603407`, which differ. Thus
coordinate squaring sends the descendant to a **nonisomorphic conjugate**,
not back to itself. Squaring its saved generator was checked on that
conjugate and did not lie on the original codomain. The source has `j=1`
and its generator's square remains on the source. The
[`Sage receipt`](sage-verification.json) verifies these exact models using
the checked repository launcher. It does not rule out a transport-induced
action on the prime-order subgroup; that action and its cost remain open.

The first Sage attempt failed because its verifier incorrectly asserted
`j=1/a6` before accounting for `A²`. The raw failure and source hash are
preserved in [`sage-failure-r1.json`](sage-failure-r1.json), with the exact
[failed source snapshot](verify_sage_r1_failed.py). The corrected
check used a fresh [runtime receipt](runtime-info-r2.json) and passed.

The decision is to **deprioritize matrix-orbit folding of unchanged W24**
as the route to an ECC2K-130 IC advantage. The equal-size policies differ
by only 2,066 potential source columns under the direct action; the next
material gate remains held-out ordinary-query W24/m6 PDP yield and novel
rank, including every failed attempt and charged transport cost. A separate
implicit orbit-closed source base is a distinct proposal whose membership
and PDP cost must be measured before it can inherit any claimed benefit.

Reproduce the deterministic checks with fresh output paths:

```sh
python3 experiments/ecc2k130-equal-w24-orbit-columns-20261005/analyze.py --out /tmp/equal-w24-orbit-analysis.json
python3 experiments/ecc2k130-equal-w24-orbit-columns-20261005/verify_direct.py --out /tmp/equal-w24-orbit-direct.json
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /tmp/equal-w24-orbit-runtime.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/ecc2k130-equal-w24-orbit-columns-20261005/verify_sage.py --out /tmp/equal-w24-orbit-sage.json
```

The direct verifier reads the committed analysis rather than the fresh
`/tmp` replay; compare the deterministic counts and hashes in both outputs.
The Sage script reads the committed checked runtime receipt while the fresh
receipt above documents the replay environment.
