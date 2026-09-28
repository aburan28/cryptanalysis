# Additive amendment: count unordered five-summand tuples

The original `manifest.json` and protocol are immutable. The first frozen run
constructed exact projected n=83 bases of B=52 (l=6), B=4,054 (l=12), and
B=64,904 (l=16), checked against the previous controls and independent
subgroup samples. Their raw outputs, source hashes and timing are in `run-1/`.

The preregistered bound `(B+1)^m/(r-1)` counts ordered tuples. Since elliptic
curve addition is commutative, every permutation of a tuple has the same sum.
Therefore a *stronger, still only upper* bound on uniform nonidentity query
coverage is `min(1, C(B+1+m-1,m)/(r-1))`, allowing repeated points and a
possible cofactor-zero point. No independence or random-sum assumption enters.
For the measured l=16, B=64,904, m=5 base this is **0.003970514508**;
the ordered bound was 0.4763883392. Thus the l=16 base does not even clear
the *necessary* 1% coverage screen, despite the loose ordered test passing.
This correction is a mathematical inference from the frozen B, not a measured
relation yield. No solver or rank data are inferred.

`manifest-l17.json` adds one *new* case, n=83, l=17, before running it.
Source files and limits are unchanged: 120-second watchdog, 512 MiB address
space, a fresh output directory, and 64 deterministic independent subgroup
sample checks. It must preserve both manifests and all results. This case
tests whether an explicitly constructed bigger base makes the unordered
five-summand bound at least 1%. If yes, it permits a **subsequent** ordinary
relation/independent-rank experiment with a five-summand solver; it does not
establish one. If not, the bound rejects the base for this threshold.

The number of columns, base construction cost and solver equation size remain
material. A five-summand S6 descent is not implemented by this enumerator;
the existing PDP study reports S6 has 190,252 monomials before descent.
The final linear algebra and single-target DLP costs remain unknown.
