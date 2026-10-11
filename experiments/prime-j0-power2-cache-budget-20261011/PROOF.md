# Feasible seed-for-tau trade under a fixed table budget

For one tau cycle, each stored seed covers one, two, or three consecutive
unit classes. Let `n_j` be the number of selected segments of length `j`.
The class count `C`, seed count `S`, and exponent-two class count `E`
satisfy

`C=n1+2n2+3n3`, `S=n1+n2+n3`, and `E=n3`.

Therefore `E=C-2S+n1 >= C-2S`. This is a universal lower bound on
exponent-two classes for a given seed count under the declared
three-image cover policy.

Two adjacent length-three segments cover six consecutive classes and
use two seeds. Replacing them with three consecutive length-two
segments covers the same classes with three seeds. The transformation
changes `(S,E,n1)` by `(+1,-2,0)`, attaining the greatest possible
reduction of `E` per extra seed while keeping `n1` fixed. Every new
length-two segment is admissible: the exhaustive minimum-memory atlas
construction established `3N(d_v)<=1024^2` for every unit class `v`.

The deterministic screen finds at least 7,586 disjoint adjacent
length-three pairs. Selecting 4,096 uses exactly 4,096 additional full
seeds and removes 8,192 exponent-two classes. Starting from
`(S,E,n1)=(73,417,27,999,69)`, the result is
`(77,513,19,807,69)`. For `C=174,764`, the universal lower bound at
`S=77,513` is `19,738`; this construction is 69 classes above it,
exactly the retained singleton count.

There are twelve full-window rows. Each additional seed contributes
twelve 64-byte affine points and a four-byte atlas seed pair, hence
`12*64+4=772` retained bytes. The minimum-memory native table retains
61,829,108 bytes. After 4,096 transformations the projected retained
size is `61,829,108+4,096*772=64,991,220` bytes. The reported 64 MiB
cache capacity is 67,108,864 bytes, giving 2,117,644 bytes of nominal
headroom. This arithmetic describes a table-size boundary; the table's
runtime cache behavior remains an empirical question.
