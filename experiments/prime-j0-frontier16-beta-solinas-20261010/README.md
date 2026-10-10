# Solinas cube-root rotation for the compact tau table

Mode 155 keeps the 64-byte affine points, the proved sixteen-window tau
recoding, and the direct XYZZ bucket merge of mode 154. It computes the two
nontrivial cube-root x rotations with the fixed three-fold reduction in
`PROOF.md`. The retained table plus atlas is **8,336,528 bytes**; the new
three-word canonical constant array adds 96 bytes, for **8,336,624 bytes**
charged to mode 155.

The source and input law are frozen before drawing a disjoint 4,096-scalar
panel. Independent affine binary multiplication constructs expected points.
The candidate and five controls are replayed on that panel, ten boundary
cases, and 129 fixed cases. A temporary counter build records how many unit
rotations use the new reducer and the matched source-level product counts;
its patch and raw log are kept beside the result. The shipping source has
no counters.

On the new 4,096-scalar panel, mode 155 selected a nontrivial cube-root unit
43,743 times. Both compact modes used 65,536 nonidentity digit terms, 86,016
point-kernel field additions, and 135,168 squares. Mode 155 used 532,480
generic Montgomery multiplications plus 43,743 Solinas constant products;
mode 154 used 576,223 generic Montgomery multiplications. Counting the
executed source-loop products in `PROOF.md` gives **25,041,417** for mode 155
and **25,610,076** for mode 154, a reduction of **568,659**. The two-X
sixteen-window and seventeen-window controls used 24,035,328 and 25,509,168
source-loop products respectively on the same panel. `verify_ops.py` binds
these counts to the frozen source, temporary patch, raw log, and input hash.

The restored-source release suite passed **129 tests**. The standalone field
test covers 65,540 input words under each nontrivial unit, with 1,024 words
also checked against independent big-integer multiplication. All six replay
modes matched independently computed points for the new 4,096-scalar panel,
ten boundary cases, and 129 fixed cases. The rebuilt release binary hash
matches the binary recorded by the replay.

The resulting operation counts and retained bytes are algorithmic
measurements. CPU wall-time comparisons require a passing host-level
isolation receipt as specified in `docs/ISOLATED_BENCHMARKS.md`.
