# Cached Jacobian seed orbit for a one-use τ scalar

Freeze this protocol and `cached_projective.py` before deriving 64 fresh
one-use secp256k1 base/scalar pairs. The control is the verified
inversionless endomorphism-assisted projective seed format. Both arms
use identical nine projective seeds, width-four digits, unit rotations,
and paired-τ steps. The candidate caches each seed's `Z²` and `Z³`
once if that seed participates in a general addition after the first
free insertion. All three unit-orbit images share the same `Z` cache.

Building one cache entry costs `1M+1S`. A generic Jacobian/Jacobian
addition costs `12M+4S`; using the cached powers for the second input
costs `11M+3S`. The candidate's net source-count saving per scalar is
therefore `(general_adds − cache_entries)M` and the same number of
squarings. Charge every cache entry, including a one-use entry; do not
charge the first insertion as an addition. All affine outputs must
independently match Sage, and the two arms must agree exactly. Save
the checked Sage runtime receipt before running, refuse overwrites,
and preserve complete inputs and source hashes.

This is a source-operation diagnostic for a public scalar. Cached
readdition is established prior art in the
[Explicit-Formulas Database](https://www.hyperelliptic.org/EFD/g1p/index.html),
which specifically describes reuse of `Z²` and `Z³`. No academic
novelty or CPU speedup is inferred. A native full operation and an
isolated host receipt remain required to make a timing claim.
