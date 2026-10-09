# The numeric tau-comb row path maximizes the frozen pair-activity score

On 4,096 design scalars, the eleven numeric adjacent edges were exactly
the eleven highest-weight row pairs. Their design co-activity counts
range from **2,391 to 2,554** columns; the largest nonadjacent edge has
**1,880**. Thus the numeric path is the unique undirected eleven-edge
maximizer of the frozen pair-activity objective, with a gap of at least
511 when any adjacent edge is replaced by a nonadjacent edge. An exact
Held-Karp path search selected `(0,1,...,11)`.

The selected path therefore made exactly the same **21,029 fusions** as
the existing native path on the independent 4,096-scalar holdout, with
the same **1,060,497-unit point-operation proxy** and 45,034,704-byte
retained edge-table budget. The [frozen protocol](PATH_ORDER_PROTOCOL.md)
required at least 1% holdout proxy improvement for a native row-order
variant, so this candidate stops at the screen. The score optimizes
pairwise co-activity; it is not a proof that the numeric path maximizes
the nonlinear matching objective over every possible path.

| Panel | Scalars | Numeric fusions | Selected fusions | Numeric proxy | Selected proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Design seed `20261009211` | 4,096 | 20,954 | 20,954 | 1,060,316 | 1,060,316 |
| Holdout seed `20261009212` | 4,096 | 21,029 | 21,029 | 1,060,497 | 1,060,497 |

The screen obtained the nine-choice selected representative from the
frozen native path binary, reconstructed each width-six digit stream,
and checked its numeric-path fusion count against the native report
for every scalar. The complete-graph matching bound was 37,029
holdout fusions and an 884,497-unit proxy, but it would require
66 edge tables. These are operation-count comparisons, with no CPU
wall-time claim. The [receipt](path-order-screen-result.json) retains
the entire 12-by-12 design weight matrix, panel totals, per-scalar
delta histograms, input hashes, and source hashes.

| Artifact | SHA-256 |
| --- | --- |
| Screen receipt | `5e970cf1b84914e4964350f6151ff6504e2c130077d32608487f1cb8f7b36227` |
| Frozen native binary | `e8ffd24be7ea2c976b9ab8f31cea7d7d1cda0b6fbeb35b7e5b95ba2e1ae411aa` |
| Frozen protocol | `3aee887d99b27ab95b004ba826e50c469817df9260d907a8310a7b3001a0ce4d` |
| Screen source | `14b8ee7c1b3a564d1565b7922d45498bbf91fa7151b1319bdaa4122d7cc5b7d0` |

## Reproduce

```sh
cd experiments/prime-j0-secp256k1-native
PYTHONDONTWRITEBYTECODE=1 python3 path_order_screen.py \
  --binary /absolute/path/to/frozen/path/eisenstein_fixed \
  --output /absolute/path/to/new-screen-result.json
```
