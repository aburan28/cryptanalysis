# Native split-terminal selector

The native secp256k1 evaluator now has a complete four-corner selector for
the frozen split-terminal scheme. It recodes each lattice representative
through the budget-optimal radix-1024 atlas, tries direct or two-entry
terminal representations, scores every admissible path, and evaluates the
chosen path with the existing XYZZ point buckets. The retained table remains
**67,108,816 bytes**, within the 64 MiB limit.

The focused release replay matched the frozen selected certificate on all
**4,096** scalars: 609,671 declared point-work proxy units, 54,528 nonzero
terms, and 1,280 split terminals. Every native output matched the existing
budget-optimal evaluator; the first 128 also matched its independent binary
point path. The [native receipt](native-targeted-check.json) binds the
executable, patched source, frozen input and certificate, raw log, compiler,
and materialization. [native.patch](native.patch) is the exact source delta
from the source-pinned budget-optimal crate, and [materialize.py](materialize.py)
recreates that crate from the recorded base-tree hash.

The prototype currently builds the four corners with big-integer division.
That choice preserves the frozen mathematics while making complete-operation
cost visible; a fixed-limb four-corner constructor is the next implementation
step. The point-work proxy excludes corner construction, extra recodings,
and lookups. The native run above is a correctness replay on an unisolated
host. Any CPU timing comparison requires the repository's
[isolation gate](../../docs/ISOLATED_BENCHMARKS.md). The selector is
variable-time and remains a research path for fixed-generator experiments.

To reconstruct the crate, provide an existing budget-optimal native crate
with the hash in [base-tree-sha256.txt](base-tree-sha256.txt):

```sh
python3 experiments/prime-j0-terminal-split-native-20261011/materialize.py \
  --base-crate /absolute/path/to/budget-optimal-native-crate \
  --output /absolute/path/to/new-split-terminal-crate
```

Build its focused test with `cargo test --release --bin eisenstein_fixed
split_terminal_selector_matches_frozen_panel_and_binary_points -- --nocapture`.
The collector in this directory records a hash-bound correctness log from
the resulting executable.
