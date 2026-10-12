# Three-representative sparse tau comb

Choosing the least expensive of the three shortest equivalent Eisenstein
lattice representatives reduces the sparse 13-row tau-six comb's **point
evaluation proxy** from 3,251,525 to **3,195,339 field-product units** on a
disjoint 10,000-scalar secp256k1 panel. The same fixed-generator table retains
exactly **1,024 affine points**. On the frozen 128-scalar holdout, the point
proxy falls from 41,722 to **40,836** units. All **471** native replay points
match an independent secp256k1 multiplication.

## Algorithm and completeness

For scalar `k`, the existing lattice basis `U,V` gives 25 nearby pairs
`(a,b)` satisfying `a+b*lambda_tau = k (mod n)`. Sort these by Eisenstein
norm, then coefficient magnitude and coordinates. Recode the first three with
the frozen width-six digit atlas. A candidate is eligible only when its digit
stream fits 162 positions and the sparse top row has at most one digit. Score
its *complete* evaluation, including a row-zero fallback for an absent top
orbit, as `5*tau_steps + 11*mixed_additions`. Choose the lowest score, with
norm rank as the tie break, and evaluate only that stream.

The nearest lattice representative remains among the three and has the
proved `norm <= n/3` and 162-position span. Thus at least one candidate is
eligible for every scalar. Each pair is congruent to `k` modulo the subgroup
order; recoding reconstructs that pair exactly; the selected native
evaluation checks the resulting point. The selected point-operation score
cannot exceed the original sparse comb's score under this frozen cost model.
The selector is variable-time and intended for public scalars.

## Paired source record

| Panel | Scalars | Nearest representative | Three-representative selection | Non-nearest selected |
| --- | ---: | ---: | ---: | ---: |
| Frozen edges | 22 | 1,838 | 1,838 | 0 |
| Frozen design random | 64 | 20,776 | 20,292 | 33 |
| Frozen holdout random | 128 | 41,722 | **40,836** | 57 |
| Disjoint random, seed `2026100926` | 10,000 | 3,251,525 | **3,195,339** | 3,955 |

On the disjoint panel, rank zero wins 6,045 times, rank one 2,233 times,
and rank two 1,722 times. The three attempted representatives include one
eligible stream for 164 scalars, two for 1,796, and all three for 8,040.
The nearest-representative variant invoked its complete sparse fallback once;
selection found an eligible stored top orbit for that scalar. The point proxy
saves 56,186 units in total, or 5.6186 units per scalar.

This is a **point-evaluation** reduction. The selector computes two additional
digit streams, whose cost is outside this source proxy. The native case timer
includes that work, so promotion to an end-to-end speedup requires a paired
isolated-host receipt under
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).
The next measurement should compare the original sparse mode and the coset3
mode on the same frozen scalars, including scalar reduction, representative
search, all three recodings, point evaluation, affine output, and verification.
`make_tau6_comb13_coset_isolated_manifest.py` creates that paired manifest
from the 129-scalar fixture in the preceding PR. On a host satisfying the
strict preflight, invoke it with `--repo-root`, the native `--binary`,
`--cgroup`, `--cpus`, `--execution-cpu`, `--mem-node`, and `--output`, then
submit through `scripts/isolated_bench.py`. The manifest fixes seven
alternating-order repetitions by default and hashes every source artifact.

## Reproduction

The **43** release tests pass, including congruence, output equality, and
non-increasing point-proxy checks for boundary and fallback scalars. The saved
screen verifies 214 frozen scalars, the deliberate fallback scalar, and the
first 256 scalars from the disjoint panel against independent curve points.

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/private/tmp/prime-j0-comb13-target
TMPDIR=/private/tmp cargo test --offline --locked --release --bin eisenstein_fixed
TMPDIR=/private/tmp cargo build --offline --locked --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 tau6_comb13_coset_screen.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /private/tmp/new-comb13-coset-result.json
```

The frozen result SHA-256 is
`7e3500378075891a964f1d78a6bb0f1875a2f800c569f830994edf7210c39760`.
The native source SHA-256 is
`e2737a78d8a845b16031be87911f52363e9362af081f44327915db7d77c667f6`;
the release binary SHA-256 is
`56b8d728c9c002aa57f272517810d8b3cd49c4934cc1e0102bdefa3872f9be53`.
