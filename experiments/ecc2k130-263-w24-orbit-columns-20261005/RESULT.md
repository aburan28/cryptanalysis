# ECC2K-130 W24 Frobenius-column result

**Folding the existing W24 base saves only 2,066 of 8,393,232 signed log
columns (0.0246151%).** This is 81,867 columns short of the preregistered
1% material-saving threshold. The verified degree-263 transported copy has
the same group-orbit partition, but transporting and recognizing its points
is not priced. This is a factor-base geometry result, not an IC candidate or
a DLP speedup. No natural PDP, useful rank, relation matrix, target log, or
paired rho interval was measured; `candidate_id` remains `null`.

The [protocol](PROTOCOL.md) and [configuration](CONFIG.json) were committed
as `9f43e94ce21f8df6b472bb687f096a5265b009cd` and opened in
[PR #301](https://github.com/aburan28/cryptanalysis/pull/301) before the
full scan. They pin the merged W24 mask stream, field, curve, route, 4-GiB
RSS and 3,600-second wall limits, and 1% decision threshold. The scan uses
`w^(2^k)` and `(1/w)^(2^k)` for `1 <= k <= 65`, where `w` identifies a
signed `[4]`-projected subgroup class. Reciprocal coordinates represent
translation by rational order-four torsion; reverse Frobenius powers cover
the remaining exponents. The full source stream contains 8,393,232 unique
rational masks and has raw SHA-256
`59f89b3f9b2773963f1a722737f34740e1bfc657aaa277bef4c2e74a6746ffdd`.

| Exact quantity for original source W24 | Value |
| --- | ---: |
| Usable subgroup points before sign folding, `B` | 16,786,464 |
| Sign-only potential log variables | 8,393,232 |
| Sign-plus-Frobenius orbit representatives among those points | 8,391,166 |
| Potential variables saved | 2,066 (0.0246151%) |
| Masks in nontrivial intersections of the base with their signed Frobenius orbit | 4,104 |
| Orbit components of sizes 1, 2, 3, 4 | 8,389,128; 2,012; 24; 2 |
| Direct / reciprocal scan hits before union deduplication | 2,096 / 0 |
| Raw 17-byte-per-log vector saved, excluding all other costs | 35,122 B |

The 2,066 saved columns are a **potential** quotient. A real relation
matrix still needs scalar/sign labels, efficient orbit recognition, row
rewriting, verified novel rank, and its own accounting. The native ARM PMULL
and portable bitwise builds gave byte-identical spanning forests and
canonical nontrivial-component maps on the complete W24 stream. An
independent pure-Python GF(2) nullspace replay enumerated the intersection
`W24 ∩ Frobenius^(-k)(W24)` for every `k=1,...,65` and recovered all 2,096
direct hits and exactly the same 8,391,166-component partition without
using the native field code or an eight-million-mask scan. It does not
independently enumerate the zero reciprocal-hit channel; that result rests
on the two complete native backends. The direct hits occur only at powers
1, 2, and 3 (2,064, 28, and 4 hits respectively); powers 4 through 65
have no rational intersection with this base. An
independent checked-Sage verifier exhausted the 492-mask W10 control and
reconstructed all 481 point-orbit classes, including 16 reciprocal
point-law controls. At full W24 it checked all 2,066 forest edges
structurally, independently replayed a frozen SHA-selected sample of 256
edges as elliptic-curve Frobenius equalities, and checked the frozen source
and route digests. The two complete native backends agree on all
8,393,232 masks; the full-field point-law sample alone is not an exhaustive
independent recomputation. No run failed or timed out.

The native and portable scan times were 27.38 and 127.01 seconds, with
peak RSS near 236 MB, on this unisolated Apple ARM host. These are
reproducibility diagnostics, not controlled performance ratios. The exact
source, reused field-core, input, output, runtime, executable, and verifier
hashes are in [analysis.json](analysis.json). The
[independent direct-overlap receipt](independent_direct.json) retains the
intersection dimension and rational hit count at each Frobenius power. The archived executables
identify the ones that produced the receipts; a fresh Apple Clang build
can have a different Mach-O UUID, while a fresh d10 build reproduced the
same forest and component bytes. The compiler was Apple Clang 17.0.0
(`arm64-apple-darwin25.6.0`), using `-O3 -std=c++20 -Wall -Wextra -Werror`;
the portable build additionally used `-U__ARM_FEATURE_CRYPTO`.

## A separate orbit-closure hypothesis

The same exact partition identifies a different policy worth testing. The
source has four `F_2`-rational points, none in its odd prime-order target
subgroup except infinity. Since the field Frobenius has prime order 131 on
`F_(2^131)` points, every nonidentity subgroup point has orbit length 131.
Sign folding does not shorten it: an odd-order Frobenius power cannot send
an odd-order point to its negative. Closing the *set* of W24 classes under
that action would
therefore contain exactly `131 * 8,391,166 = 1,099,242,746` signed classes,
or **2,198,485,492 geometric subgroup points**, a 130.97-fold expansion
over the original W24 base. It would still have 8,391,166 orbit
representatives. This set has not been materialized as a factor base, and
its membership, construction, PDP, matrix, and target costs are unknown.

For an optimistic collision-free count, this closed base has only
`0.00143025586` unordered four-summand multisets per nonidentity target,
so even its four-summand one-shot uniform support upper bound is below 1%.
The corresponding five-summand **formal** mean is about 628,879
multisets per target. That count does not establish natural yield: sums
can collide, an implicit solver may fail, and relations can be dependent.
It makes *implicit orbit-closed W24/m5* a sharper next experiment than
spending effort on the 0.025% quotient saving for unchanged W24/m6.

The next gate should encode a summand as a W24 seed plus a Frobenius
exponent, check that the resulting union-of-131-subspaces membership rule
can be solved and independently verified on planted controls, then freeze
held-out **ordinary** queries and compare verified novel rank per charged
query against W28/m5 and the original W24/m6 policy. It must charge every
failed attempt and all orbit-label, transport, matrix, and target costs.
Gray-code/FES sharing across exponent choices, SAT, and algebraic solvers
are alternative front ends to compare on the same frozen equations; a
solver-only improvement cannot establish IC advantage. The descendant-native
W24 policy has no free source Frobenius endomorphism: its proved endomorphism
order has conductor 263. An induced transported action is mathematically
available but its practical cost remains open.

## Replay

From the repository root, save the checked Sage runtime receipt before any
new Sage verification, unpack the frozen source mask stream to a fresh path,
then compile and run the two backends with the arguments documented below.
The committed `orbit.cpp` reuses the merged W24 field code via an include,
so both source hashes matter. The following commands independently replay
the result from the archived full native outputs; use fresh output paths:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /tmp/w24-orbit-runtime-replay.json
gzip -dc experiments/ecc2k130-263-w24-exact-base-20261005/runs/w24-b2048-r1/source-masks.bin.gz \
  > /tmp/w24-orbit-source-masks.bin
shasum -a 256 /tmp/w24-orbit-source-masks.bin
/Volumes/SSD990/cryptanalysis/sage -python experiments/ecc2k130-263-w24-orbit-columns-20261005/verify_sage.py \
  --dimension 24 --input /tmp/w24-orbit-source-masks.bin \
  --run-dir experiments/ecc2k130-263-w24-orbit-columns-20261005/runs/w24-native \
  --out /tmp/w24-orbit-verification-replay.json
python3 experiments/ecc2k130-263-w24-orbit-columns-20261005/analyze.py \
  --out /tmp/w24-orbit-analysis-replay.json
cmp /tmp/w24-orbit-analysis-replay.json \
  experiments/ecc2k130-263-w24-orbit-columns-20261005/analysis.json
```

The independent direct-overlap replay does not need Sage or the decompressed
mask stream:

```sh
python3 experiments/ecc2k130-263-w24-orbit-columns-20261005/independent_direct.py \
  --out /tmp/w24-orbit-independent-direct-replay.json
cmp /tmp/w24-orbit-independent-direct-replay.json \
  experiments/ecc2k130-263-w24-orbit-columns-20261005/independent_direct.json
```

To regenerate the producer files, build `orbit.cpp` with the stated flags
and run the executable with dimension `24`, expected count `8393232`,
batch size `2048`, wall limit `3600`, RSS limit `4294967296`, the
decompressed stream, and three fresh output paths for forest, nontrivial
components, and native receipt. The same interface accepts the pinned W10
control with dimension `10` and count `492`. Re-run `verify_sage.py` against
the generated outputs and compare their forest/component hashes with
`analysis.json`; elapsed time and peak RSS are host-dependent.

```sh
clang++ -O3 -std=c++20 -Wall -Wextra -Werror \
  experiments/ecc2k130-263-w24-orbit-columns-20261005/orbit.cpp \
  -o /tmp/w24-orbit-native
clang++ -O3 -std=c++20 -Wall -Wextra -Werror -U__ARM_FEATURE_CRYPTO \
  experiments/ecc2k130-263-w24-orbit-columns-20261005/orbit.cpp \
  -o /tmp/w24-orbit-portable
/tmp/w24-orbit-native 24 8393232 2048 3600 4294967296 \
  /tmp/w24-orbit-source-masks.bin /tmp/w24-orbit-forest.bin \
  /tmp/w24-orbit-components.bin /tmp/w24-orbit-native.json
```
