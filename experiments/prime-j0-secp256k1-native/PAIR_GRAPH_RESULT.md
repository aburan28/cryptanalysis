# Adaptive row-pair path for fixed-generator tau multiplication

An eleven-edge path of adjacent row-pair tables saved **3,172 mixed
additions** relative to the six-edge fixed pairing on a 2,048-scalar
holdout panel. The complete point-operation proxy fell from **565,841 to
530,949 field-product units (6.17%)**. The same selected Eisenstein
representative, tau map count, and output point were retained. The
additional five edge tables increased retained compact slots from
24,564,384 to **45,034,704 bytes**. These are operation and storage
results; controlled online CPU timing awaits an isolated host.

## Method

For each tau-comb column, consider the 12 ordinary rows as a path with
edges `(0,1),...,(10,11)`. Walk from row zero upward, fusing two adjacent
active digits when possible and skipping both rows. This gives a maximum
matching on every active interval of the path. Every edge uses the
same sixfold common-unit quotient as the parent pair table: 81 first
digit orbits, 81 second digit orbits, and six relative units. The native
implementation reuses the six even-edge tables and builds five additional
odd-edge tables. It keeps the thirteenth sparse row and its exact repair.

The per-column path matching needs only row-activity tests and no general
graph solver. The computation is variable time and intended for public
scalars. The [frozen protocol](PAIR_GRAPH_PROTOCOL.md) specified both
fresh input panels, the holdout gate, correctness checks, and the 45 MiB
table cap before the screen.

## Frozen screen and native replay

| Panel | Scalars | Six-edge fusions | Path fusions | Six-edge proxy | Path proxy | Proxy reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Design seed `20261009161` | 2,048 | 7,387 | 10,589 | 564,611 | 529,389 | 6.24% |
| Holdout seed `20261009162` | 2,048 | 7,227 | 10,399 | 565,841 | 530,949 | **6.17%** |

The complete-graph matching upper bound on the holdout uses 18,462
fusions and a 442,256-unit proxy, but its 66 edge tables would require
270,208,224 retained slot bytes. It is a bound, not an implemented mode.
The path never had fewer fusions than the fixed pairing on any screened
scalar. The [screen receipt](pair-graph-screen-result.json) records the
active-row distribution and per-scalar count digests.

The native evaluator passed all **49 release tests**, including direct
pair-sum comparisons for the five new edge tables. The
[differential verifier](pair_graph_verify.py) checked **4,444 scalars**:
five boundaries, 214 frozen cases, 129 benchmark fixtures, and the two
fresh panels. Every affine point, selected representative, tau count,
top repair, and predicted fusion count matched. An independent Python
secp256k1 multiplier checked 261 boundary and fresh points, and all 129
fixture points matched their recorded expected coordinates. The
[verification receipt](pair-graph-verify-result.json) retains panel totals.

An explicit preparation run reported 433,026 compact table entries and
45,034,704 retained slot bytes. Its local macOS ARM64 preparation interval
was 7,045.470 ms and child peak resident memory was 213,221,376 bytes.
This interval is fixed-generator setup outside the online scalar timer;
the local host does not satisfy the CPU isolation gate.

| Artifact | SHA-256 |
| --- | --- |
| Frozen screen | `a395d1aaca0e1d670f3b711f5ecf6a65e56ae4b96f8ed685f55f3f3831d22424` |
| Native replay | `5c01f2c599a69f396c23fdf142f65cda7c7f2f9e29e26099b52d46288a219e05` |
| Candidate source | `036f504580933c0959d87e89975b4f69bb14bcdd275d41b49755fe614826e1b0` |
| Candidate release binary | `e8ffd24be7ea2c976b9ab8f31cea7d7d1cda0b6fbeb35b7e5b95ba2e1ae411aa` |
| Six-edge reference binary | `2b2def850cc37cb06815590e1b7921fb3d7debe5453d64287c84341e76fcb18b` |

## Next checks

The paired 129-fixture, seven-repeat online panel still needs a host that
passes [`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).
That run must charge matching decisions, compact decoding, all nine
candidate recodings, point evaluation, affine output, and expected-point
verification. It must retain the raw failures and setup resources. A
prior-work review of multi-table comb and joint precomputation is still
needed before a priority claim for this specific schedule.

## Reproduce

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/absolute/path/to/path-build
cargo test --offline --locked --release --bin eisenstein_fixed
cargo build --offline --locked --release --bin eisenstein_fixed
"$CARGO_TARGET_DIR/release/eisenstein_fixed" --prepare-w6-comb13-hex9-path
PYTHONDONTWRITEBYTECODE=1 python3 pair_graph_verify.py \
  --reference /absolute/path/to/six-edge/eisenstein_fixed \
  --candidate "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /absolute/path/to/new-verification.json
```
