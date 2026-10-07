# Held-out result: pair-aware τ recoding score

The opt-in implementation, tests, protocol, independent affine input
generator, and serial checker were committed in `23877cee`. The new
1,024-pair input bytes and expected output digests were committed
separately in `98d58cfd` before either held-out solver panel ran.
Release and UBSan each ran control, candidate, candidate, control on
`glv-j0-32` and `j0-56`. All 16 raw trials succeeded, matched the
frozen independent output digests, and passed per-output generic
scalar replay. The two builds agree exactly on all operation counters.
The input manifest SHA-256 is
`9f8f92911f705a40731a5741a7f9c5ed955790102d66fe94382c1b1cea2bfe14`.
The panel JSON retains the source, binary, and input hashes, stdout,
stderr, all trial outcomes, and online/replay intervals.

| Curve; 1,024 scalar pairs | Control nominal M | Candidate nominal M | M saved | Extra score positions |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 106,791 | 106,472 | 319 (0.299%) | 39,618 |
| `j0-56` | 243,299 | 242,890 | 409 (0.168%) | 88,088 |

Both arms used the same 1,104-byte prepared table, 4,084 recodings,
4,086 stream-pair scores, and 1,022 output inversions on each curve.
The candidate's extra scan chooses a different lattice representative
pair on some inputs, changing τ steps, additions, fused pairs, and
rotations. Its selected model score matches the aggregate evaluator
formula count on these held-out inputs. The small field-operation gain
is real under the frozen formula boundary, but the scorer traversal is
not included in that boundary.

The two-repeat local Release median `online_ms` values were
`1.0135` control versus `1.1190` candidate on `glv-j0-32`, and
`1.8700` versus `2.2845` on `j0-56`. UBSan medians were
`13.0250` versus `17.1795` and `20.4705` versus `25.0005`.
These timings are exploratory because the host lacks verified
exclusive CPU and NUMA isolation. Both machine records set
`cpu_speedup_claim: null` and `isolation_receipt: null`. They do not
establish a controlled slowdown or speedup.

Release passed all 16 CTest tests with warnings as errors; UBSan
`joint_tau` passed. This candidate passes correctness and the positive
nominal-M gate, but the saving is too small to justify routing its
extra scan into the one-target rho path on present evidence. It remains
an opt-in scalar-stage experiment. A cheaper way to select recodings
would be required before a full one-target rho and isolated-host gate.
Academic novelty of the combination is unestablished.
