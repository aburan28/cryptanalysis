# Joint target equation rejects partial pair-output combinations; exact prefixes arrive too late

A sound binary-linear relaxation of **two still-variable exact pair outputs and their shared S3 output** rejects 58 of 64 independently sampled N131 W18 pair combinations with 32 low coordinate bits unresolved in each output. Both pair-local relaxations accept all 64 by construction. At 36 unresolved bits, all 64 pass the joint relaxation. The archived positive four-atom block passes at every tested width. An independent checked-Sage audit reproduces selected ranks, the positive, a rejected control, and a surviving false positive. The N41 S3 output is derived from the frozen public-point witness; the N131 output is a supplied constructed four-atom block coordinate, so this N131 panel measures component pruning rather than an ordinary public-point search.

The decisive generation check is exact: among the **65,868 fixed-seed W18 pair outputs** per rotation, the high 99-bit prefix at width 32 is unique for every output in both rotated domains. The high 95-bit prefix at width 36 is also unique. Thus a solver that obtains these prefixes by enumerating valid pair outputs has already selected each pair leaf before this gate can reject its combination. This experiment identifies a useful joint constraint for a symbolic solver, with a precise point where an explicit-prefix implementation loses its early-pruning advantage.

## Exact relaxation

For a pair with rotated source-reciprocal seed `s` and product `p`, its output `c=1/x` satisfies

`c²+s²+pc+p²c²=0`.

At fixed nonzero seed, `p=a²+sa` for one source-mask coordinate `a`. This map has kernel `{0,s}`, so its W6 or W18 image has dimension `d−1`. Choose a basis `b_j` of that exact product image. Write the proposed pair coordinate as `c=c₀+Σδ_i e_i`, with `k` coordinate bits `δ_i` still unknown. Expanding the pair equation and treating the products `δ_i p_j` as separate binary variables gives a sound linear relaxation. Any exact pair assignment satisfies it.

For two pair outputs `c,d` and a fixed sum-output reciprocal `z`, add the standard S3 equation

`z²+(cd)²z²+cdz+c²+d²=0`.

Expanding `c` and `d` in their unknown bits and treating each `δ_i γ_j` as another independent variable yields one joint `3n`-row binary system. These independent monomial variables enlarge the solution set, so augmented-rank inconsistency safely rejects an entire partial-output family. The implementation counts every introduced variable and reports matrix rank and consistency. It does not infer Boolean consistency of the monomials from a passing linear system.

## Frozen controls and measurements

The N41 source is `GF(2)[t]/(t^41+t³+1)` on `y²+xy=x³+1`, using the exact W6 rotations 20 and 30 and the known right-middle point from the frozen public-point witness. The [N41 panel](panel.json) samples 128 independent exact left/right pair IDs with replacement; its positive is inserted separately. The [N41 result](result.json) gives:

| Low bits unresolved per pair | Controls passing both pair-local tests | Controls passing the joint test | Positive |
| ---: | ---: | ---: | --- |
| 8 | 128 / 128 | 0 / 128 | pass |
| 10 | 128 / 128 | 16 / 128 | pass |
| 12 | 128 / 128 | 123 / 128 | pass |

The N131 source is `GF(2)[t]/(t^131+t^13+t²+t+1)` on the archived W18 fixed seed 13,686 at rotations 26 and 39. Its [first frozen panel](n131_panel.json) uses 24 independent exact pair-output combinations from the 65,868-row table plus the archived constructed positive. The [narrow](n131_result.json) and [wide](n131_wide_result.json) receipts place the transition near 32–36 unresolved bits. A separately frozen [128-row holdout](holdout_panel.json) reached its 120-second Python cap before a complete receipt; its [capped status](holdout_timeout.json) preserves that outcome. Before seeing any holdout decisions, a [64-row prefix](holdout64_panel.json) of those same frozen indices was selected for a new run.

| N131 low bits unresolved per pair | First panel joint passes | 64-row holdout joint passes | Joint rank across holdout | Positive |
| ---: | ---: | ---: | ---: | --- |
| 32 | 0 / 24 | 6 / 64 | 386–387 of 393 | pass |
| 36 | 24 / 24 | 64 / 64 | 392 of 393 | pass |

Every exact-pair control passes both pair-local tests at both widths. The [holdout receipt](holdout64_result.json) records each decision and a 70.683-second local elapsed interval for 64 two-width checks; this is an exploratory Python arithmetic cost. The [independent Sage audit](sage_audit.json) recomputes nine selected joint ranks using its own field arithmetic and `GF(2)` matrix elimination. It confirms that one width-32 survivor fails the exact S3 equation, as a sound relaxation permits. The [prefix census](prefix_result.json) independently scans all 65,868 output coordinates at both rotations and confirms one distinct high-bit prefix per output at widths 32 and 36. Its 49.757-second local Python interval is a setup diagnostic.

All measured runs used one process and the frozen 120-second/4-GiB panel envelope; the N131 128-row run is censored. The `candidate_id` remains `null`: these are target-coupled component tests on exact pair-output inputs. Their control rates describe that declared input law, not ordinary N131 relation yield or a single-target online speedup.

## Next algorithm gate

The joint equation contains target information that separate pair membership misses, but materializing a 99-bit prefix from either exact domain already identifies one of its 65,868 leaves. The next experiment should retain the `δ_i p_j` and `δ_i γ_j` products as coupled Boolean variables or derive an elimination that acts on **source-selector families before pair-output prefixes are fixed**. Test that propagation on the unpinned N41 public point, charge all rejected branches, and require a source-bound full N131 work and memory projection before another ordinary 600-second relation attempt.
