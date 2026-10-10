# Q20261010123500: fixed-anchor four-sum rank-work bound

The input law is one uniform nonidentity point `Q` of the declared prime
subgroup. Before `Q` is drawn, fix the complete schedule of left-pair
queries. Each complete fixed-output S3 scan may test at most `h` signed left
subgroup sums, with `h ∈ {1,2,8}`. The right pair uses two points from the
same exact factor base; repetitions and duplicate rows are allowed in the
count to make the bound optimistic. All `K` independent factor-base log rows
must come from these scans. The schedule may correlate its left sums, and a
scan may return every right-pair representation. It cannot select a new left
sum after seeing `Q` or earlier target-dependent results.

For actual usable base size `B`, the number of unordered right-point pairs
including repeats is `M=B(B+1)/2`. Each of the `hM` signed-left/right-pair
combinations equals the uniform nonidentity `Q` with probability at most
`1/(r−1)`. Across `S` complete scans, expected relation representations are
at most `ShM/(r−1)`. Novel rank is no larger than representations. Markov's
inequality therefore gives

```text
Pr(rank >= K) <= S h M / [K (r−1)].
S_95 >= ceil(19 K (r−1) / [20 h M]).
```

Every complete scan visits `D=B/2` rational raw-`x` coordinates for these
exact bases. Thus its necessary root visits are `S_95 D`. All four base
receipts independently establish `D=nK`, because each signed-Frobenius
column has `n` rational raw coordinates and both point signs are counted in
`B`. For large `B`, the product approaches `0.95(r−1)/(2hn)` and is nearly
independent of the weight cutoff. The exact integer calculation uses the
actual `B` and `K`, not this asymptotic expression.

Profiles are the exact Q1301 N53 W≤3, Q1325 N83 W≤5, and Q1413 N131 W≤5
and W≤6 bases. Keep their distinct curve IDs, field representations,
enumerated-set digests, cofactor policies, and actual `B`/`K` values. The
N131 pair is a controlled weight-cutoff comparison on the same curve. All
profiles have `isogeny: "none"` (`ISO0`), `candidate_id: null`, and `run_id:
null`. The two N53/N83 curves are separate comparisons, not matched targets.

Freeze this protocol, calculator, independent integer auditor, exact base
receipts, N131 curve protocol, and the Q20261010120000 measured N83 root
kernel receipt before calculating. The calculator reports root-visit units
as a **conditional necessary count**, and field-multiplication counts only
as an extrapolation at the measured N83 source ratio. Report h values
separately; `h=8` is a conservative branch allowance, not a measured
branch count. Do not turn this uniform-target theorem into a statement
about the fixed published point or a target-adaptive left generator. It
does not supply a complete IC cold or one-target online work exponent.
