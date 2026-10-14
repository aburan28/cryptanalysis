# Split-prime radix for fixed-base scalar multiplication

The new evaluator replaces the two-dimensional mixed-radix digit atlas with
21 signed integer digits in the Eisenstein base `pi = 86 - 21 tau`, where
`tau² = 3 tau - 3` and `N(pi) = 3301`. A single row of positive multiples
of `[pi^i]G` supplies each digit. Two short rows handle the final carry;
one stores `[m]pi^21 G` and the other stores `tau([m]pi^21 G)`. Thus the
online path needs at most 23 selected affine points and no tau evaluation.

In the quotient by `pi`, `tau = 1576 (mod 3301)`. For a coefficient pair
`a + b tau`, choose the centered integer residue
`d = (a + 1576 b) mod 3301` in `[-1650,1650]`, and put
`k = (a + 1576 b - d)/3301`. Exact division gives

```
a' = 23 k - 11 b
b' = 21 k - 10 b
a + b tau = d + (86 - 21 tau)(a' + b' tau).
```

Repeat this step 21 times. The final pair `(a_21,b_21)` contributes
`[a_21]pi^21 G + [b_21]tau(pi^21 G)`. The signed scalar decomposition
already used by the mixed-640 evaluator supplies the initial `(a,b)`;
the same point and 128-scalar frozen fixture are used for comparison.

The existing lattice basis has determinant equal to the secp256k1 subgroup
order. Its floor/ceil representative lies in one basis cell, yielding
`|a| <= |W_0|+|V_0|` and `|b| <= |W_1|+|V_1|`. Therefore the complex
magnitude of `a+b tau` is below
`M = 2252907023369138918423925520396307732351`, using `|tau|<2`.
Since `|pi|=sqrt(3301)>57` and `|d|<=1650`, the magnitude after 21 steps is
below `M/57^21 + 1650/56 < 331.023`. The quadratic norm
`a²+3ab+3b²` is at least `a²/4` and `3b²/4`, so both terminal coordinate
magnitudes are below 663. The native path checks this bound before each
terminal lookup. The table holds 21 rows of 1,651 entries and two terminal
rows of 664 entries: **35,999 points, 2,303,936 point bytes, no atlas**.

`split_prime_radix.py` checks every holdout recoding, exact reconstruction,
the lattice determinant, the numeric bound, and the table counts. On the
128-scalar fixture, 124 recodings use 23 nonzero point terms and four use
22; the largest observed terminal coordinates are 40 and 31. These are
fixture observations; the 663 table limit follows from the bound above.
`SplitPrimeRadix.lean` proves the quotient root and pi residue identities,
norm multiplicativity for `pi`, the exact division step, recursive
reconstruction, the two coordinate inequalities, and the group-action
evaluation formula. Its numeric lemma checks the final rational bound.
The analytic contraction and the floor/ceil lattice-cell inequalities are
written here and checked numerically by the model; their full Lean bridge
remains open.

`native_split_prime_bench.py` generates the pinned Rust evaluator and a
128-scalar correctness test against independent binary multiplication. The
release test passed locally and on the RunPod; the native table retained
2,304,336 bytes including metadata. The Pod's build and 128-scalar test
logs, binary hash, and command receipt are in
`tier1-runpod-20261013/split-prime-validation/`. Table construction is recorded as
preparation; the online timer includes recoding, signed lookup, mixed
additions, and affine recovery.

The case-0 grouped/split-prime comparison completed eight valid serial
pairs with median online ratio **1.2173** and paired bootstrap interval
**1.1697–1.4454**. All artifacts, binaries, and the runner stayed stable.
Median case-0 online times were 0.05037/0.04116 ms for grouped/split-prime;
median table preparation times were 5,403/9,568 ms respectively. These
preparation costs are recorded separately from the online interval.
The raw job is `tier1-runpod-20261013/e4ff7ae8cc93481e9c2c540d3b173f2a/`;
the transferred archive SHA-256 is
`4307c078a7300d1d9b5bb27ce24f0baff3d1bcc0249b9148a779c47d75b31f10`.
The Pod supplies instance-scoped Tier 1 evidence and records
`host_exclusivity_proved=false`. Eight additional frozen holdout scalars
completed as separate five-pair jobs in the same serial service: all 40
pairs and 80 timed invocations were valid, and all eight case medians were
above one. The median of case medians was **1.1796**; a 20,000-replicate
hierarchical bootstrap over cases and within-case pairs gave
**1.1351–1.2448**. Case medians ranged from 1.1288 to 1.2708. Raw jobs
and `split-prime-eight-panel.json` are under `tier1-runpod-20261013/`;
the transferred eight-job archive SHA-256 is
`4e3a2df6b475e237856a447356fb66073a1d4ae811768ea07625e26ef4d9a9d8`.
This panel supports the online direction across the frozen cases within
the instance-scoped measurement envelope.

This variable-index fixed-base evaluator is a
research benchmark path; use in a secret-scalar API would require a
constant-time selection design and a separate side-channel review.

