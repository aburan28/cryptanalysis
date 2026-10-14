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
The later six-unit variant has a checked 21-step norm contraction in
`SplitPrimeNormBound.lean` for digits of norm at most 1,064². The
floor/ceil lattice-cell bound for the actual minimum-norm selector is
checked separately in `SplitPrimeLatticeCell.lean`.

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
Before the successful fused build, two unmeasured housekeeping commands
failed: pinning to CPUs `0-7` was rejected by the Pod's affinity mask, and
a later `taskset` invocation could not resolve `cargo` on its command path.
The recorded successful build used allowed housekeeping CPUs and the
absolute `/root/.cargo/bin/cargo` launcher. Neither failure entered a
timed benchmark job.

The case-0 serial comparison against the original norm-3301 radix completed
eight valid pairs. Its median paired original/fused online ratio was
**1.1101**, with paired bootstrap interval **1.0012–1.1600**. The raw job
is `tier1-runpod-20261013/e2e0700e2f9a466dbd3243636687833c/`; the
transferred archive SHA-256 is
`eaf524ff4cf8852eb254cc8fe349b2363767febbcac99af111b47fa7e7361ffb`.
All 16 invocations returned independently verified points, and artifacts,
binaries, and runner stayed stable. The eight-case serial follow-up also
completed: 40 valid pairs and 80 valid invocations, with every case median
above one. The median of case medians was **1.1102**, and a 20,000-replicate
hierarchical bootstrap over cases and their five pairs gave
**1.0272–1.1913**. The case medians ranged from 1.0205 to 1.1913. Raw jobs
and `fused-prime-eight-panel.json` are under `tier1-runpod-20261013/`;
the transferred eight-job archive SHA-256 is
`3c6e46ca83a658693ce223d0b4af21f8a38c5242c1c00ae88b789c1aa58b3e00`.
`summarize_split_prime_panel.py` replays the aggregate from the raw case
jobs and rejects invalid runs or changed binaries, artifacts, or runner.
Host exclusivity remains unproved, so these timing results are exploratory.

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
open. The Pod release test also passed all 128 frozen points. Its build,
test, overlay, and manifest logs are under
`tier1-runpod-20261013/split-prime-validation/`; the transferred validation
archive SHA-256 is
`f17f693a13d3f7345daeda14eb9313a8934f7faa960e242ad60a644db14c9189`.

The source-pinned case-0 comparison against the 21-digit norm-3301 fused
evaluator completed eight valid pairs. The median paired 21-digit/20-digit
online ratio was **0.9096**, with paired bootstrap interval
**0.8530–1.0348**. Median online times by arm were 0.03604/0.03840 ms;
median table preparation was 9,907/14,140 ms, measured separately.
The raw job is `tier1-runpod-20261013/39b4b17a2f71421893bb9f9920794b22/`;
the transferred archive SHA-256 is
`4682b937f5d97dcd7fc942b770adb3a83093d62d6dac86878c2c13ab071850e3`.
All 16 invocations returned verified points, and artifacts, binaries, and
runner stayed stable. This case gives no measured advantage for the shorter
radix; host exclusivity was unproved.

## Six-unit quotient compression

The `--unit-fused` generator retains the norm-3301 base and groups its
3,300 nonzero quotient residues into 550 orbits under the six Eisenstein
units. Zero adds one seed. For each residue, the model records a canonical
positive integer seed `m` and a unit code. The largest chosen `m` is 1,064;
all six images preserve norm `m²`. Each of the 21 digit rows consequently
stores 551 orbit seeds rather than 1,651 signed-integer entries.

The native orbit point stores the three cube-root images of `x` and one
`y`, so unit selection uses an indexed coordinate and optional sign change
after lookup. Its digit rows hold 11,571 entries of 128 bytes each. Keeping
the established fused terminal table and exact axis fallback gives
**1,929,600 point payload bytes** before lookup arrays and metadata, versus
2,667,456 point payload bytes in the fused signed-integer variant. The
residue lookup identifies the seed, unit, digit-coordinate adjustment,
and quotient adjustment; digit division uses one signed small radix
division per step.

