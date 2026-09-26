# Result: faster polynomial-basis scalar calls

The ratios below compare complete `CurvePb.mul` calls, charging scalar
recoding and all point operations. Each entry is a ratio of twelve paired
warm-call medians. Both phases used fresh processes and independent seeds;
every output matched the binary-loop parent and passed curve membership.

| Phase | Curve copy / degree | 4-bit control | 8 bits | 16 bits | 32 bits | 64 bits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Primary | Local polynomial / 11 | 0.996x | 1.381x | 1.734x | 1.674x | 1.934x |
| Primary | Tracked runner polynomial / 15 | 1.002x | 1.851x | 1.972x | 2.028x | 1.760x |
| Confirmation | Local polynomial / 15 | 1.002x | 1.976x | 1.848x | 1.691x | 1.618x |
| Confirmation | Tracked runner polynomial / 13 | 0.986x | 1.683x | 1.676x | 1.685x | 1.861x |

The eight accelerated cells in each phase have geometric mean gains of
1.781x and 1.751x. Separate first calls on independent field objects had
geometric mean gains of 1.742x and 1.724x. The 4-bit controls use the old
binary loop and stayed within 2% warm. Process peak RSS was 21.6–22.0 MiB,
within the declared 512 MiB cap.

The identity `tau² + tau + 2 = 0` was checked on the exact curve across
small even and odd binary fields. Exhaustive point and small-scalar
comparisons, 131-bit scalars, infinity, order-two points, and negative
scalars matched the parent on both code copies. With SAT dependencies in a
temporary directory, the broader runner suite passed 29 of 30 tests; the
last test could not load a fixed-parameter fixture absent from this
checkout. No source or test fixture was silently substituted.

The runner uses `CurvePb` on polynomial-basis fields without an optimal
normal basis. These results are scalar-call gains, not a complete IC
workload: no total with verified recovered logarithm and exclusive phase
accounting is asserted here.