Complex-radix scalar expansions in Eisenstein rings have prior literature,
including [Heuberger and Krenn, *Symmetric digit sets for elliptic curve
scalar multiplication without precomputation* (2014)](https://doi.org/10.1016/j.tcs.2014.06.010).
The contribution tested here is the split-prime, single-integer-digit
fixed-base table layout, its bounded terminal carry, and the matched native
implementation on this exact curve and workload.

## Near-real base variant

The optional `--linear` generator selects `pi = 56 + tau`, whose norm is
3307. The quotient relation becomes `tau = -56 (mod 3307)`. With centered
`d = (a - 56b) mod 3307` and `k = (a - 56b - d)/3307`, the exact update is
`(a',b') = (59k+b,-k)`. This uses a smaller coefficient in residue
construction and fewer signed-limb operations per digit. The same 21-step
bound gives terminal coordinates below 663 because
`2(M/57^21 + 1653/56) < 663`. Its 21 digit rows and two terminal rows
contain 36,062 points, or 2,307,968 point bytes. The local native release
test matched all 128 frozen points against independent binary multiplication
and reported 2,308,368 retained bytes including metadata. The norm,
residue, terminal numeric inequality, and exact quotient update are checked
in `SplitPrimeRadix.lean`.

The RunPod release build passed all 128 independent binary replay cases.
Its serial case-0 comparison against the original split-prime evaluator
completed eight valid pairs. The median original/near-real online ratio was
**0.9854**, with paired bootstrap interval **0.8894–1.0762**. The data do
not resolve an online advantage for either radix in this case. The raw
receipt is `tier1-runpod-20261013/775315ffa9b24cf5ab9715f2878383b6/`;
the transferred archive SHA-256 is
`030823cecb0cf226bba3ece12ce2788093b7547c6a62c81fadae8bd3f2a5fc05`.
The runner, binaries, and artifacts were stable. Host exclusivity was not
proved, so this remains an instance-scoped comparison.

## Fused terminal pair

The `--fused-terminal` generator replaces the two usual terminal point
additions with one lookup for terminal Eisenstein norm below `56²=3136`.
The nearest lattice choice satisfies `3N(z_0)≤n`; the digit contraction gives
`sqrt(N(z_21))≤sqrt(n/3)/57²¹+1650/56<56`. The strict numeric step follows
from `28²n<3·743²·57⁴²`, checked in `SplitPrimeRadix.lean`. The complete
analytic and lattice-cell bridge remains the same open Lean obligation as
the original coordinate bound. The runtime therefore retains both axis
rows and uses them whenever the terminal norm is at least 3136.

The fused table contains all 5,680 canonical pairs `(a,b)` with
`a²+3ab+3b²<3136` modulo sign, including identity. Contiguous `b` ranges
per nonnegative `a` give constant-time row indexing. With the original
fallback rows, the native retained size is **2,668,328 bytes**. Local
release testing matched all 128 frozen scalar points to independent binary
multiplication; all 128 took the fused path, with maximum terminal norm
1,861. The Pod release test also passed all 128 cases; its build, test, and
overlay logs, together with the near-real variant logs, are retained under
`tier1-runpod-20261013/split-prime-validation/`. Their transferred archive
SHA-256 is
`28654dc4b96346a238d68ef7958c6001d4b5c64291d2269cba2daa1b379590f1`.

The case-0 serial comparison against the original norm-3301 radix completed
eight valid pairs. Its median paired original/fused online ratio was
**1.1101**, with paired bootstrap interval **1.0012–1.1600**. The raw job
is `tier1-runpod-20261013/e2e0700e2f9a466dbd3243636687833c/`; the
transferred archive SHA-256 is
`eaf524ff4cf8852eb254cc8fe349b2363767febbcac99af111b47fa7e7361ffb`.
All 16 invocations returned independently verified points, and artifacts,
binaries, and runner stayed stable. The eight-case serial follow-up is
queued under the same instance-scoped service. Host exclusivity remains
unproved, so this timing result is exploratory.

## Twenty-digit norm-5113 variant

The `--short-fused` generator selects `pi = 70 + tau`, of prime norm 5113.
Its quotient root is `tau = -70 (mod 5113)`, and centered digit division is
`d = (a - 70b) mod 5113`, `k = (a - 70b - d)/5113`,
`(a',b') = (73k+b,-k)`. Twenty digit rows replace twenty-one, while the
same 5,680-entry canonical terminal-pair table handles `N(a_20,b_20)<56²`.
The nearest-cell norm bound and `|pi|>71` yield
`sqrt(N(z_20))<sqrt(n/3)/71²⁰+2556/70<56`; the final strict numeric
inequality is `35²n<3·682²·71⁴⁰`. The original cell coordinate bound also
gives terminal coordinate magnitudes below 499, so two 500-entry axis rows
remain as an exact fallback.

The 20 digit rows, fallback rows, and fused terminal table contain 57,820
point entries, or **3,700,480 point bytes**. The local native release test
matched all 128 frozen scalars against independent binary multiplication
and reported **3,701,336 retained bytes** including metadata. The exact
model in `split_prime_radix.py` found maximum fixture terminal norm 2,163;
126 cases used 21 nonzero point terms and two used 20. Norm scaling,
quotient root, exact digit division, and both numeric bounds are checked in
`SplitPrimeRadix.lean`; the analytic and nearest-cell Lean bridge remains
open. Online timing awaits a source-pinned serial Pod comparison.