`split_prime_radix.py` exhaustively covers all 3,301 residues, checks the
maximum seed, pins the lookup digest, and reconstructs all 128 frozen
scalar representatives. Every fixture recoding uses 22 nonzero point terms;
the maximum observed terminal norm is 1,201. The uniform digit norm bound
1,064² improves the written terminal estimate to
`sqrt(N(z_21))<sqrt(n/3)/57²¹+1064/56<46`. The runtime retains the
conservative 56-norm fused table and 663-coordinate fallback while this
variant is tested. `SplitPrimeRadix.lean` proves norm preservation under
the unit action, exact division for an arbitrary unit digit, and the
numeric 46-norm and coordinate inequalities. The generated
`SplitPrimeNormBound.lean` proves the Eisenstein norm triangle bound and
strict per-digit contraction for exact division by `86-21 tau`:
`N(z)≤B²`, `N(d)≤D²`, and `(B+D)²<3301 R²` imply `N((z-d)/pi)<R²`.
Its polynomial Cauchy identity and axiom audit are pinned in
`split-prime-norm-bound-lean-receipt.json`. Its Lean theorem
`terminal_bound_from_cell` composes all 21 exact quotient steps and the
digit norm bound, with the nearest-cell inequality `3N(z₀)≤n` stated as
an explicit hypothesis. The checked integer radius sequence starts at
`B₀=27·57²¹` and ends at `B₂₁=46`; each step is strict against the exact
norm multiplier 3301, so the theorem concludes `N(z₂₁)<46²`.
`SplitPrimeLatticeCell.selected_norm_bound` closes the initial premise
for every integer scalar. It proves the four-corner covering inequality,
the exact secp256k1 basis Gram and determinant identities, the floor
quotient/remainder equations, and the norm bound inherited by the
minimum-norm selector. Its source and axiom audit are in
`split-prime-lattice-cell-lean-receipt.json`. The Python selector orders
the same four candidates by norm first, then by its documented tie breaks.
`SplitPrimeComplete.min_norm_scalar_terminal_bound` imports and composes
the lattice and contraction modules. It applies to any 21-step trajectory
whose initial norm equals the four-corner minimum, every step is the exact
`pi` quotient equation, and every chosen unit digit has norm at most
1,064². The Python selector's tie breaks preserve that minimum norm.
The imported theorem's source and axiom audit are in
`split-prime-complete-lean-receipt.json`.
The generated
`SplitPrimeUnitCover.lean` proves the complete finite quotient bound:
for every `0 ≤ r < 3301`, there is a seed `m ≤ 1064` whose image under one
of the six explicit unit multipliers is `r`. Its 24 bounded certificate
chunks use kernel-checked `decide`; the theorem's axiom audit lists only
Lean's standard `propext` and `Quot.sound`. Regenerate it with
`python3 generate_split_prime_unit_cover.py --write` and check it with
`lean SplitPrimeUnitCover.lean`; the
[Lean receipt](split-prime-unit-cover-lean-receipt.json) pins the source and
output. `SplitPrimeRadix.unit_seed_residue_forms` identifies those six
numeric multipliers with the actual coefficient images of the unit action.
`SplitPrimeCanonicalSeeds.canonical_count` proves that the explicit
minimum-orbit predicate selects exactly 550 positive seeds;
`canonical_last` proves that the last is 1,064. Both pass with no axioms in
the [canonical Lean receipt](split-prime-canonical-lean-receipt.json). The
generated `SplitPrimeCanonicalCover.all_residues_covered_by_table`
strengthens the coverage statement to the **actual canonical seed set**:
every residue has an image of zero or a member of the 550-item `seeds`
list. Its 67 finite slices cover all 3,301 residues and pass kernel
checking with only `propext` and `Quot.sound`. Regenerate with
`python3 generate_split_prime_canonical_cover.py --write`; the
[canonical cover receipt](split-prime-canonical-cover-lean-receipt.json)
pins the generated source, generator, dependency, and axiom audit. The
imported `SplitPrimeDigitChoice.bounded_unit_step` then proves that every
integer coefficient pair admits a canonical-table seed, a six-unit code,
and an exact next quotient pair with digit norm at most 1,064². The
[digit-choice receipt](split-prime-digit-choice-lean-receipt.json) pins
the source, imports, and `#print axioms` output.
`SplitPrimeComplete.canonical_scheme_terminal_bound` composes 21 such
choices with the lattice selector and proves `N(z₂₁)<46²` for every
integer scalar. Its witness selector uses standard `Classical.choice` in
Lean; it is a mathematical existence proof. The native evaluator instead
uses the generated packed residue lookup. The Python model checks equality
of the canonical and runtime greedy seed lists and all 3,301 lookup
residues, while a direct Lean theorem about the packed runtime bytes
remains to be added.
The
model checks that this canonical list exactly equals the runtime's greedy
551-entry list including zero and pins its digest. Direct kernel replay of
the runtime seen-residue loop was stopped at a local resource ceiling; its
[attempt receipt](split-prime-greedy-attempt.json) preserves that status.
The nearest-cell bound is checked in `SplitPrimeLatticeCell.lean`; the
runtime greedy seed-list equivalence remains a model-checked bridge.
The generated native release test matched all 128 frozen points against
independent binary multiplication locally and reported **1,950,422
retained bytes** including the residue lookup and metadata. The Pod
release test also passed all 128 points. Its build, test, overlay, and
manifest logs are under `tier1-runpod-20261013/split-prime-validation/`;
the transferred validation archive SHA-256 is
`e5beee1c5f69b54562784dec342439d306102716f69ebc3a8ac60a155e6846cf`.

