# Hexagonal four-corner reduction and nine-representative tau comb

The endomorphism lattice has an exact equilateral basis. Replacing its
original vector `U` by `W=U-2V` gives

`N(W) = N(V) = N(W+V) = n`,

where `N(a+b*tau)=a^2+3ab+3b^2` and `n` is the secp256k1 subgroup order.
This makes the nearest representative one of the **four floor/ceiling
corners** in `(W,V)` coordinates. The new scalar mode scores the nine
positions centered on the rounded coordinates, including those four,
then evaluates the cheapest eligible width-six stream with the existing
1,024-point, 13-column comb and two-point terminal cover.

On a fresh 10,000-scalar panel, hex9 reduced the complete point-evaluation
proxy from **3,253,019 to 3,153,335 field-product units (3.06%)**. The
25-representative search scored **3,130,220** on the same inputs. Thus hex9
retained **81.18%** of that search's point-proxy saving while recoding nine
representatives per scalar instead of 25. The nine-representative search,
integer lattice arithmetic, and table lookup are charged by the native case
timer, but excluded from this point proxy. A qualifying isolated-host run is
needed to determine the online CPU wall-time tradeoff.

## Four-corner theorem

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
`3-by-3` neighborhood contains all four corners, so its minimum norm
equals the exact nearest norm. The existing nearest representative is
eligible for the 162-position comb and terminal cover. Consequently hex9
always has an eligible stream, and its chosen point proxy cannot exceed
that nearest-cover proxy.

The candidate pair obeys `a+b*lambda_tau = k (mod n)` by construction.
The width-six digit expansion reconstructs that pair exactly. For the
nine-position search, each reduced-basis coordinate error has magnitude
at most `3/2`, so the starting norm is at most `27*n/4`; the existing
norm-decreasing recoder keeps its coordinates well inside signed 192-bit
range. This public-scalar implementation has input-dependent control flow.

## Frozen operation and correctness record

| Panel | Scalars | Nearest cover proxy | Hex9 proxy | Cover25 proxy |
| --- | ---: | ---: | ---: | ---: |
| Prior frozen cases | 214 | 64,336 | **62,310** | 61,962 |
| Fresh disjoint seed `2026100961` | 10,000 | 3,253,019 | **3,153,335** | 3,130,220 |

The independent Python screen checked the four-corner norm identity on
every frozen and fresh scalar. It verified **535 native point outputs**
against independent secp256k1 multiplication, including the prior frozen
cases, the deliberate omitted-orbit case, the first 256 fresh cases, and
64 further cases that selected a terminal repair. The native release
suite passed **46 tests**. The frozen result is
[`hex9-cover-result.json`](hex9-cover-result.json), SHA-256
`8e6dcc44647577b0bb086c352b818a9405596f804f43a5f93e4a03d72eea9a30`.

`make_hex9_cover_isolated_manifest.py` prepares paired 129-case manifests
against either the nearest cover or cover25, each with seven repetitions
by default. Both modes use the same binary, public scalars, expected
points, and 1,024-point table. The online timer includes scalar reduction,
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
