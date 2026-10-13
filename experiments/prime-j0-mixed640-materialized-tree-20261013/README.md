# Pre-tau materialized mixed-radix tree

Moving the degree-three endomorphism into selected table entries lets the
fourteen-window mixed-radix 640 recoder use one absolute-gauge tree. On the
frozen 4,096-scalar panel, this changes the source-formula model from
552,976 to **516,096** field-kernel calls, saving 36,880 calls (nine per
scalar on average). The 64-case affine replay in `model.py` independently
checks the resulting points against binary scalar multiplication. This is
an operation model and correctness experiment; complete-operation timing is
still open.

The prior mixed-radix atlas emits `(seed, exponent, unit)` with exponent in
`{0,1}`. For each window and seed that occurs with exponent 1, prepare the
point `tau(seed)` once. The lookup selects either `seed` or `tau(seed)`, then
applies the unit and inserts the point into the single tree. The identity

`tau(sum(unit_i(seed_i))) = sum(unit_i(tau(seed_i)))`

uses tau's group-homomorphism law and commutation with the six unit actions.
`TauMaterialization.lean` proves this implication for arbitrary point lists
under exactly those hypotheses. The proof does not yet instantiate the
secp256k1 point type or the Rust field arithmetic; this bridge remains a
formalization obligation. The pinned Lean receipt records the actual build
and `#print axioms` output. The native evaluator for this combined candidate
has not yet been built, so the current model must not be called a measured
speedup.

| Format | Distinct point slots | 96-byte point and atlas bytes | Modeled calls, 4,096 scalars |
| --- | ---: | ---: | ---: |
| Two tau buckets, compressed orbit | 415,190 | 44,588,220 | 552,976 |
| One tree with pre-tau entries | 808,296 | 82,326,396 | 516,096 |

The second table has 393,106 extra pre-tau entries, only for seed IDs actually
used at exponent 1. Its additional point payload is 37,738,176 bytes. The
table builder can form these entries from `tau(base)` for each window, using
the same seed multiples as the ordinary table; this needs one tau transform
per window base and a second table-building pass, rather than a tau transform
for every seed. Both passes and the compressed-orbit x preparation belong to
cold setup accounting. The
model charges 6/10/14 calls for affine/one-affine/projective tree joins, 14
for the two-bucket final projective join, and 6 multiplies plus 3 squares for
the old project's runtime tau map. It accounts for the four rare cases with
one leaf in the tau bucket. It excludes table construction, recoding,
affine recovery, memory traffic, and host wall time. The extra table can lose
on cache traffic despite its arithmetic saving.

The next gate is a native source overlay that materializes both compressed
orbits, replays unseen points, and instruments the actual join and tau calls.
Compare the full operation on a host that passes the repository's isolated
benchmark preflight before making a CPU speed claim.

Reproduce the current receipts:

```sh
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/model.py
(cd experiments/prime-j0-mixed640-materialized-tree-20261013 && lean TauMaterialization.lean)
```
