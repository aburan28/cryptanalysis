# Cross-block product translations have a sharp W18 support cost

An exact XOR-correlation census measures the source lost when corresponding pairs in the two constrained four-atom blocks differ by one of a small set of source-mask translations. Allowing all translations `u=1,…,31` leaves an N131 W18 six-pair **uniform-target tuple mean upper ceiling of 7.687867** before remaining column exclusions. If the first free pair is selected independently of the target, at least **2,242,676,351 distinct prefixes** are needed for a one-half union-bound ceiling. A 600-second query would have at most **0.26754 microseconds per prefix** for *all* target-dependent work. Narrower sets of 7 or 15 translations require still more prefixes. This source gate rejects the proposed small cross-block product-translation policy as a practical target-independent prefix method at W18.

The exact field is `GF(2)[t]/(t^131+t^13+t²+t+1)` on `y²+xy=x³+1`, curve `EC1N131Ckb1heb5f1998f20b`, with prime subgroup order `680564733841876926932320129493409985129`. The audited W18 source has **B=1,575,684** subgroup-usable points before folding, **K=131,068** folded columns, and **N=34,482,792,912** signed distinct-column pair states across all nonzero mask-XOR seeds. The N41 control uses `GF(2)[t]/(t^41+t³+1)`, the same curve model, `B=384`, `K=26`, and `N=1,956` signed pair states per rotation. Its source export checks all six original rotation blocks and both signs of every source mask.

## Exact translation identity and count

For an unordered source pair `(w,w+s)`, set `p=w(w+s)`. Translate its two masks by `u` in the corresponding pair slot of the other block. The new product is

`p'=(w+u)(w+s+u)=p+u²+su`.

Thus a small source-mask translation set gives an exact small product-offset set for each seed `s`. This experiment requires the two constrained blocks to use the **same nonzero seed** and aligns both pair slots by independently chosen translations from `U_k={1,…,k}` for `k=7,15,31`. The translations apply before the known Frobenius rotations. Source support and distinct columns inside each translated edge are enforced; collisions between different edges and the two free pairs are relaxed, making the count an upper ceiling.

For a fixed `u`, the source indicator `T_u(w)` is one when both `w` and `w+u` are rational supported masks with different folded columns. Its XOR autocorrelation is `C_u(s)=Σ_w T_u(w)T_u(w+s)`. For `s≠u`, `C_u(s)/2` counts unordered mask quartets before cross-edge column checks; `s=u` would reuse the same masks and is omitted. Each quartet has 16 signed leaf choices, so the upper signed linked-pair count is `L_s(k)=8Σ_(1≤u≤k, u≠s) C_u(s)`. The two aligned pair slots contribute `E_k=Σ_s L_s(k)²`. With two free pair slots, the six-pair tuple ceiling is `N²E_k`, its uniform-target mean upper is `N²E_k/r`, and the first-pair prefix floor is `ceil(r/(2NE_k))`.

| Source | Translation cap | Mean upper before remaining column checks | First-pair `q₅₀` floor | Necessary 600-second average per prefix |
| --- | ---: | ---: | ---: | ---: |
| N41 W6 | 7 | 20.324361 | 49 | 12.245 s |
| N41 W6 | 15 | 73.187652 | 14 | 42.857 s |
| N41 W6 | 31 | 348.122376 | 3 | 200 s |
| N131 W18 | 7 | 0.391923 | 43,991,806,702 | 0.01364 µs |
| N131 W18 | 15 | 1.804577 | 9,554,261,367 | 0.06280 µs |
| N131 W18 | 31 | **7.687867** | **2,242,676,351** | **0.26754 µs** |

The [frozen producer protocol](protocol.json) binds both support sources, the native executable and code, the exact indicator and sign law, one worker, a 120-second cap per field, and 4 GiB RSS. The [census](census.cpp) uses an integer Walsh transform to compute every seed's autocorrelation without enumerating source-pair cross products. Its N41 and N131 runs completed in **0.440** and **1.741** local seconds with respective peak process RSS **1,507,328** and **15,220,736** bytes; these are arithmetic diagnostics from an unisolated host. The [summary](summary.json) retains exact integers and high-precision ratios for every row above.

The [independent audit](audit.json) directly enumerated all 63 N41 seeds and eight selected N131 seeds against every translation `1,…,31`, matched the Walsh outputs at all three caps, recomputed each big-integer `E_k` and prefix floor, and checked the field product identity on supported, four-column-distinct witnesses in both fields. This validates the combinatorial ceiling; it is not an ordinary relation-yield measurement on the fixed public point. The N41 mean shows the restriction remains testable as a correctness control, but its W18 prefix floor fails the stated 600-second source gate before a solver is built.

The next target-conditioned design must retain substantially more W18 product support and use the public-point S3 links to reject incompatible product families during search. Selecting a small product-offset set before seeing the target spends too much of the source density. A target-derived translation choice could change the conditional law, but would need its own complete proposal and rejection accounting. This configuration remains a design proposal with `candidate_id: null`.
