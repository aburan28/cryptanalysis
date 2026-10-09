# N41 two-pair quadratic rank and cofactor audit

**Contribution.** An exact rank witness removes every mask-dependent Boolean equation of degree at most two in the declared 93-variable decoder family for the frozen N41 two-pair geometry. The remaining coordinate equations include a quadratic that holds on all 3,825,936 last-two-pair sums. Its apparent 49.6% rejection rate on general even-x curve points disappears under the DLP subgroup law: it rejected **zero of 3,167,136** admissible first-two-pair residuals for the public target. A subgroup-conditioned control has the same quadratic row space as the pair sums on the frozen samples.

## Exact instance and feature family

The field is \(\mathbf F_2[t]/(t^{41}+t^3+1)\), with elements encoded as 41-bit polynomial coefficients. The curve is \(y^2+xy=x^3+1\), of order \(4r\) for \(r=549756390943\). The public target is \(Q=(1458168294740,1672312028033)\). The frozen factor base contains **256 distinct usable points**, 64 in each rotation window 0, 10, 20, and 30. Each two-point domain has 1,956 unordered, distinct-column states. The effective signed/Frobenius relation columns are 26. The exact geometry and input points are in [screen.json](../n131_w18_four_pairs/screen.json) and [native_input.txt](../n131_w18_four_pairs/native_join/native_input.txt).

This is a point-decomposition stage experiment under proposal `Q20261008221400`; `candidate_id` and `run_id` remain null because no complete IC pipeline is specified or compared here. For domains 2 and 3, the 93 Boolean variables are 6 seed-sum bits from each pair, then bits 1–40 of \(x(U_2+U_3)\), then bits 0–40 of \(y(U_2+U_3)\). The full feature family is the constant, all 93 linear terms, and all 4,278 squarefree quadratic terms: 4,372 columns. The coordinate-only subfamily has 81 variables and 3,322 columns. The low bit of every pair-sum x-coordinate is zero and is excluded from both feature families.

## Rank result

The first 8,192 exact valid rows give full-feature rank **4,248/4,372** and coordinate-only rank **3,198/3,322**. Both nullities are 124. Since every coordinate-only equation embeds in the full feature space, equality of nullities proves that **every quadratic equation vanishing on those 8,192 rows has zero mask coefficients**. In particular, a universal equation in this feature family that could decode pair masks from a sum would also vanish on these rows, so this finite witness rules it out for the frozen domains.

An independent 8,192-combination pair holdout kept the coordinate rank at 3,198. A separate 8,192-point even-x curve control reached rank 3,199; the pair-plus-control union also has rank 3,199. The extracted 1,583-term equation spans the extra one-dimensional sample constraint. Doubling each general curve control gives 8,192 points in the order-\(r\) subgroup. This subgroup control has rank 3,198, and its union with the 16,384 pair rows remains rank 3,198. The union rank was computed from the 124-dimensional right nullspace: every subgroup row has zero quotient signature.

The first 8,192 full rows came from the previously frozen exact point-decomposition controls, whose scalar and group sums passed the installed-Sage replay recorded by that source experiment. The new pair holdout drew unique pair-index combinations uniformly from the two 1,956-state domains, excluding combinations already in the first sample. The curve control drew uniform 40-bit even-x candidates, retained those lifting to curve points, and chose one y branch uniformly. All ranks were independently repeated with reversed row order and low-pivot elimination in [verification.json](verification.json).

| Frozen check | Input count and law | Measured result |
| --- | ---: | ---: |
| Full mask and coordinate rank | 8,192 valid decomposition rows | 4,248/4,372 and 3,198/3,322 |
| Pair holdout | 8,192 new exact pair-index combinations | Combined coordinate rank 3,198 |
| General curve control | 8,192 retained even-x curve points | Rank 3,199; pair union 3,199 |
| Subgroup control | 8,192 doubled general controls | Rank 3,198; pair union 3,198 |
| Equation support | All \(1956^2=3825936\) D2×D3 combinations | Zero violations, identities, or odd-x outputs |
| General curve rejection | 8,192 even-x curve controls | 4,064 rejected; Wilson 95% interval 48.53%–50.69% |
| Target-dependent prefix scan | All 3,167,136 distinct-column D0×D1 prefixes for \(Q\) | **Zero equation rejections** |

