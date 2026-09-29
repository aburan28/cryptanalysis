# Four-point pair claw: n=53 DLP controls and n=83 work screens

This experiment tests a two-color pair-sum distinguished-point walk for an
ordinary four-point relation. At a state $X$, a fixed hash selects a color
and a pair of points from a target-independent factor base $F$. Color zero
maps to $F_i+F_j$; color one maps to $Q-(F_i+F_j)$. When two trails first
merge with opposite colors, the two pairs sum to $Q$. The witness is checked
with the curve group law. Only distinguished endpoints are retained between
trails; replay recovers the collision predecessors.

This is a group-law search, not a quotient-summation polynomial solver. Its
large-instance cost remains unknown. In particular, a small-base step timing
does not establish relation yield or a sub-$2^{61}$ solve at n=83.
The local [stage proposal registry](stage_proposals.json) assigns `Q1036`
to the completed toy pipeline and `Q1037`–`Q1043` to the later work.
`Q1036` and the complete n=53 known-log control `Q1042` have final `IC1`
candidate identities; the remaining stage proposals do not.

## Complete n=23 one-target control

The [run receipt](runs/n23_one_target.json) and [immutable candidate
manifest](candidates/IC1N23Ckb1fb322PDP4clawRCwalkLAgaussTDdirectISO0h549197846e9c.json)
identify the exact type-II normal field, Koblitz curve, prime subgroup,
projected factor base, algorithm, code hashes, workload, and run. The curve
is `EC1N23Ckb1haed91d8afed0`; the candidate is
`IC1N23Ckb1fb322PDP4clawRCwalkLAgaussTDdirectISO0h549197846e9c`.
`fb322` is the **actual 322 distinct subgroup points before folding**. The
signed-Frobenius quotient has seven columns. `ISO0` means no isogeny; the
manifest records `isogeny: "none"`.

Seven verified setup relations from seven queries gave rank seven. The
recovered logs of all seven representative points were replayed against the
generator. On one previously unseen target, the method found a verified
four-point relation, recovered scalar `987654`, and independently replayed
it. The target-dependent online interval was **201.9 ms**, including the
claw walk, relation check, and scalar replay. It used **3,145 main walk
evaluations** and **9,171 group-add API calls** including replay and
verification. Setup took 17,295 main walk evaluations and is recorded
separately. The scalar used to construct the target fixture was outside the
online clock. No paired rho run or speedup is claimed. The measured `R1`
workload and operation vectors are in the receipt; a single field-operation
total is deliberately `null` because the field API categories are nested.

Run and independently check the control:

```sh
./sage -python experiments/koblitz-pair-claw-20260929/run_n23.py
./sage -python experiments/koblitz-pair-claw-20260929/verify.py
```

## Measured step cost on the named n=53 and n=83 curves

[The stage receipt](runs/n53_n83_step_perf.json) uses the exact curve
records and public targets from the existing frozen prefix workloads. The
n=53 curve has cofactor 428; n=83 has cofactor 4. For each curve, the
benchmark deterministically takes the first 128 rational normal-$x$
coordinates of weight at most two, projects by the correct cofactor, and
includes both signs. This gives a **256-point sample base** at each degree.
It is a timing fixture, not a candidate factor base for four-point yield.
Each reported timing is the median of three uninstrumented 2,048-step
chains. Logical field API calls are counted in a separate run.

| Exact curve ID | Sample B | Median Python time per step | Inversions/step | Multiplications/step |
| --- | ---: | ---: | ---: | ---: |
| `EC1N53Ckb1hf77aab617904` | 256 | 43.3 µs | 1.497 | 2.994 |
| `EC1N83Ckb1h876c2921cb64` | 256 | 62.2 µs | 1.463 | 2.927 |

The field call ratios vary slightly because point-add exceptional cases
depend on the sampled walk. Squarings and field additions are in the receipt.
The code uses a fixed 48-byte encoding per field coordinate so the same
hash definition works through n=131. The timings are for the repository's
accepted Sage launcher running Python field arithmetic on this host; they
are not machine-independent field-operation counts.

```sh
./sage -python experiments/koblitz-pair-claw-20260929/bench_steps.py
```

## Bounded n=53 ordinary-target relation probe

