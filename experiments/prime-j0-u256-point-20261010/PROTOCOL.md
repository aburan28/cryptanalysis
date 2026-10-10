# Four-limb Montgomery point backend for Eisenstein U14

Mode 126 keeps mode 125's unsigned 256-bit scalar reduction, certified
Voronoi representative, U14 widths, residue atlas, orbit IDs, and unit
codes. It changes the representation used for the online point sum. Before
the timed interval, each selected affine table point is converted from the
balanced Eisenstein field representation to a four-limb Montgomery field
element. The online accumulator uses four-limb Jacobian arithmetic; unit
codes act by multiplying its selected point's `x` coordinate by the fixed
cube root `beta` and, for the negative unit, negating `y`. The result is
inverted and formatted directly in that field representation.

For an Eisenstein coefficient pair `(a,b)` stored with radix `R128=2^128`,
the field value is `(a+b*beta)/R128 (mod p)`. The existing conversion
routine maps it to `(a+b*beta)*R256/R128 (mod p)` with `R256=2^256`, which
is its four-limb Montgomery encoding. It preserves field addition and
multiplication. The curve automorphism is `(x,y) -> (beta*x,y)` and negation
is `(x,y) -> (x,-y)`. The candidate applies the same mixed Jacobian group
law to those converted table points. Its scalar and point correctness is
therefore reducible to table conversion, unit action, and field group-law
checks, all of which are verified empirically below.

## Frozen validation gates

1. Commit this protocol before generating a disjoint 4,096-input unsigned
   256-bit holdout. Preserve prior input digests and failed checks.
2. Compare four-limb affine table conversion with the original field
   representation on all U14 nonidentity table slots, or record the exact
   subset and a separate algebraic proof for the unchecked slots. Verify
   both nontrivial unit images and negation on at least 512 selected slots.
3. Compare the four-limb Jacobian mixed-add and doubling formulas against
   independent Eisenstein group arithmetic on identities, equal/inverse
   pairs, and at least 512 deterministic nontrivial additions. Compare the
   complete mode-125 and mode-126 points and selected orbit/unit codes on
   all prior and new scalar panels. Replay at least 128 new points using an
   independent binary scalar multiplier. Verify all 129 frozen fixtures.
4. Bind source, inputs, release binary, raw test/fixture output and exits;
   cross-compile for x86-64 and submit physical x86 correctness through the
   existing serial queue. Record retained table bytes, preparation peak,
   and online field operation counts for both arms.
5. Pair verified online operations on the same scalars and resource limits.
   Report CPU wall-time improvement only after the host-level isolation and
   noise gates pass. Input decoding and reusable table construction remain
   outside both online timers and are reported separately.

The implementation is opt-in and handles public scalar research inputs.
Table indexing and the binary-GCD finalizer are input dependent.
