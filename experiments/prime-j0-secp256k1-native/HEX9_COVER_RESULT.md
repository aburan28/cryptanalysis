# Hexagonal four- and nine-representative tau comb

The [earlier tau-comb result](TAU6_COMB_RESULT.md) established the
equilateral geometry and `n/3` covering-radius bound for this
endomorphism lattice. This experiment uses that geometry for an exact
four-corner nearest-point rule and two cost-aware scalar selectors.
Replacing the original vector `U` by `W=U-2V` gives

`N(W) = N(V) = N(W+V) = n`,

where `N(a+b*tau)=a^2+3ab+3b^2` and `n` is the secp256k1 subgroup order.
This makes the nearest representative one of the **four floor/ceiling
corners** in `(W,V)` coordinates. `hex4` scores exactly those corners;
`hex9` scores the centered nine-position neighborhood that contains them.
Each evaluates the cheapest eligible width-six stream with the existing
1,024-point, 13-column comb and two-point terminal cover.

On a fresh 10,000-scalar panel, the complete point-evaluation proxy falls
from **3,251,425** for nearest-only to **3,183,751** for hex4 (2.08%) and
**3,153,236** for hex9 (3.02%). The 25-representative search scores
**3,130,172** on the same inputs. Hex4 and hex9 retain **55.81%** and
**80.98%** of cover25's point-proxy saving while recoding four and nine
representatives per scalar instead of 25. Integer lattice arithmetic,
recoding, and table lookup are charged by the native case timer but
excluded from this point proxy. A qualifying isolated-host run is needed
to determine the online CPU wall-time tradeoff.

## Four-corner selection rule

Let `c=(c_w,c_v)` be the exact real coordinates of the scalar in the
`(W,V)` basis, and let the residual after choosing a lattice point be
`r=xW+yV`. The Gram matrix is

`n * [[1, -1/2], [-1/2, 1]]`.

For a nearest lattice point, comparing it with its six neighbors
`+/-W`, `+/-V`, and `+/-(W+V)` gives

`|<r,W>| <= n/2`, `|<r,V>| <= n/2`, and
`|<r,W+V>| <= n/2`.

Writing `p=<r,W>` and `q=<r,V>`, inversion of the Gram matrix gives
`x=2*(p+(p+q))/(3*n)` and `y=2*(q+(p+q))/(3*n)`. Therefore
`|x|,|y| <= 2/3 < 1`. Each coordinate of a nearest lattice point is the
floor or ceiling of the corresponding coordinate of `c`. The rounded
`3-by-3` neighborhood contains all four corners. Both candidate sets
therefore contain an exact nearest representative eligible for the
162-position comb and terminal cover. Their chosen point proxies cannot
exceed the nearest-cover proxy; hex9's candidate set contains hex4's, so
its minimum proxy cannot exceed hex4's.

The candidate pair obeys `a+b*lambda_tau = k (mod n)` by construction.
The width-six digit expansion reconstructs that pair exactly. For the
nine-position search, each reduced-basis coordinate error has magnitude
at most `3/2`, so the starting norm is at most `27*n/4`; the existing
norm-decreasing recoder keeps its coordinates well inside signed 192-bit
range. This public-scalar implementation has input-dependent control flow.

## Frozen operation and correctness record

| Panel | Scalars | Nearest cover proxy | Hex4 proxy | Hex9 proxy | Cover25 proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Prior frozen cases | 214 | 64,336 | **62,757** | **62,310** | 61,962 |
| Fresh disjoint seed `2026100971` | 10,000 | 3,251,425 | **3,183,751** | **3,153,236** | 3,130,172 |

The independent Python screen checked the four-corner norm identity on
every frozen and fresh scalar. It verified **1,070 native point outputs**
from the two modes on 535 scalars
against independent secp256k1 multiplication, including the prior frozen
cases, the deliberate omitted-orbit case, the first 256 fresh cases, and
64 further cases that selected a terminal repair. The native release
suite passed **46 tests**. The frozen result is
[`hex9-cover-result.json`](hex9-cover-result.json), SHA-256
`34f241234dbc03ea484bfcacb6c8402138cfd129a314fb509257f65f5c6cad4e`.

`make_hex9_cover_isolated_manifest.py` prepares paired 129-case manifests
for cover1 versus hex4, cover1 versus hex9, hex9 versus hex4, and cover25
versus hex9, each with seven repetitions by default. All four manifests
passed structural validation, and their **516 distinct fixture commands**
returned the expected point and input fields. All modes use the same
binary, public scalars, expected points, and 1,024-point table. The online
timer includes scalar reduction,
representative construction, every candidate recoding, selection, point
evaluation, affine conversion, and expected-point assertion. The current
RunPod container fails the host isolation preflight, so the operation
record above remains separate from an online CPU speedup claim.

## Reproduce

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/Volumes/SSD990/crypto/target-hex9
cargo test --offline --locked --release --bin eisenstein_fixed
cargo build --offline --locked --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 hex9_cover_screen.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /Volumes/SSD990/crypto/new-hex9-result.json
```