The [full-base probe receipt](runs/n53_weight3_relation_probe.json) uses
every rational normal-$x$ support of weight at most three on
`EC1N53Ckb1hf77aab617904`, projects by the curve's cofactor 428, and
includes both signs. It enumerated **24,062 distinct subgroup points**
before folding and **227 signed-Frobenius columns**. The base and column
setup took 18.7 seconds; the base digest and fixed public target are in the
receipt. This is a stage probe, so its `candidate_id` is `null`.

The fixed target produced **no relation** by the cap of **5,000,000 main
pair-step evaluations**. The query took **533.8 seconds**, including 3,159
endpoint replays, and retained 1,901 distinguished endpoints. Replay steps
are included in wall time but are not included in the main-evaluation count;
the receipt therefore leaves complete work unknown. A simplistic model of
independent, equally split color outputs predicts only
$(5{,}000{,}000)^2/(4r) \approx 0.30$ opposite-color matches by this cap;
that model is not a measured yield curve. The failure remains a data row.
It neither proves that the method scales as $\sqrt r$ nor rules it out.

```sh
./sage -python experiments/koblitz-pair-claw-20260929/probe_n53_relation.py
```

## Signed-Frobenius quotient key and measured searches

The [orbit-key code](orbit_key.py) puts the type-II ONB coefficients in
Frobenius-cycle order. It takes the minimum over all rotations and both
signs. A collision of the canonical keys for $A=F_i+F_j$ and
$Q-(F_k+F_l)$ gives a relation by rotating and possibly negating the first
pair back into the original target equation. The witness is checked against
the enumerated base and the group law. The key invariant and transform were
checked on n=23, n=53, and n=83 points and their Frobenius and sign orbits.

On the same n=23 target, the [quotient target-stage control](runs/n23_quotient_target_control.json)
recovered scalar `987654` in 1,807 main evaluations and 118.3 ms. It imported
the seven factor-base logs from `Q1036`; therefore it is a target-stage
control with `candidate_id: null`, not a second complete IC candidate.

The [paired step benchmark](runs/n53_n83_quotient_step_perf.json) uses the
same 256-point sample bases at both field sizes:

| Curve | Direct step | Quotient step | Quotient/direct wall ratio |
| --- | ---: | ---: | ---: |
| n=53, `EC1N53Ckb1hf77aab617904` | 44.5 µs | 64.2 µs | 1.44 |
| n=83, `EC1N83Ckb1h876c2921cb64` | 64.3 µs | 136.2 µs | 2.12 |

On the full n=53 weight≤3 base, the [quotient distinguished-point
walk](runs/n53_weight3_quotient_relation_probe.json) found **no relation**
by its two-million-main-step cap. It spent 317.4 seconds on the query and
replayed 11,418 endpoint merges. The simple independent-output model would
predict about five opposite-color matches at that cap; repeated walk states
make that model unreliable for this implementation. This measured miss is
why no quotient-walk $\sqrt{r/(2n)}$ claim is made.

A direct quotient **pair table** did find an ordinary n=53 relation for the
same public target. The [receipt](runs/n53_weight3_quotient_table_probe.json)
and [independent verifier](verify_table.py) fix the same 24,062-point base,
227 folded columns, and exact field/curve. The target-independent table used
500,000 pair samples and kept 457,277 distinct quotient keys. A target-side
pair matched after 165,899 samples. This run used 665,899 pair samples,
or $2^{19.345}$ stage samples. Table and query times were 23.6 and
12.4 seconds; base setup took 19.0 seconds. Peak parent RSS was 156 MiB.
The independently replayed four-point witness sums to the public target.
The factor-base logs and target DLP remain unknown, so `Q1040` has
`candidate_id: null` and no complete-work exponent.

```sh
./sage -python experiments/koblitz-pair-claw-20260929/verify_orbit_key.py
./sage -python experiments/koblitz-pair-claw-20260929/probe_n23_quotient.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_quotient_steps.py
./sage -python experiments/koblitz-pair-claw-20260929/probe_n53_quotient.py
./sage -python experiments/koblitz-pair-claw-20260929/probe_n53_table.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_table.py
```

## Exact n=83 orbit base and bounded full-base timing

