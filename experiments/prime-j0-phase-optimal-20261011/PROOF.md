# Minimum tau-squared class count at the minimum seed count

The radix-1024 quotient has 174,764 six-unit classes in 513 directed
cycles under multiplication by the norm-three endomorphism `tau`. A
minimum-norm representative of a class has capacity one, two, or three:
its `tau^j` image is an eligible full-window digit exactly when its norm
times `3^j` is at most `1024^2`. A seed's eligible images occupy
consecutive positions of one cycle. The nearest representative has at
least the capacity of any other representative of that class.

For a cycle with capacities `c_i`, let `s_i` indicate whether class `i`
is selected as a seed. Class `i` has an eligible provider precisely when

`s_i OR (s_(i-1) AND c_(i-1)>=2) OR (s_(i-2) AND c_(i-2)>=3)`.

An exponent-two image is **forced** precisely when the first two clauses
are false and the third is true. The independent verifier enumerates the
two initial seed bits and applies a two-bit-state dynamic program around
each cycle. Its lexicographic cost is `(sum s_i, forced exponent-two
classes)`. This searches every Boolean seed set, including covers with
overlapping images; the wraparound conditions are checked explicitly.
Across all 513 cycles the exact optimum is **(73,417 seeds, 27,932
exponent-two classes)**.

The constructor independently finds a cyclic tiling by eligible segments
of lengths one to three. It minimizes `(seeds, singleton segments, sum of
seed norms)` on each cycle. In a tiling, with `C` classes, `S` seeds,
`n_1` singleton segments and `E` length-three segments,
`E=C-2S+n_1`. The resulting plan has two singleton segments and
27,932 length-three segments, so it meets the unrestricted Boolean-DP
optimum. Its atlas assigns exactly one image to each class, and the
verifier checks the image and six-unit orbit of every class and all
1,048,576 residues.

The earlier 73,417-seed norm-priority cover has 31,165 exponent-two
classes. This cover removes **3,233** such assignments at the same
seed count and the same native table size. Full scalar multiplication
cost depends on which images co-occur on a scalar path; the frozen panel
and native replay measure that separately.