The full-support equation check is [exhaustive_result.json](exhaustive_result.json), and the target scan is [prefix_result.json](prefix_result.json). The 3,167,136 prefix count agrees with the earlier [complete N41 census](../n131_two_pair_prefix_density_20261008/n41_census.json), which found 20 exact completion hits. The equation is stored as explicit monomial indices in [pair_relation.json](pair_relation.json). The independent Python audit re-evaluated every saved point, checked 256 freshly recomputed pair sums, and confirmed the rank values and curve-control rejection count.

## Why the quadratic gate has zero target yield

In this polynomial basis, the absolute trace of a field element is its low bit; all 41 basis traces were checked. For an even-x curve point \(P=(x,y)\), let \(\lambda=\operatorname{halftrace}(x)\), so \(\lambda^2+\lambda=x\). Set

\[
u^2=y+(\lambda+1)x,\qquad v=u(\lambda+u).
\]

The curve equation gives \(u^2(x+u^2)=1\), hence \(R=(u,v)\) is on the curve and \(2R=P\). Conversely, every doubled point has x-coordinate \(\mu^2+\mu\), so trace-zero x is exactly the two-divisibility condition. The two halves of \(P\) differ by \(T=(0,1)=2(1,0)\), which itself lies in \(2E\). Thus \(P\) is four-divisible exactly when \(R\) is two-divisible, giving

\[
P\in4E(\mathbf F_{2^{41}})
\quad\Longleftrightarrow\quad
\operatorname{Tr}\bigl(y+(\lambda+1)x\bigr)=0.
\]

The trace on the right is a quadratic Boolean function of the coordinate bits, because half-trace is linear. The two possible choices of \(\lambda\) give the same trace, since their difference changes the argument by \(x\) and \(\operatorname{Tr}(x)=0\). Here \(4E\) is the order-\(r\) subgroup. The extracted quadratic and this cofactor character agreed on all **24,576** saved pair and general-curve points. Scalar multiplication also checked the first 256 general controls, all 256 factor-base points, and \(Q\); [cofactor_result.json](cofactor_result.json) records those checks. The group-law proof explains the cofactor character; the direct prefix census establishes the extracted equation's zero rejection count for the frozen \(Q\).

## Reproduction and next experiment

The protocols and pre-execution source hashes are in `protocol*.json` and `freeze*.json` beside the code. The native checks compile with Apple clang 17.0.0, `-std=c++20 -O3 -march=armv8-a+crypto`; their source is [exhaustive.cpp](exhaustive.cpp) and [prefix_gate.cpp](prefix_gate.cpp). Run the saved Python stages with `PYTHONDONTWRITEBYTECODE=1 python3` and the matching `.py` file. The installed-Sage replay belongs to the frozen source rows; these new runs use standard Python and native C++ arithmetic. All wall times are unisolated stage diagnostics; the support and prefix counts, rank equalities, and scalar checks are the reproducible results. Failed Python and compiler invocations are retained as `analysis_attempt1.json`, `build_attempt*.json`, and `subgroup_attempt*.json`.

The next decoder screen should condition on the order-\(r\) subgroup **from its input law**, quotient out the 124 observed coordinate-only quadratic relations, and test a restricted degree-three mask–coordinate family on exact pair sums. A useful relation must involve mask variables and reject subgroup-valid residuals before the full pair combination is enumerated. Freeze the term family, independent subgroup controls, sampled pair indices, and rank or rejection gate before running it; then replay any surviving filter on every admissible prefix for the same public target.