The [n=83 base receipt](runs/n83_weight5_orbit_base.json) and
[compressed orbit-key file](runs/n83_weight5_orbit_keys.bin) freeze an
actual, target-independent weight-five normal-$x$ orbit-union base on
`EC1N83Ckb1h876c2921cb64`. A deterministic seed drew 52,021 five-bit
supports, considered 48,381 distinct $x$ orbits, and retained 24,097
rational, nonidentity, distinct subgroup-point orbits after $[4]$
projection. The subgroup order is prime. Its Frobenius eigenvalue has order
83, so every nonidentity representative has 166 distinct signed-Frobenius
points. **Actual B is 4,000,102 before folding; effective columns are
24,097.** The sorted 21-byte canonical-key file is 506,037 bytes; its
SHA-256, expansion rule, source hashes, exact field/curve record, and
`isogeny: "none"` are in the receipt. Building it took 7.4 seconds in this
Python run. The [independent verifier](verify_n83_base.py) decoded and
checked all 24,097 representatives on the curve and in the subgroup.

The [full-base stage benchmark](runs/n83_full_base_quotient_pair_perf.json)
decoded base points on demand. On the same public n=83 target, 100,000
target-independent table samples averaged **99.5 µs/sample**, and 100,000
target-complement query samples averaged **145.8 µs/sample**. There were
zero quotient-key hits at this tiny cap. Peak parent RSS was 52.4 MiB.
In a separate instrumented run, one table sample used 1 field inversion,
2 multiplications, 1 squaring, and 7 additions; one target-side sample
used 2 inversions, 4 multiplications, 2 squarings, and 15 additions.
These are real pair-sample costs on the exact base, but they do not measure
ordinary relation yield at a useful query budget or recover any base log.

```sh
./sage -python experiments/koblitz-pair-claw-20260929/build_n83_orbit_base.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_base.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_n83_full_base.py
```

## Conditional n=83 work screen

The [direct-walk screen](n83_conditional_screen.json) uses the **enumerated**
base above. Under a uniform-sum model it has about 4.41 four-point
multisets per target in expectation. It further supposes that a useful opposite-color
claw costs exactly $\sqrt r$ walk evaluations and that every verified
relation adds rank. Charging one further search for the target gives

$$
\log_2((24{,}097+1)\sqrt r) = 55.057
$$

**pair-step evaluations**, before constants, misses, rank dependencies,
base construction, replay, memory, and matrix work. For a total budget of
$2^{61}$ field operations, all those costs together leave at most **61.5
field operations per pair step** even if every other stage were free. No
conversion of the measured inversions into field-operation equivalents has
been established. Reusing the small-base n=83 Python step time would imply
about **74,000 one-core years**, a wall-time illustration whose cache
behavior and search law are unvalidated at a four-million-point base.

The n=53 budget miss does not calibrate an n=83 success rate. The screen
records the actual B and column count, but keeps `candidate_id`, measured
n=83 relation yield, and complete-work exponent `null`; the stage-specific
`verified_n83_dlp` flag is false. It does
not promote a stage benchmark or a conditional extrapolation to a result.
An exact n=83 candidate still needs measured ordinary-query yield including failures, rank per
query, a verified previously unseen target DLP, and complete operation
accounting. Those are the next gates for this line.

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_screen.py
```

The [quotient-table screen](n83_conditional_table_screen.json) makes the
memory/work exchange explicit for the same exact base. It assumes a
reusable table of $M$ **distinct** zero-pair quotient keys, independent
uniform target-side keys, 95% match probability for targets with a relation,
and one novel rank row per successful query. It charges the table once,
about $24{,}097/0.95$ setup queries, and one target query. Matrix and base
construction, duplicate rows, missing target representations, and the cost
of a field operation are still unpriced.

| Distinct table keys | Key bytes alone | Ideal cold pair samples | Maximum field operations/sample for total $<2^{61}$ |
| ---: | ---: | ---: | ---: |
| $2^{27}$ | 2.6 GiB | $2^{62.84}$ | 0.28 |
| $2^{30}$ | 21 GiB | $2^{59.84}$ | 2.24 |
| $2^{33}$ | 168 GiB | $2^{56.84}$ | 17.9 |
| about $2^{35.49}$, near the full pair-key cap | 943 GiB | $2^{54.35}$ | 100.4 |

The memory column contains only the 21-byte quotient key per entry. Pair
indices and hash-table overhead add to it; a 32-byte packed entry at the
last row would occupy about 1.4 TiB. Even the $2^{30}$ row leaves only
2.24 field operations per pair sample, before any other work. The large
memory rows may fit a $2^{61}$ *conditional operation count* only if their
unmeasured per-sample field cost falls below the listed cap. The n=53
relation shows that the table can work on a larger field; it does not
validate the n=83 uniform model or provide an n=83 DLP.
Even counting every measured field API call as one unit, including each
inversion, the $2^{33}$-key row would cost $2^{61.36}$ units. At the last
row, that optimistic model gives $2^{58.87}$ units; the total could stay
below $2^{61}$ only if an inversion cost at most 39.7 such units when field
additions, multiplications, and squarings each cost one and every other
stage is free. This is a conditional threshold, not a field-operation
calibration or a complete solve.
At the last row, the measured **small-table** n=83 Python rates would imply
roughly 100,000 one-core years. That is a conditional wall extrapolation;
memory behavior at a terabyte-scale table has not been measured.

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_table_screen.py
```

