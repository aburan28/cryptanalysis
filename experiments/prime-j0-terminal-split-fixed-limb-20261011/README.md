# Fixed-limb four-corner construction

The split-terminal secp256k1 evaluator can generate all four nearest-plane
lattice corners from two 512-bit reciprocal products and fixed-limb
multiply/add/subtract operations. Each corner uses one of the `(0,0)`,
`(1,0)`, `(0,1)`, or `(1,1)` offsets to the common cell floor. The existing
certified nearest-corner routine identifies the baseline for tie breaking.
This removes big-integer division from the four-corner generation path.

The focused release test passed on the frozen **4,096** scalars. The selected
digits and terminal pieces matched the certificate, all native outputs
matched the budget-optimal evaluator, and the first 128 matched its
independent binary point path. The result retained **67,108,816 bytes**,
reproduced **609,671** point-work proxy units, **54,528** nonzero terms,
and **1,280** split terminals. The [native patch](native.patch) applies to
the source-pinned split-terminal native crate; [materialize.py](materialize.py)
checks the parent tree and recreates the fixed-limb source. The
[materialization receipt](native-materialization.json) binds the exact
parent, patch, input, certificate, and resulting source hashes.

The run above establishes path and point correctness. Its wall time reflects
the contended macOS host and is not a controlled CPU comparison. The remaining
online work includes four full-window recodings and tie-breaking, whose cost
must be evaluated as part of complete scalar multiplication under the
[host-isolation gate](../../docs/ISOLATED_BENCHMARKS.md). The selector remains
a variable-time research path.

To rebuild, provide the split-terminal native parent with the hash in
[base-tree-sha256.txt](base-tree-sha256.txt):

```sh
python3 experiments/prime-j0-terminal-split-fixed-limb-20261011/materialize.py \
  --base-crate /absolute/path/to/split-terminal-native-crate \
  --output /absolute/path/to/fixed-limb-native-crate
```
