# Direct-limb scalar intake for Eisenstein U14 multiplication

This candidate uses the mode-124 binary-GCD finalizer and U14 point
path, but removes arbitrary-precision scalar reduction and diagnostic
coordinate conversion from the online path for a canonical 256-bit
encoded scalar. The input loader decodes the scalar before timing, as
it does for the parent. Mode 125 receives four input limbs directly.

The secp256k1 subgroup order `n` is above `2^255`. Therefore any
unsigned 256-bit input `k` satisfies `0<=k<2^256<2n`. Its residue is
`k` if `k<n` and `k-n` otherwise: one four-limb comparison and at most
one subtraction. The certified Voronoi selector then consumes those
limbs without a BigInt round trip. Its exact tie/ambiguity fallback
retains the parent selector and is charged to the online interval.
Signed or wider inputs use the existing arbitrary-precision scalar path
and remain valid. The candidate's primary input law is uniformly
sampled unsigned 256-bit scalars reduced by the rule above.

The direct path returns a projective point and compact source counters;
it does not construct BigInt lattice coordinates after the point work.
Both paired modes load the same fixture before the online clock, and
both timers start with target-dependent scalar reduction and end after
the expected affine point has been independently checked. Record any
input conversion in preparation or a supplementary encoded-input
interval; it is not silently included in only one arm.

## Frozen gates

1. Commit this protocol before generating a new disjoint 4,096-scalar
   holdout. Preserve every prior input digest and all failures.
2. Compare four-limb and BigInt residues on boundaries `0,n-1,n,2^256-1`
   and at least 512 deterministic 256-bit inputs. Compare certified
   representative coordinates, corner certificates, and fallback
   status on the same inputs.
3. Compare complete mode-124 and mode-125 outputs, addition counts, and
   table payloads on all boundary, prior-panel, and new holdout cases.
   Replay at least 128 new points independently. Check signed/wider
   fallback inputs, all 129 frozen fixture points, and the full native
   release suite.
4. Bind source, input, binary, raw output, exits, and x86 compilation.
   Use a paired isolated host and its strict noise gates before
   reporting a CPU wall-time improvement.