## Known-log orbit base: complete n=53 control and n=83 screen

The previous weight-five bases have unknown factor-base logs. A second
target-independent construction starts from seeded scalar multiples
$[a_i]G$. Their logs $a_i$ are known, and the Frobenius eigenvalue gives
the log of every signed-Frobenius orbit point. It retains the same quotient
pair-matching algorithm and needs **no relation matrix**. The candidate
stage tag is `LAnone` for this precise reason.

The [n=53 complete run](runs/n53_knownlog_one_target.json) has its own
[immutable candidate manifest](candidates/IC1N53Ckb1fb24062PDP4qtableRCdirectLAnoneTDdirectISO0h7c80ef394c64.json).
Its 227 independently checked seed logs expand to **actual B=24,062**
points. On the same public n=53 target as the preceding probes, 500,000
table samples and 1,249,820 target-side samples found a proper relation.
The recovered scalar is **`3400509474685`**, independently replayed as
$[k]G=Q$ and checked against the fixture. The one-target online interval
was **117.94 seconds**; cold base, table, membership index, and online time
totaled **150.10 seconds**. Cold pair samples were 1,749,820, or
$2^{20.739}$. The [independent verifier](verify_knownlog_n53.py) rebuilt
all seed logs and the matching pair metadata. No paired rho speedup or
field-operation total is claimed.

The [n=83 known-log base](runs/n83_knownlog_orbit_base.json) independently
replays 24,097 seeded scalar orbits, again giving **actual B=4,000,102**
and **24,097 folded columns, all with known logs**. Its compressed
[key-and-log file](runs/n83_knownlog_orbit_keys_and_logs.bin) is 771,104
bytes. Base construction took 64.4 seconds; the
[independent verifier](verify_n83_knownlog_base.py) regenerated every key
and log. On that exact base, the [bounded stage benchmark](runs/n83_knownlog_pair_perf.json)
measured **95.4 µs per table sample** and **140.4 µs per target-side
sample** over 100,000 samples of each. It found zero matches at that small
cap, and no DLP from this quotient-table stage.

### X-only keys, unique pair schedules, and corrected work estimate

The [stage proposal record](stage_proposals.json) records these measured
stages as **Q1044** on `EC1N53Ckb1hf77aab617904` and **Q1045** on
`EC1N83Ckb1h876c2921cb64`. Both reuse the exact known-log bases from
Q1042 and Q1043, with actual pre-folding B and folded columns recorded
separately and `isogeny: "none"`. Their candidate IDs remain null because
this optimized schedule has not completed a one-target pipeline.

The signed-Frobenius quotient key needs only the x coordinate: negation
leaves x unchanged, and the least normal-basis x rotation identifies the
orbit. The [paired benchmark](runs/n53_n83_batch_xkey_perf.json) checked
the x-only key against the original full-point key on 32,768 table pairs
and 32,768 target-side pairs per curve. Three timing repetitions on the
same pairs give n=53 target-side medians of **89.5 µs** (range 89.4–91.5)
for the full key and **79.1 µs** (78.9–80.2) for x-only. At n=83 they
give **138.3 µs** (137.3–138.5) and **119.3 µs** (119.2–119.6).
Batch inversion was also measured, but the local ONB inversion costs only
about 2.29 multiplication-call times at n=83. Its extra multiplications
made the 256-point batch slower at **131.0 µs** (129.4–131.2) than
direct x-only addition. The [field calibration](runs/n53_n83_field_unit_perf.json)
records the local timing ratios.

The [unique schedule](runs/n53_n83_unique_schedule_perf.json) permutes
zero-pair quotient descriptors and unordered query-pair ranks without
repeats. At n=83 its three-repetition medians were **77.1 µs per table
descriptor** (range 76.9–77.3) and **119.6 µs per target query**
(118.9–119.8), over 32,768 of each; all table descriptors and
query ranks were distinct. The [exhaustive n=23 receipt](runs/n23_pair_schedule_verified.json)
from [the verifier](verify_pair_schedule.py)
compared all 52,003 unordered base pairs with the 1,127
nonidentity quotient descriptors and found the same 1,094 distinct keys.
The n=83 base still has no measured target relation.

