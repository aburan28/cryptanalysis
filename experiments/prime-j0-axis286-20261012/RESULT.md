# Fourteen-window radix-286 axis scalar format

The radix-286 format uses fourteen ordinary windows and two terminal axes for the same certified secp256k1 Eisenstein representative as the radix-152 control. It reconstructs every scalar covered by that representative bound. Its exact table objective has 217,609 point entries, including 13,634 ordinary orbit representatives per window, 16,040 first-axis entries, and 10,693 second-axis entries. The point payload is 13,926,976 bytes at 64 bytes per point.

The exact integer search finds radix 286 as the unique minimum of this fourteen-window, six-unit quotient and two-axis point-entry objective. Radix 285 is next at 217,622 entries. The proof map in [PROOF.md](PROOF.md) distinguishes the checked Lean reconstruction and axis theorems from the still-open Lean bridge for the global entry minimum. [search.json](search.json) retains the finite census; [PROTOCOL.md](PROTOCOL.md) gives the monotonic tail argument.

## Frozen correctness replay

The native builder, holdout generator, verifier, and Lean source freeze is commit `3fc826979e53f357017b1462d30a58bf4c24b525`. Only after that commit, [holdout.py](holdout.py) drew 512 distinct scalars disjoint from the prior design and control panels. [holdout.json](holdout.json) has SHA-256 `51d245dad559dc7089402d425358bdd79a9202b45b576f13553eceaa90c26026`. Both the new panel and the earlier 512-case control panel pass complete-point comparison against the radix-152 evaluator and independently generated binary-multiplication points on macOS ARM64 and Linux ARM64. [replay.json](replay.json) retains source, fixture, and output digests; [local-build.json](local-build.json) and [linux-build.json](linux-build.json) identify the two native builds.

| Panel | Cases | Radix-286 noninitial additions | Radix-152 noninitial additions | Radix-286 unit rotations | Radix-152 unit rotations | Radix-286 retained bytes | Radix-152 retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Earlier control | 512 | 7,680 | 8,704 | 1,022 | 1,024 | 14,309,128 | 4,568,960 |
| New frozen panel | 512 | 7,680 | 8,704 | 1,024 | 1,024 | 14,309,128 | 4,568,960 |

The candidate uses 1,024 fewer noninitial additions per 512 scalar calls (11.76% in this operation count), at roughly 3.13 times the retained table and atlas memory. The frozen 4,096-scalar design panel selected 65,536 total terms for radix 286 versus 73,726 for radix 152. These are exact operation and storage diagnostics; the CPU wall-time comparison remains open until a qualifying isolation receipt exists. Table construction stays outside the online scalar-call boundary.

## Verification and next measurement

`check.py --write` built the theorem modules under pinned Lean 4.34.1 and recorded `#print axioms` in [lean-build.txt](lean-build.txt). The checked theorems cover fourteen-step reconstruction, subgroup congruence, the terminal norm cap, unique sector image, and axis factorization. The global point-entry minimum has an exact integer census and written tail proof; formalization remains partial at its Burnside count, monotonic-tail, and finite-census bridge.

The Linux ARM64 replay used the pinned `rust:1.93.1-bookworm` image and a disposable overlay. It returned `axis286_matches_axis152_and_independent_points` for both panels. A paired online CPU experiment should charge complete recoding, lookup, point arithmetic, and affine recovery for each variant, use the same frozen scalar panel and resource envelope, and retain the runner's isolation preflight and raw noise counters. Until that experiment passes the host gate, `online_speedup` is unknown.