The serial case-0 comparison against the signed-integer fused evaluator
completed eight valid pairs. The median signed/unit online ratio was
**0.8837**, with paired bootstrap interval **0.8444–0.9614**. Median
online times by arm were 0.03495/0.03887 ms. Median reusable table
preparation was 9,127/3,541 ms, recorded separately; the compressed
table was also 26.9% smaller in retained bytes. The raw job is
`tier1-runpod-20261013/42ed4fdbb9274b308cd559eb00b2dfae/`;
the transferred archive SHA-256 is
`f1e9db151c6a2f1bd9810fcac04bd04b54ce5df653417d9f8bacfa6525c8fdc0`.
All invocations returned verified points, and artifacts, binaries, and
runner stayed stable. This format improves preparation and memory under
the recorded instance-scoped envelope while increasing case-0 online time.

The follow-up `--unit-packed` form moves the digit's two small coordinate
corrections past the large signed-limb multiplications. Exhaustive quotient
screening puts the corrections in `[-20,43]` and `[-7,28]`; seed index, unit
code, and both corrections fit in one 32-bit residue word. This replaces
three separate residue arrays with one. `split_prime_radix.py` pins the
packed lookup digest and checks every decoded field; the Lean declaration
`unit_packed_correction_identity` proves that the rewritten quotient step
is identical for arbitrary coefficients. The generated native release test
matched all 128 frozen points against independent binary multiplication
locally and on the Pod, and reported **1,943,788 retained bytes**. Its Pod
build, test, overlay, and manifest logs are under
`tier1-runpod-20261013/split-prime-validation/`; the transferred validation
archive SHA-256 is
`b6f2ef1c27e50aaf0a0e470621fa41a68944847ef76cc6c0fcf1a9ab543ca1f1`.

The direct serial case-0 comparison with the first unit format completed
eight valid pairs. Median first-unit/packed online ratio was **1.1425**,
with paired bootstrap interval **0.8683–1.2299**. Median online times by
arm were 0.03822/0.03483 ms. The raw job is
`tier1-runpod-20261013/ec98874e4794472892f64d0e567c7d95/`.
The separate direct comparison with the signed-integer fused evaluator
also completed eight valid pairs: median signed/packed ratio **0.9164**,
paired interval **0.7774–1.0291**, and median online times
0.03349/0.03638 ms. Its raw job is
`tier1-runpod-20261013/7b7180a0e92a4a9dae3d4a643e5bd8f6/`.
Both jobs returned verified points with stable artifacts, binaries, and
runner. The transferred two-job archive SHA-256 is
`465f2b137a519c12737873c08b81f50d0d8a036546cc3fede552d2ab5d7e2bc7`.
Packing improved the unit format on this case but did not establish an
online advantage over the signed-integer fused evaluator.