The previous screen treated repeated queries as independent even after
the finite query-pair domain had been exhausted. That gave impossible 95%
success estimates for small tables. The [corrected screen](n83_knownlog_conditional_screen.json)
uses the exact **8,000,410,005,253** unordered query pairs and a cap of
**48,195,228,947** nonidentity zero-pair quotient descriptors. Its
random-base heuristic has an average of **4.412** distinct four-point
multisets for a fixed target. Each has six zero-pair/query-pair
partitions. Indexing fraction $f$ of zero-pair keys and visiting fraction
$t$ of unique query pairs gives modeled success
$1-\exp[-4.412(1-(1-ft)^6)]$. This is a prediction, not measured yield.

| Distinct table keys | Modeled maximum success after all query pairs | Unique target queries for 95% | Conditional sampled-stage Python multiplication-time equivalents | x-key bytes alone |
| ---: | ---: | ---: | ---: | ---: |
| $2^{24}$ | 0.92% | impossible | unknown | 176 MiB |
| $2^{28}$ | 13.53% | impossible | unknown | 2.75 GiB |
| $2^{30}$ | 42.76% | impossible | unknown | 11 GiB |
| $2^{32}$ | 84.92% | impossible | unknown | 44 GiB |
| $2^{33}$ | 95.28% | $2^{42.82}$ | $2^{46.55}$ | 88 GiB |
| $2^{34}$ | 98.34% | $2^{41.82}$ | $2^{45.55}$ | 176 GiB |
| about $2^{35.49}$ | 98.79% | $2^{40.33}$ | $2^{44.09}$ | 494 GiB |

The model needs at least **8,314,903,507 distinct table keys**
($2^{32.95}$) to reach 95% even after exhaustive query enumeration.
At $2^{33}$ keys, the 32-byte illustrative packed table would use **256
GiB** before hash or sorting overhead. The $2^{46.55}$ number divides
the measured small-stage Python time by the measured local n=83 field
multiplication-call time; it includes base decoding, pair arithmetic,
keying, and rank scheduling in those stage samples. It omits large-table
lookup, duplicate keys, base construction, and final relation replay, so
it is **not** a complete field-operation count or a demonstrated
sub-$2^{61}$ solve. Extrapolating the same small-stage rate gives about
**29.4 one-core years** at $2^{33}$ keys. The public target's actual
four-point representability remains unverified.

### Native n=83 exact-table measurement and solve-work units

The [native pair-stage receipt](runs/n83_native_pair_perf.json) uses the
same curve, exact known-log base, frozen target, and unique schedules as
Q1045. Its C++ field kernel uses the generated n=83 basis conversion and
batched affine additions. The first 256 table keys and first 256 target
keys were checked against the independent Python implementation for each
batch size. Over one million samples per phase and three repetitions,
batch size 1024 gave medians of **157.8 ns per table descriptor** and
**192.8 ns per target query** for arithmetic, keying, and scheduling.
This stage has no materialized hash table or lookup.

The [exact-table receipt](runs/n83_native_exact_table_perf.json) then
materialized lossless 83-bit x keys in 12-byte open-address slots. It
tested table sizes $2^{20}$, $2^{24}$, $2^{26}$, and $2^{28}$ with
$2^{20}$ unique public-target queries at each size. The largest table had
**268,435,456 distinct keys, zero duplicates, 4,601,762,952 table bytes**
(4.29 GiB), and **zero key hits**. Its build rate was **351.5 ns per
descriptor** and its target rate, including exact lookup, was **415.3 ns
per query**; peak process RSS was about 4.76 GB. The zero-hit observation
at this cap is consistent with the model's maximum 13.53% target success
even after *all* query pairs are searched. The separate
[planted-hit control](runs/n83_native_planted_control.json) found its
constructed hit, reconstructed all four points, recovered the scalar, and
independently replayed it. That control does not measure ordinary target
relation yield.

