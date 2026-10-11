# Shared-corner split-terminal selector

The four-corner scalar evaluator already computes exact fixed-limb reciprocal
quotients and their fractional remainders. This revision derives the certified
baseline corner from those same remainders, eliminating a duplicate pair of
reciprocal products and a duplicate baseline representative construction.
The rare certificate fallback still delegates to the existing exact routine.
It constructs the `(0,0)` lattice corner with four 192-bit products, then
obtains `(1,0)`, `(0,1)`, and `(1,1)` by adding or subtracting the fixed basis
vectors in two's-complement limbs. The previous four-corner loop used sixteen
such products; its separate baseline construction used four more.

Candidate ranking now compares proxy, terminal-part count, and baseline flag
before constructing any big integers. When tied candidates have the same
representative, their norm and coordinates are identical, so the terminal
parts decide the rank directly. Different-representative ties keep the exact
original rank. The selected scalar path, table, and online timing boundary are
unchanged by this source transformation.

The focused release test compares all four incremental corners with the
independently computed direct four-product formula on the frozen 4,096-scalar
panel and the edge inputs `0`, `1`, and `2^256-1`. It also compares the shared
baseline with the original certified routine; it passed with raw output in
[corner-equivalence.log](corner-equivalence.log). The complete native selector
and point replay for this final patch is running as a separate check.

The [patch](native.patch) applies to the exact benchmark crate identified by
[base-tree-sha256.txt](base-tree-sha256.txt). [materialize.py](materialize.py)
recreates the source and [selector-materialization.json](selector-materialization.json)
binds the parent receipt, patch, materializer, and resulting source hashes.
The selector still needs a paired complete-operation timing run on a host that
passes the benchmark isolation gate before any CPU speedup can be reported.