The `--unit-packed-tight` follow-up uses the checked 46-norm terminal bound
directly. Its canonical terminal table has 3,838 points instead of 5,680;
the exact axis fallback is limited to coordinate magnitude 642 instead of
663. Local native release testing matched all 128 independent binary
points and reported **1,823,132 retained bytes**. Its online effect is
measured as a separate arm against the packed and signed-integer formats.

The `--unit-split-table` format factors each canonical seed as
`m = (m mod 32) + 32 floor(m/32)`. The bound `m ≤ 1064` makes the two
indices at most 31 and 33. At each of the 21 radix positions it stores 32
low multiples and 34 high multiples, each with the same six-unit orbit
representation as the packed format. Table preparation builds the low and
high point chains directly from `P` and `32P`, so it does not materialize
all 1,056 intermediate multiples. The residue word now carries the
11-bit seed itself, so the online evaluator applies the unit action to
each nonzero component and adds at most two mixed points per digit. The
Lean declaration `split_seed_reconstruct` checks the exact decomposition
and both index bounds; the group step follows by distributivity of scalar
multiplication and the unit endomorphism over point addition.

The generated release implementation passed the 128-point frozen holdout,
including an independent binary multiplication for every point, with
**519,452 retained bytes**. This is 71.5% less retained memory than the
packed tight table. The 1,386 digit points occupy 177,408 bytes; the
terminal and fallback tables and lookup account for the rest. On the same
128 scalar representatives the split requires a median of 19 additional
mixed additions per scalar (range 14–21) relative to the one-point-per-digit
packed table. The [model receipt](split-prime-radix.json) records the full
distribution and the [local correctness receipt](split-table-local-validation.json)
records the generator, compiled source, fixture, and test hashes. That local
build used compile-only placeholders for 31 unavailable, unrelated atlas
includes in this sparse checkout; the selected scalar test did not read
them. A clean source-pinned Pod build and serial online comparison are
needed to place this memory format on the measured time/memory frontier.

The generated `split_prime_packed_lookup_exhaustive` test now decodes all
3,301 residue words in both packed layouts. For each word it checks the
minimum-orbit seed, six-unit image, digit norm, and packed quotient
corrections, then replays nine signed coefficient inputs through the
actual Rust step function: **29,709 exact quotient cases per layout**.
Each layout also passed the 128-scalar independent binary replay in a
separate Cargo target directory. The ordinary packed and split layouts
reported 1,823,132 and 519,452 retained bytes respectively. The
[native lookup receipt](packed-lut-validation.json) pins the generated and
compiled sources, binaries, raw logs, and temporary include shims. It
also preserves an earlier shared-target run that loaded the wrong layout;
that run is excluded from these results.

The `--unit-split-terminal-orbit` format folds the terminal norm ball under
the same six Eisenstein units used by the digit table. The exact ball
`N(a+bτ) < 46²` contains 7,675 coefficient pairs: zero and 1,279 nonzero
six-unit orbits. The earlier sign-canonical terminal table held 3,838
points. The new table holds 1,280 representatives as two-x affine records
and a 3,838-word index/unit map. The two-x record derives the third cube-root
x image with field additions, so terminal recovery still uses one mixed
point addition. Its retained table size is **404,392 bytes**, 115,060 bytes
(22.15%) below the split-seed format, with the same 21 radix steps.

The [terminal orbit receipt](terminal-orbit-validation.json) records a release
build with its own Cargo target directory, all 3,838 direct terminal-point
comparisons, all 3,301 packed residue words and 29,709 exact quotient cases,
and the 128-scalar independent binary replay. The 31 temporary include shims
only satisfy unrelated atlas includes absent from this sparse checkout; the
compiled source hash and shim manifest hash are recorded. In
`SplitPrimeTerminalOrbit.lean`, checked lemmas prove the lattice unit has
order three, has no nonzero fixed point under the tested actions, and
preserves the Eisenstein norm. The finite orbit count and correspondence of
the native point action to the curve endomorphism remain verified by the
native exhaustive test rather than by Lean. CPU timing for this format awaits
a reachable serial runner and an isolation receipt.