For an explicit $2^x$ work estimate, the [finite-support screen](n83_knownlog_conditional_screen.json)
uses $M=2^{33}$ exact table keys and about $2^{42.816}$ unique target
queries to obtain **95% modeled success** on this fixed base. The sum is
$2^{42.818}$ pair evaluations. Counting the native batched code's field
XORs, multiplications, and squarings, including its inversion chain,
gives approximately **$2^{47.58}$ field-operation calls**; multiplications
alone are $2^{46.14}$. These are algorithm-level counts under the
finite-support model, not a measured complete solve. They exclude key
canonicalization, hash probes, memory traffic, base construction, and
final replay. At the measured small-table rates, arithmetic without
lookup extrapolates to **17.3 one-core days**, while applying the
$2^{28}$ exact-table build and lookup rates to the much larger proposed
table gives **37.3 one-core days**. The latter is only a throughput proxy:
the required $2^{33}$-key table would occupy about **147 GB** with this
12-byte-slot design at 70% load, above this host's 48 GB physical memory,
and its large-table lookup rate is unmeasured. There is still no verified
ordinary n=83 relation or quotient-table public-target DLP, so the
complete **IC** solve work remains **unknown** and no sub-$2^{61}$ IC
result is claimed.

The same n=83 public target already has a separately verified
[rho solution](../ecc2k130-quotient-pair-probe-20260926/runs/n83_public_target_rho_solved.json):
the recovered scalar is `467066815623456506232910`, independently replayed
on this exact curve after **$2^{37.554}$ aggregate walk iterations** across
three workers. The rho result supplies a same-target reference and a
complete DLP in rho-step units. It does not establish ordinary factor-base
relation yield or the quotient-table solve cost. The
[finite-support screen](n83_knownlog_conditional_screen.json) now links the
rho receipt explicitly and labels its own DLP flag as
`verified_n83_quotient_table_dlp`.

These additions are stage proposals **Q1046** and **Q1047** under the
same exact `EC1N83Ckb1h876c2921cb64` curve and B=4,000,102 known-log
base. Their `candidate_id` remains null. The factor base is recorded as
actual B before folding, with 24,097 signed-Frobenius columns separately;
both records specify `isogeny: "none"`.

### Bounded memory filter with exact second-pass verification

Stage **Q1048** replaces the large in-memory exact table with a two-block
Bloom filter. It sets 17 independently mixed bits per 83-bit quotient key
across two 64-byte blocks and keeps every positive target query for an
exact second pass over the deterministic table schedule. Only a replayed
exact key match is sent to the independent four-point and scalar verifier.
The [bounded receipt](runs/n83_native_bloom_exact_replay_perf.json) used
the exact same n=83 curve, B=4,000,102 base, and frozen public target.
At $2^{28}$ table descriptors, the filter occupied **805,371,904 bytes**;
$2^{24}$ unique target queries produced **291 filter positives and zero
exact matches**. The planted control yielded one exact match and an
independently replayed scalar. Build, target-query, and exact replay rates
were approximately **312.6**, **344.8**, and **165 ns per descriptor or
query**, respectively. The 291 false positives give a measured rate
$1.7345\times10^{-5}$ on that bounded query prefix; the reported Wilson
interval assumes independent outcomes and may not cover correlations in
the deterministic schedule.

The [resource screen](n83_bloom_resource_screen.json) applies those rates
to the same **95% modeled success** point of $2^{33}$ distinct table keys
and about $2^{42.816}$ unique target queries. Its projected Bloom filter
is **25.77 GB**; the measured false-positive rate suggests about **134
million** candidate queries. Allowing twice that count for vector capacity
and adding observed base-process overhead gives an illustrative **32.4 GB
peak filter-phase footprint**, below the host's 51.54 GB physical memory.
The one-core measured-rate proxy, including a second exact table pass, is
**31.0 days**; the field add/multiply/square model is $2^{47.58}$ calls.
These are conditional projections from the bounded run. Full-size memory
pressure, throughput, exact key counts, target representability, and
ordinary relation yield remain unmeasured. The rho reference above is the
only verified complete DLP for this n=83 public target.

```sh
./sage -python experiments/koblitz-pair-claw-20260929/knownlog_n53.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_knownlog_n53.py
./sage -python experiments/koblitz-pair-claw-20260929/build_n83_knownlog_base.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_knownlog_base.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_n83_knownlog.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_batch_xkey.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_field_unit.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_unique_schedule.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_pair_schedule.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_native_n83.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_native_n83_table.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_native_n83_planted.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_native_n83_bloom.py
python3 experiments/koblitz-pair-claw-20260929/n83_knownlog_screen.py
python3 experiments/koblitz-pair-claw-20260929/n83_bloom_resource_screen.py
```
