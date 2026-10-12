# Voronoi-clipped fixed-base scalar table

The secp256k1 radix-256 fixed-base table now uses **174,883 point entries**:
15 ordinary windows with 10,924 entries each and an 11,023-entry direct
terminal table. The prior direct-terminal format uses 177,174 entries.
The native opt-in evaluator retains 11,505,936 bytes and passed its
65,536-residue atlas audit. It retains the same fifteen digit recodes and
at most sixteen selected points per scalar.

The exact construction and proof map are in [PROOF.md](PROOF.md). The
`search.json` census gives 66,133 admissible terminal pairs; `screen.json`
checks 4,096 design scalars and 1,536 scalars from three frozen holdout
panels, including representative geometry and direct row addresses. The
native development replay compares 512 independent secp256k1 points with
the radix-286 reference and gets identical points, 7,679 selected additions
against 7,680, and 11,505,936 retained bytes against 14,309,128. These
addition counts describe that particular panel, not a wall-time speedup.

`native_overlay_hex.py` builds a disposable opt-in binary from the pinned
main-tree native source. `replay.py` checks binary/source hashes, compares
native points against independent fixtures, and keeps raw panel hashes.
A source-frozen fresh holdout and independent Linux replay are the next
correctness gates. Controlled CPU time remains pending a host that passes
the isolated benchmark preflight.