The `--unit-split-terminal-orbit-no-fallback` form removes the two axis
fallback rows after the 21-step terminal bound. It retains the 1,280-point
orbit table and indexes it only after asserting `N(a+bτ) < 46²`; coefficient
conversion also rejects magnitudes above 91. The resulting retained size is
**322,056 bytes**, a further 82,336-byte reduction from the orbit format
and 82.3% below the packed tight table. The checked
`canonical_scheme_terminal_coordinates` theorem composes the all-scalar
canonical trajectory bound with exact coordinate inequalities:
`-91 ≤ a ≤ 91` and `-53 ≤ b ≤ 53` at step 21. The runtime guard preserves a
visible failure if the native selector or packed lookup diverges from that
mathematical trajectory.

The [axis-free receipt](terminal-no-fallback-validation.json) records the
separate release build and four passing test families: 128 frozen scalars,
518 additional deterministic and boundary scalars with independent binary
replay, all 3,301 packed residues and 29,709 quotient cases, and all 3,838
direct terminal-point comparisons. This is a retained-memory result. The
native selector and packed lookup bridge remains checked by the model and
native tests; a host-isolated online comparison remains the next performance
measurement.

The `--unit-split-terminal-orbit-no-fallback-two-x` format also stores each
digit-row orbit in the two-x affine representation. Since
`β² + β + 1 = 0`, it retains `x`, `x + βx`, and `y`; a field subtraction
recovers either missing cube-root x image before the mixed addition. Across
21 rows of 66 points, this changes each digit entry from 128 to 96 bytes.
The measured retained size is **277,704 bytes**, 44,352 bytes (13.77%) below
the axis-free format and 84.8% below the packed tight format. It preserves
the same radix, terminal bound, and number of mixed point additions.

The [two-x digit receipt](digit-two-x-validation.json) pins a separate
release binary and five passing test families, including all 8,316 digit
unit images (21 rows × 66 entries × 6 actions), the 646 scalar replays,
and the packed lookup and terminal comparisons. The smaller rows replace
precomputed x coordinates with an online field subtraction for some unit
codes, so a serial isolated comparison is needed to determine the time and
memory tradeoff.

The `--unit-split-batch-affine` evaluator keeps the same 277,704-byte two-x
table but fuses every selected low/high pair with one Montgomery batch
inversion over the at most 21 radix positions. It then adds one affine point
per nonzero digit to the accumulator. The frozen 128-scalar model records a
median of 19 positions with both components nonzero (range 14–21); those
positions each save one mixed accumulator addition. The fusion itself uses
five field multiplications and one field square per pair, plus one shared
binary inversion. The point-addition ordering and inversion are charged to
the online interval when this variant is timed.

The [batch-affine receipt](batch-affine-digit-validation.json) pins a release
binary with six passing test families: a 21-pair check against the independent
projective group law, all 8,316 two-x unit images, 646 independent scalar
replays, 3,301 packed residues and 29,709 quotient cases, and all 3,838
terminal points. `SplitPrimeBatchAffine.lean` proves that all six unit actions
distribute over the low/high digit split, including the canonical seed
reconstruction. The batch inversion's native field implementation is covered
by the group-law and scalar replays. An isolated paired run will determine
whether the saved mixed additions exceed the shared inversion cost.

The `--unit-direct-two-x` evaluator stores the 550 canonical nonzero seeds
directly in each of the 21 digit rows, using the same 96-byte two-x point
representation and six-unit reconstruction. A shared 1,065-entry seed-index
array translates the packed canonical seed to its row position. This yields
one selected point and at most one mixed accumulator addition per nonzero
radix digit, without an online batch inversion or low/high pair addition.
The retained table is **1,258,760 bytes**. Relative to the 277,704-byte
split two-x format, it trades 981,056 more retained bytes for fewer online
point operations. The precise speed and cache cost remain to be measured on
the isolated serial runner.

The [direct-seed receipt](direct-two-x-seed-validation.json) pins the separate
release binary, generated and compiled source hashes, temporary include
shims, and five passing test families: all 69,426 digit unit images, 646
independent scalar replays, all 3,301 packed residues and 29,709 quotient
cases, and all 3,838 terminal points. The first local version indexed the
551-entry row with a raw seed up to 1,064; its two scalar replay failures
prompted the explicit seed-index map in the checked version. The existing
Lean canonical-selector and unit-action results apply to this direct table;
the seed-index map and native point representation are checked by the
exhaustive and independent native tests.
