# Exact tau-squared optimum under a 64 MiB table budget

The radix-1024 secp256k1 fixed-generator cover has 174,764 six-unit
classes in 513 cycles under the norm-three endomorphism `tau`. A full-window
seed contributes up to three classes, through `tau^0`, `tau^1`, and `tau^2`.
The native layout stores twelve 64-byte affine points and four atlas bytes
per additional full-window seed, or **772 payload bytes**. Its aligned
`DR20` atlas also has up to four bytes of end padding. Starting from the
independently replayed 73,417-seed layout at 59,032,928 retained bytes,
the payload bound admits at most

`floor((67,108,864 - 59,032,928) / 772) = 10,461`

more seeds. The actual native layout counts an eight-byte-aligned atlas:

`T(S) = 64(12S + 9,288) + round_up_8(16 + 8(174,764) + 4S) + 362,440`.

It gives `T(83,878) = 67,108,816` bytes and
`T(83,879) = 67,109,592` bytes, so **83,878** is the exact maximum
seed count in this layout. The constructor's payload-only projection is
67,108,820 bytes; the four-byte difference is atlas padding removed at
this seed count. The native point replay confirms the exact size.

Two `tau` cycles each contain one class, represented by residues `0` and
`512`. They each consume a seed but can contribute only one distinct
class, regardless of which of the three map powers is used. Every other
seed can contribute at most two classes without a `tau^2` image. For any
cover in this format with `S` seeds and `E` classes assigned a `tau^2`
image, this gives

`174,764 - E <= 2(S-2) + 2 = 2S-2`, hence
`E >= 174,764 - 2S + 2`.

At `S <= 83,878`, the lower bound is **7,010** `tau^2` classes. It applies
to overlapping covers as well as disjoint tilings and does not assume a
particular selector or seed placement.

The construction starts with a minimum-seed cyclic tiling having 73,417
seeds, two singleton segments and 27,932 length-three segments. A
two-state dynamic program retiles each cycle among tilings with the same
minimum seed and singleton counts, prioritizing adjacent length-three
segments. The serialized plan contains **11,634 disjoint adjacent pairs**
when scanned in cycle order; 11,707 are available if the cycle boundary is
also used. Replacing 10,461 of the linear pairs by

`3+3 -> 2+2+2`

adds exactly 10,461 seeds and removes exactly 20,922 `tau^2` assignments.
Every new length-two segment is eligible: its seed has norm at most
`1024^2/3`, checked at construction and independently at verification.
The resulting segment counts are `(n1,n2,n3)=(2,76,866,7,010)`, so the
construction attains the lower bound exactly.

The [independent verifier](verify.py) rebuilds the six-unit quotient,
`tau` cycles, minimum-norm representatives and minimum-seed optimum using
separate arithmetic code. It checks every class assignment and all
1,048,576 residues. The [native atlas verifier](verify_native_atlas.py)
checks the separate `DR20` representation and inverse unit transforms for
the same full residue space. Both checks bind the serialized cover and
atlas by SHA-256 receipts.
