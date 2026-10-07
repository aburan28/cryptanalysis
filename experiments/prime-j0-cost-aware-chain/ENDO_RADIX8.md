# Endomorphism-folded signed radix-256 table

This public-scalar experiment changes the prepared-point format for a point
reused across many scalar multiplications. The exact Eisenstein lattice
reducer returns `a,b` with `k = a + bτ (mod r)`. Since `τ = 1−ω`, set
`x=a+b` and `y=−b`, giving `k = x + yω (mod r)`. Recode both short signed
coordinates in balanced radix 256. For each window position `i`, prepare
only `[d·256^i]P` for positive magnitudes `d=1..128`. A negative digit
negates that point; a digit in the `y` coordinate applies the cheap
order-three automorphism `ω(P)=(βX,Y)` to the **same** point. Add the
nonzero actions into one Jacobian accumulator and normalize its output.

The 25-bit study subgroup uses three positions (384 points); the 56-bit
subgroup uses four (512 points). The capacity is checked after recoding and
an oversized coordinate falls back to the generic multiplier. A preparation
verifier independently recomputes every table point. The implementation is
variable-time and intended for public scalars. This is a fixed-base batch
throughput study, not a one-target rho result.

The [design](endo-radix8-design.json) was frozen in commit `70b9a374`
before generating the [new fixture](endo-radix8-inputs/inputs.json). The
fixture contains 32,768 scalars across eight cases and excludes all scalars
from seven earlier fixtures. An independent Python model checked every
coefficient identity and 184 elliptic-curve point outputs. The native
[release panel](endo-radix8-native-panel.json) replays each case in rotating
order through radix, the conventional nine-column comb, and the scattered
τ atlas. Every native arm independently verifies all 4,096 results against
the generic multiplier; the three output digests match in all eight cases.
There were no fallbacks. The warnings-as-errors UBSan suite passed 2,311,868
checks, and its [24-arm panel](endo-radix8-ubsan-panel.json) also passed.

The table compares the four held-out cases per curve. The operation score is
the study's predeclared `16·mixed additions + 8·doublings + unit rotations`;
it is an algorithm diagnostic, not a CPU timing result.

| Curve | Mode | Point slots | Prep additions / doublings | Online additions / doublings / rotations | Score |
| --- | --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | signed radix | 384 | 381 / 16 | 63,104 / 0 / 31,342 | 1,041,006 |
| `glv-j0-32` | comb9 | 512 | 502 / 24 | 48,961 / 32,679 / 0 | 1,044,808 |
| `glv-j0-32` | scatter atlas | 2,494 | 2,418 / 0 | 44,147 / 0 / 29,518 | 735,870 |
| `j0-56` | signed radix | 512 | 508 / 24 | 128,298 / 0 / 64,186 | 2,116,954 |
| `j0-56` | comb9 | 512 | 502 / 56 | 114,175 / 98,201 / 0 | 2,612,408 |
| `j0-56` | scatter atlas | 4,802 | 4,669 / 0 | 93,458 / 0 / 62,828 | 1,558,156 |

The radix table occupies 12,288 or 16,384 point bytes, versus 16,384 for
comb and 79,808 or 153,664 for the scatter atlas. Radix's score is 0.36%
below comb on the smaller subgroup and 18.97% below it on the larger one.
The scatter atlas has the lowest operation score, but its per-scalar action
search and much larger table make score alone inadequate for CPU ranking.
The local macOS timing fields in both panels are exploratory; none supports
a controlled speedup claim.

[`make_endo_radix8_isolated_manifest.py`](make_endo_radix8_isolated_manifest.py)
binds the fresh scalar files, code and binary hashes, independent output
digests, and three alternating-order repetitions to the serial isolated
service. Its default comparison is radix against comb; it also accepts
`--reference-mode tau3-scatter-atlas-pos`. Build the binary on a qualifying
Linux host and substitute that host's CPU, NUMA, cgroup, and absolute paths.
The manifest passes local schema validation, while the macOS preflight
correctly rejects host isolation certification. A Linux host receipt is
required before interpreting any wall-time ratio.

GLV decomposition, signed windows, fixed-base precomputation, and
endomorphism-assisted scalar multiplication have substantial prior art; see
the [GLV/GLS fixed-base study](https://www.microsoft.com/en-us/research/publication/efficient-and-secure-algorithms-for-glv-based-scalar-multiplication-and-their-implementation-on-glv-gls-curves-extended-version/)
and the [fixed-base comb discussion](https://eprint.iacr.org/2004/342.pdf).
The contribution tested here is this specific table budget and replay in
this codebase. No academic novelty claim is made.
