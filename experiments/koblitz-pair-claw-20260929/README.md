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

### Q1067 salted epoch restart screen

The frozen [Q1067 plan](n53_quotient_epoch_plan.json) tests whether changing
the quotient walk's deterministic map after a bounded epoch reduces repeated
states. It fixes the same n=53 public target, exact weight-three base
(`EC1N53Ckb1hf77aab617904`, 24,062 usable points, 227 folded columns,
base digest `356ebb34476f44b89d376e04fe4b03570a0a4cf3dfe0cd722309d7ea083ccc18`),
walk seed, distinguished threshold, and two-million-main-step cap. The
[n=23 correctness control](runs/n23_quotient_epoch_control.json) found a
valid four-point witness under both epoch settings; a 500-step-per-epoch
control also forced a restart and found its witness in epoch three. The n=53
variants share workload ID `c87b5dc47ab5` and use `isogeny: "none"`;
Q1067 remains a stage proposal with null candidate and run IDs.

| n=53 variant | Main steps | Replay steps | Total pair-map steps | Distinct output keys summed within epochs | Endpoint rows | Query wall | Natural relations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| One epoch | 2,000,000 | 2,685,910 | 4,685,910 = $2^{22.160}$ | 495,435 | 3,889 | 300.34 s | 0 |
| Four epochs | 2,000,000 | 2,345,047 | 4,345,047 = $2^{22.051}$ | 865,659 | 6,719 | 283.26 s | 0 |

The [paired comparison](n53_quotient_epoch_comparison.json) links the two
receipts and their checked Sage runtime. Four epochs used 7.27% fewer total
pair-map steps and ran 1.0603 times faster on this one target and seed. The
distinct-key sum is within separate maps; it is not a cross-epoch unique
count. Neither run found a relation, so this screen supplies no natural-yield
rate, n=83 speedup, or complete DLP work exponent. The $2^x$ values above
count pair-map calls, including replay, and are **not** field operations or
an estimated solve. One paired seed cannot establish uncertainty for the
wall ratio or relation yield. The active n=83 native searches retain their
separately frozen implementation.

```sh
./sage --runtime-info > /private/tmp/n53_quotient_epoch_runtime_info.json
./sage -python experiments/koblitz-pair-claw-20260929/control_n23_quotient_epochs.py
./sage -python experiments/koblitz-pair-claw-20260929/probe_n53_quotient_epochs.py --variant single --runtime-info /private/tmp/n53_quotient_epoch_runtime_info.json --out /private/tmp/n53_quotient_epoch_single_replay.json
./sage -python experiments/koblitz-pair-claw-20260929/probe_n53_quotient_epochs.py --variant four --runtime-info /private/tmp/n53_quotient_epoch_runtime_info.json --out /private/tmp/n53_quotient_epoch_four_replay.json
python3 experiments/koblitz-pair-claw-20260929/summarize_n53_quotient_epochs.py
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
calibrated field-operation total is claimed from that original run.

The [Q1076 instrumented replay](runs/n53_knownlog_field_api_replay_q1076.json)
used the same exact curve, base seeds, table/query seeds, target, and
checked Sage runtime. It reproduced the archived relation after
1,249,820 target queries and recovered the same scalar. Across base
setup, table build, online search, and scalar replay, it directly counted
31,455,094 non-inversion field API calls and 3,012,612 inversions. The
online portion counted 26,245,565 non-inversion calls and 2,499,573
inversions. At the **assumed** weight of 90 calls per inversion, those
are $2^{28.173}$ cold and $2^{27.904}$ online weighted API calls. The
90-call weight has not been calibrated for this Python Euclidean inversion
implementation. Q1076 is a diagnostic proposal with null candidate and
run IDs; the original uninstrumented 117.94-second online measurement
remains the wall-time result.

The curve and candidate hashes in the n=23 and n=53 manifests were
recomputed against the catalog's sorted-key canonical JSON rule. Their
`fb` tags use actual pre-folding point counts, and both record
`isogeny: "none"`. The archived n=23 and n=53 raw run receipts retain
their originating `Q` proposal ID alongside their promoted `IC1` ID.
That is historical provenance, but those are not schema-compliant catalog
measurement rows:
the [measurement contract](../ic-candidate-catalog/MEASUREMENT.md)
requires exactly one of those IDs to be non-null. New comparison rows
must use the `IC1` ID and carry the old `Q` lineage separately. The
current n=83 search records use `Q` proposal IDs with `candidate_id: null`
until a complete method and verified target solve are recorded.

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
were approximately **314.8**, **348.6**, and **170.8 ns per descriptor or
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
**31.3 days**; the field add/multiply/square model is $2^{47.58}$ calls.
These are conditional projections from the bounded run. Full-size memory
pressure, throughput, exact key counts, target representability, and
ordinary relation yield remain unmeasured. The rho reference above is the
only verified complete DLP for this n=83 public target.

### Parallel query ranges and first full-key chunk

Stage **Q1049** shares one read-only Bloom filter among query workers and
accepts an absolute query-position offset. The [paired receipt](runs/n83_native_bloom_parallel_perf.json)
compared one, four, and eight workers on identical n=83 public-target
query ranges. At $2^{28}$ table descriptors and $2^{25}$ unique target
queries, the query phase measured **346.7 ns per pair with one worker**
and **51.5 ns per pair with eight workers**: a **6.73×** speedup in the
query phase. All worker counts produced the same 564 filter positives and
zero exact hits. A separate split-range check showed that two disjoint
query ranges recombine to exactly the full range's positive, false-positive,
and exceptional-query counts. The [chunk runner](run_n83_bloom_chunk.py)
records one frozen range, its failed work or verified hit, phase timings,
source hashes, and the same-target rho scalar check when a hit occurs.

The [first-chunk screen](n83_parallel_chunk_screen.json) specifies
$2^{33}$ table descriptors, the first $2^{38}$ unique query pairs, and
eight workers. It predicts a **14.76% relation probability** under the
same finite-support model, **26.15 GB** illustrative peak filter-phase
memory, **5.74 hours** from bounded build/query/replay rates, and about
$2^{42.81}$ field add/multiply/square calls. These are predictions until
that full-key chunk actually finishes; the $2^{28}$-key query speed may
change when the filter grows to 25.77 GB. Each separate chunk rebuilds
the filter, and cumulative solve work must charge every chunk, including
ones with zero relations.

### Memory-bounded n=83 table shards and measured-work boundary

The first $2^{33}$-descriptor, 24-bit-filter run was stopped during filter
construction when host swap-outs rose and the system volume had about 3 GiB
free. Its [terminal receipt](runs/n83_bloom_chunk_M33_Q38_start0.json)
records exit 130, the source and input hashes, and **unknown consumed field
work**. It is not a completed zero-hit sample. This observation supersedes
the earlier 26.15 GB peak-memory projection as a feasibility claim on this
host.

Stage Q1049 now accepts a nonzero absolute table start. Two disjoint
$2^{32}$ table shards cover the same first $2^{33}$ scheduled descriptors;
each shard scans the same unique target-query prefix, and every build and
exact replay is charged. The native hit stores its **absolute** table
position, so the existing independent four-point verifier still checks the
relation and recovered scalar. A [nonzero-shard planted control](runs/n83_bloom_bits20_nonzero_shard_planted.json)
at table position 1024 passed. It is a correctness control, not natural
relation yield. The [chunk aggregator](aggregate_n83_bloom_chunks.py)
rejects overlapping table/query rectangles, checks curve, target, base,
source and Bloom parameters, and preserves any failed chunk's unknown
work. A verified scalar remains a verified scalar even if cumulative work
is unknown.

The [20-bit calibration](runs/n83_bloom_bits20_stage_M28_Q24.json) used
$2^{28}$ descriptors, $2^{24}$ queries, 14 hashes, and eight workers on
the same n=83 curve, factor base, and public target. It measured **1,599
Bloom positives, zero exact matches**, 671,154,176 filter bytes, and
835,387,392 bytes peak RSS. The [shard screen](n83_bloom_shard_screen.json)
gives a nominal Wilson 95% false-positive-rate interval of
$[9.075\times10^{-5},1.001\times10^{-4}]$, equivalent to about
24.9–27.5 million candidates at $2^{38}$ queries if the rate transfers.
The deterministic schedule may violate that interval's independence
assumption. Timing uncertainty from the single bounded run is unmeasured.
The screen
projects one $2^{32}$-descriptor, $2^{38}$-query shard at **10.00 GiB
filter memory**, **11.32 GiB illustrative peak filter-phase memory**,
**4.03 hours** from the smaller run's phase rates, and **$2^{42.786}$
field add/multiply/square calls**. These are predictions; the large
random-access filter may change throughput. The finite-support model
assigns **7.73%** success to the first shard and **14.76%** to both
shards at this query prefix. The first shard was
[interrupted](runs/n83_bloom_chunk_M32_Q38_tstart0_qstart0_b20_h14.json)
after about an hour when swap-outs rose and the system volume fell to
about 1.2 GiB free. The process exited 130, its native child was absent
on readback, and its native phase counts and consumed work are **unknown**.
It is not a completed zero-hit measurement.

For the 95% *modeled* success point, both $2^{32}$ shards would each
scan about $2^{42.816}$ unique query pairs. Counting both builds, both
exact replays, and both query scans gives **$2^{48.581}$ field calls**
under the native operation model. Scaling the bounded rates gives
**8.14 elapsed days** for those two sequential eight-worker shards;
but retaining all positives from either long query pass would give an
illustrative **43.15 GiB peak filter-phase footprint**, unsafe with the
available host memory. The executable bounded plan uses **29 chunks of
$2^{38}$ queries per table shard**, or 58 runs covering 7,971,459,301,376
unique query positions per shard. It reaches **95.25% modeled success**
and charges **$2^{48.644}$ field calls** and **9.74 elapsed days** at the
small-run rates, including all 58 filter builds and exact replays.
These are conditional projections; the full-size random-access rate has
not been measured. Quotient keying, Bloom probes, memory
traffic, base construction, failed work with unknown counts, and final
verification remain outside that number. It is a conditional stage
estimate, **not** measured complete IC solve work or evidence of a
sub-$2^{61}$ IC solve.

The [campaign driver](n83_bloom_campaign.py) lists the 58 disjoint
table/query rectangles, runs at most one missing chunk per invocation,
and refuses to advance past a start marker, a terminal failure, or a
verified DLP. A marker alone is not proof that a process is alive; check
the original run handle before resuming. `--aggregate` writes the
completed 20-bit shard receipts into a separate cumulative account.
The interrupted 24-bit prototype remains in the research record but is
outside this 20-bit candidate configuration.

A [paired bounded lookup check](runs/n83_bloom_early_exit_paired_negative.json)
tested stopping a Bloom membership query at its first missing bit. It
produced identical exact outcomes over $2^{26}$ table descriptors and
$2^{27}$ query pairs in both ABBA repetitions, but its query phase took
**1.055×** the baseline time. The full-size shard was running at the
same time, so this is a bounded negative result rather than a full-size
throughput comparison; the early-exit variant was not promoted.

### Signed-Frobenius query-pair reuse (Q1050)

Every cross-orbit pair in this base belongs to a 166-member simultaneous
sign/Frobenius orbit. For a representative pair sum $Z$, its lifted query
key obeys the exact identity

$$\operatorname{can}_x(Q-\epsilon\pi^k Z)
  =\operatorname{can}_x(\pi^{-k}Q-\epsilon Z),\qquad
  \epsilon\in\{+1,-1\}. $$

The right side computes $Z$ once, then checks 166 target complements.
The [n=23 control](runs/n23_query_orbit_reuse_control.json) exhaustively
maps all 44,436 cross-orbit unordered pairs to 966 representatives with
no duplicates and checks 944 group/key identities. The
[n=83 control](runs/n83_query_orbit_reuse_sample.json) checks 512 more
identities on the exact B=4,000,102 base and frozen target. Within-orbit
pairs account for only **0.00417%** of the n=83 unordered query domain;
Q1050 currently omits them, and its model records that exclusion.

The [native bounded stage](runs/n83_native_query_orbit_bounded.json)
uses the same 20-bit Bloom filter and exact second pass as Q1049. Its
planted hit at **table start 1024, query-representative start 256** was
reconstructed into four base points and an independently replayed scalar.
All three bounded public-target runs had zero exact hits. An
[ABBA paired comparison](runs/n83_orbit_reuse_vs_direct_ABBA_bounded.json)
at $2^{24}$ table descriptors and 43,515,904 tested complements per run
measured **1.251× query-phase speedup** over the direct solver. The
deterministic query schedules differ, and a full-size shard was running
concurrently; $2^{32}$-table throughput remains unmeasured.

The [conditional work screen](n83_query_orbit_reuse_screen.json) uses
22 chunks of $2^{31}$ query-pair representatives per $2^{32}$ table
shard. Across two shards this covers a **95.11% modeled success**
prefix in 44 runs. Counting each build, exact replay, representative
pair addition, lifted target addition, and batch inversion gives
**$2^{47.592}$ field add/multiply/square calls**, about 2.07× fewer
than Q1049's 58-chunk model on the same base. This count excludes
keying, Bloom probes, memory, setup, and scalar replay. No ordinary
n=83 relation or complete quotient-table DLP has been measured for
Q1050, so neither model is a complete sub-$2^{61}$ solve claim.

A [larger n=83 stage run](runs/n83_orbit_chunk_M28_R20_tstart0_qstart0_b20_h14_rb8.json)
completed with $2^{28}$ table descriptors and $2^{20}$ representatives
(174,063,616 lifted target complements): **16,421 Bloom positives, zero
exact matches**, 671,154,176 filter bytes, and 836,894,720 bytes peak
RSS. Its build, query, and exact replay phases took 85.69, 6.34, and
50.70 seconds. Query time was **36.45 ns per lifted complement**. No
swap-outs occurred during this bounded run. Scaling those measured
rates gives **7.73 days** for the 44-run two-shard model, with an
illustrative **11.66 GiB** peak filter-phase footprint per chunk.
The prior 10 GiB-filter direct run nevertheless caused host swap and
was interrupted; this is not evidence that a $2^{32}$ Q1050 shard fits.
Four $2^{31}$ table shards instead project **6.66 GiB** peak per chunk,
**$2^{48.576}$ field calls**, and **14.34 days** across 88 chunks at
the earlier $2^{28}$ rates. These memory and time figures remain projections.

Three more public-target [calibrations](n83_query_orbit_reuse_screen.json)
used the same curve, target, base digest, solver binary, filter settings,
and $2^{20}$ query representatives:

| Table descriptors | Filter | Peak RSS | Build | Query | Exact replay | Exact hits |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| $2^{28}$ | 0.67 GB | 0.84 GB | 85.69 s | 6.34 s | 50.70 s | 0 |
| $2^{29}$ | 1.34 GB | 1.51 GB | 221.09 s | 5.99 s | 100.38 s | 0 |
| $2^{30}$ | 2.68 GB | 2.85 GB | 353.63 s | 6.14 s | 201.30 s | 0 |
| $2^{31}$ | 5.37 GB | 5.53 GB | 798.46 s | 6.73 s | 406.70 s | 0 |

Swap-outs stayed flat through all four runs. Build rate varied from
319 to 412 to 329 to 372 ns per descriptor. Scaling the measured
$2^{31}$ table and $2^{20}$-representative query rates projects
**15.27 days** for the four-shard 95.11% model; this remains a forecast,
with full-size query throughput, candidate memory, and natural relation
yield unmeasured. The completed $2^{31}$ stage used a modeled
$2^{35.768}$ field add/multiply/square calls; no complete DLP work
exponent is known.

The [Q1050 chunk runner](run_n83_orbit_chunk.py) freezes one absolute
table range and one query-representative range, records a terminal failed
receipt with unknown work on interruption, and independently replays an
exact public-target hit against the same-target rho scalar. Its bounded
zero-hit smoke checks passed at table starts 0 and 4096 and query starts
0 and 1024. The [aggregator](aggregate_n83_orbit_chunks.py) combined
two disjoint table shards and rejected a duplicate rectangle. The
[campaign driver](n83_orbit_campaign.py) defaults to the four-shard,
88-rectangle M=$2^{31}$ plan. The earlier two-shard, 44-rectangle
M=$2^{32}$ plan is available for read-only inspection with `--plan m32`.
The driver advances one rectangle per invocation only when no search
start marker exists and at least 4 GiB is free on the system volume.
This disk guard does not establish that a full M=$2^{31}$ run fits in
memory. The direct shard's original process handle exited 130; its
terminal failure receipt remains in the record. A start marker guards
against accidental concurrent filters; it is not proof of life.

Naming follows the [candidate catalog measurement contract](../ic-candidate-catalog/MEASUREMENT.md):
the exact curve is `EC1N83Ckb1h876c2921cb64`; the factor base has
**B=4,000,102 actual subgroup-usable points before folding** and 24,097
signed-Frobenius columns, with its enumerated-set digest in each receipt;
the isogeny is `"none"`. Q1049 and Q1050 remain proposals with
`candidate_id: null` because a complete IC target solve and all pipeline
stages have not been measured. No nominal base dimension or folded column
count is being used as `fb<B>` in an `IC1` name.

### Doubled known-log orbit base (Q1051)

The [extended base receipt](runs/n83_knownlog_orbit_base_k48194.json)
uses the same n=83 field, curve, generator, seed stream, and
`isogeny: "none"` as Q1050. It contains **48,194 distinct signed-Frobenius
orbits**, or **B=8,000,204 actual subgroup points before folding**.
Its enumerated-set digest is
`7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02`.
The [independent replay](runs/n83_knownlog_orbit_base_k48194_verified.json)
checked every canonical key and log against the seeded scalar stream and
confirmed that all 24,097 original orbits and logs are a subset. A
[nonzero-offset planted control](runs/n83_large_orbit_nonzero_offset_planted.json)
used two orbits beyond the original base, found one exact quotient hit,
and independently replayed its scalar. It is a correctness control, not
natural target yield.

The [Q1051 work screen](n83_large_knownlog_base_screen.json) estimates
95.24% success for **one $2^{31}$-descriptor table** scanned against
**59 chunks of $2^{31}$ query representatives**. It charges
**$2^{47.999}$ native field add/multiply/square calls**, compared with
$2^{48.576}$ for Q1050's four-shard 88-chunk plan. The larger base
raises the modeled four-point multiset count from 4.41 to 70.59 and
makes the one-shard query prefix fit within its exact pair domain.
These success rates and field-call totals are conditional models.
The [first-hit work distribution](n83_large_orbit_solve_work.json)
states the solve estimate at a fixed accounting boundary: one complete
rectangle costs $2^{42.116}$ modeled native field calls, including its
fresh table build and exact replay. The model reaches 50% success after
14 rectangles ($2^{45.923}$ calls), 90% after 45
($2^{47.608}$), and 95% after 59 ($2^{47.999}$). Conditional on a hit
within all 89 full disjoint rectangles, its expected first-hit work is
$2^{46.349}$ calls; the modeled chance of no hit after all 89 is still
1.06%. These are **first-hit predictions**, not completed DLP
measurements. Keying, Bloom work, memory traffic, base setup, and final
scalar replay are outside the field-call model; the full-size wall rate
and natural relation yield have not been measured.

Public-target [bounded measurements](runs/n83_orbit_k48194_chunk_M31_R20_tstart0_qstart0_b20_h14_rb8.json)
at $2^{28}$ and $2^{31}$ table descriptors found zero exact hits.
At $2^{31}$, the Bloom filter used 5.37 GB, peak RSS was 5.69 GB,
and build, $2^{20}$-representative query, and exact replay took
809.00, 6.39, and 408.66 seconds. Swap-outs stayed flat. Scaling
these rates to the 59-chunk model gives **9.76 days**; the full-size
query throughput is still unmeasured. Twice the expected Bloom-positive
candidate capacity yields an illustrative **7.29 GB** full-chunk
filter-phase peak, not a memory bound. A
[paired worker check](runs/n83_large_orbit_worker_count_paired.json)
on identical $2^{24}$-descriptor inputs found a **1.370× median
query-phase speedup** with 14 workers versus eight, with identical
Bloom-positive and exact-hit counts. Applying that bounded ratio to
the $2^{31}$ filter rate gives **7.35 projected days**, conditional on
the same speedup holding at full size. The
[campaign driver](n83_large_orbit_campaign.py) checks competing start
markers and interrupts its child if swap-outs rise by more than 1,024
pages or system-volume free space falls below 512 MiB. After the repeated
interruptions, it now requires at least 12 GiB system-volume free space
and stable swapouts over a 30-second preflight, and launches via the
checked repository Sage path with runtime information saved before each
new run. A failed chunk's
consumed work remains unknown. Q1051 has `candidate_id: null` until a
natural relation recovers the public target and complete IC work is
accounted for.

The first full M=$2^{31}$, R=$2^{31}$ public-target rectangle was
[interrupted by the system-volume guard](runs/n83_orbit_k48194_chunk_M31_R31_tstart0_qstart0_b20_h14_rb8.json)
after 39 minutes. Swap-outs did not rise, but free space fell below
512 MiB. Its native phase counts are unavailable; this is **not** a
completed zero-hit result. To retain more measured progress per run, the
campaign now splits the same 95.24% modeled query prefix into **118
disjoint R=$2^{30}$ rectangles**. This charges a fresh M=$2^{31}$ table
build and exact replay for every rectangle: **$2^{48.016}$ modeled field
calls** for the 95% prefix, and **8.18 projected days** if the bounded
14-worker speedup transfers. The extra build cost is explicit. Retry
receipts use `.retry<N>.json`; the campaign retains all failed receipts,
and the aggregator gives an upper bound under the same field-call model
while leaving actual failed work and complete end-to-end work unknown.
For this active R=$2^{30}$ plan, the
[first-hit distribution](n83_large_orbit_solve_work.json) reaches 50%
after 27 completed rectangles ($2^{45.888}$ modeled field calls), 90%
after 89 ($2^{47.609}$), and 95% after 117 ($2^{48.003}$). The plan's
118th rectangle raises modeled success to 95.24%. Adding full-rectangle
model upper bounds for all three interrupted attempts gives $2^{48.064}$;
their actual consumed work remains unknown.

The [first full R=$2^{30}$ rectangle](runs/n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json)
completed on the public target with **16,719,837 Bloom positives, all
rejected by exact replay**, and zero verified relations. It measured
803.1 seconds to build the $2^{31}$-descriptor filter, 5,644.4 seconds
for 14-worker queries, and 715.9 seconds for exact replay; peak RSS was
6.42 GB. Its query plus replay interval was **6,360.2 seconds** and
the wrapper wall time was **7,164.3 seconds**. The completed native
field-call model is **$2^{41.133}$**. The
[cumulative receipt](runs/n83_large_orbit_campaign_aggregate.json)
retains three failed attempts as unknown actual work. The second,
[R=$2^{30}$ range starting at $2^{30}$](runs/n83_orbit_k48194_chunk_M31_R30_tstart0_qstart1073741824_b20_h14_rb8.json),
was interrupted after about 31 minutes with no native phase counts or
query yield. The host's swap counter was substantially higher when
inspected later, but the terminal receipt does not identify which guard
fired.
An additional [retry](runs/n83_orbit_k48194_chunk_M31_R30_tstart0_qstart1073741824_b20_h14_rb8.retry1.json)
was interrupted after about 14 seconds with no native phase counts.
The completed rectangle plus all three failures has a **$2^{43.448}$**
structural field-call-model upper bound, not a measured consumed total.
Transferring the first full
rectangle's 7,164.3-second wall time to all 118 rectangles gives
**9.78 days**, a one-sample projection that supersedes the earlier
bounded-rate 8.18-day estimate. Neither projection is a measured full
campaign or complete DLP work.

### Two-table shared-query proposal (Q1052)

Q1052 keeps the same n=83 curve `EC1N83Ckb1h876c2921cb64`,
B=8,000,204 known-log factor-base points, 48,194 folded columns,
enumerated-set digest, and `isogeny: "none"`. Its
[native stage](native_n83_orbit_query_two_shard.cpp) builds two disjoint
table Bloom filters and checks both with each target-query point sum.
The [paired bounded receipt](runs/n83_two_shard_paired_bounded.json)
matched each shard's 3,245 and 3,288 Bloom positives and zero exact
hits to separate one-table runs on identical public-target inputs. With
one query worker and $2^{20}$ descriptors per shard, sharing the query
was **1.729× faster in the query phase** than two separate runs. This
bounded timing was measured while the full Q1051 run shared the host.
The [second-table planted control](runs/n83_two_shard_second_table_planted.json)
found an exact hit and independently replayed its scalar; it is not
natural relation yield.

The [Q1052 screen](n83_two_shard_screen.json) projects 95.24% success
for 59 R=$2^{30}$ query rectangles against two M=$2^{31}$ table
shards. Its explicit field-add/multiply/square boundary is
**$2^{47.049}$ calls**, compared with Q1051's $2^{48.016}$ for the
same model probability. Combining the bounded one-worker shared-query
ratio with the earlier 14-worker calibration projects **5.43 days**;
the two-filter memory illustration is **12.66 GB**. Full-size
two-filter memory, throughput, and natural relation yield are unmeasured,
so Q1052 remains a proposal with `candidate_id: null` and complete solve
work unknown.
The [Q1052 first-hit calculation](n83_two_shard_solve_work.json) charges
whole completed rectangles: median modeled first hit at 14 chunks and
**$2^{44.974}$ stage field calls**, 90% by 45 chunks and
**$2^{46.658}$ calls**, 95% by 59 chunks and **$2^{47.049}$ calls**,
and 99% by 91 chunks and **$2^{47.674}$ calls**. The conditional mean,
given a hit within all 179 full disjoint chunks, is
**$2^{45.469}$ calls**; the model still leaves a 0.0136% no-hit chance
after those chunks. This is a first-hit prediction based on assumed
finite-support relation placement. The measured complete-solve exponent
is **unknown**; these calls exclude keying, Bloom work, base setup, prior
attempts, and independent scalar replay.

| Case | Result | Work unit and status |
| --- | --- | --- |
| n=53 known-log control | Verified one-target DLP in 117.94 s online; $2^{20.739}$ cold pair samples | Measured wall time and logical pair samples; full field-operation count unknown |
| n=83 Q1051 | One full R=$2^{30}$ rectangle completed in 7,164.3 s with zero exact hits; 95% model prefix $2^{48.016}$ | Measured one-rectangle wall time and zero yield; prefix field calls predicted |
| n=83 Q1052 | No natural hit yet; median $2^{44.974}$, 95% $2^{47.049}$ | Predicted native field-call stage only; full-size throughput unmeasured |
| n=83 Q1054 | Planted scalar replay passed; bounded query 1.176× faster at 14 workers; 95% $2^{47.071}$ | Predicted x-only field-call stage; full-size throughput and natural yield unmeasured |
| n=83 Q1055 | M=$2^{20}$ median query 1.053× faster; one M=$2^{28}$ pair gave 1.140× query and 1.054× full native-stage speedups; planted scalar replay passed | Measured bounded stages; reverse-order M=$2^{28}$ repeat interrupted; predicted 95% Bloom bit probes $2^{47.597}$, distinct from field calls |
| n=83 Q1056 | Exact fast-key equality on 1,048,576 field inputs; 1.508× isolated key-kernel and 1.326× paired bounded-query speedups | M=$2^{20}$, R=$2^{22}$ query stage only; full-size rate and relation yield unmeasured |
| n=83 Q1057 | Exact cyclic-gap rotation key; 1.202× slower than Q1056 byte-table key | Negative isolated-kernel result; gap-scanning implementation rejected |
| n=83 Q1058 | Eight disjoint M=$2^{28}$ table shards; 936 future R=$2^{30}$ rectangles model $2^{50.001}$ native field calls | Conditional lower-memory plan only; 54.5 projected query-only days, no natural relation |
| n=83 Q1059 | Q1058 shards with the exact Q1056 fast keyer; planted scalar replay and public-target smoke passed | Same $2^{50.001}$ arithmetic model; 41.1 query-only days if two bounded-rate transfers hold, no natural relation |
| n=83 Q1060 | Q1059 shards with Bloom-positive records in unlinked SSD files; planted replay and small public-target exact outcomes match | Same $2^{50.001}$ arithmetic model; M28/R30 wall time and peak RSS unmeasured, no natural relation |

The [Q1052 chunk runner](run_n83_two_shard_chunk.py) and
[campaign driver](n83_two_shard_campaign.py) retain source hashes,
exact-hit scalar replay, terminal failure receipts, disjoint query ranges,
and the same disk/swap guard. A bounded M=$2^{20}$-per-shard,
R=$2^{14}$ [public-target receipt](runs/n83_two_shard_chunk_M20_R14_tstart0_qstart0_b20_h14_rb8.json)
passed the wrapper checks with zero exact hits. The
[aggregator](aggregate_n83_two_shard_chunks.py) rejects overlapping
completed rectangles and retains unknown failed work with a conservative
field-call-model upper bound. The Q1052 driver checks for any active
Q1051 marker and will not launch a competing full-size search.
`n83_two_shard_campaign.py --calibrate-full-table` was used twice with
the same disk/swap guard to try two full $2^{31}$-descriptor filters
against $2^{24}$ query representatives. The calibration query range is
disjoint from the planned 59-chunk prefix. Neither attempt completed;
full-size Q1052 memory and query rates remain unmeasured.
The [first full-table calibration attempt](runs/n83_two_shard_chunk_M31_R24_tstart0_qstart63350767616_b20_h14_rb8.json)
was interrupted by the swap guard after about nine minutes. Swap-outs
rose by 43,468 pages during the attempt while two separate `kissat`
processes reached about 7 GB combined RSS. Its native phase counts and
actual consumed field work are **unknown**; no query yield was measured.
The [second attempt](runs/n83_two_shard_chunk_M31_R24_tstart0_qstart63350767616_b20_h14_rb8.retry1.json)
also crossed the swap guard, after about 14 minutes while the second
filter was becoming resident. The competing `kissat` jobs had exited
before that attempt. Swap-outs rose by 24,984 pages; native phase counts,
actual consumed field work, and query yield are **unknown**. A single
failed attempt has a full-rectangle structural field-call-model upper
bound of **$2^{37.119}$**. The [first-hit calculation](n83_two_shard_solve_work.json)
includes both failures as a combined **$2^{38.119}$** upper bound;
adding that to Q1052's 95% modeled prefix changes $2^{47.049}$ to
approximately **$2^{47.052}$**. These are model upper bounds, not
measured operation totals. The two-filter search has no demonstrated
full-size completion under this host's guard, so the campaign is paused
in favor of the completed one-filter Q1051 route.

### One-filter two-table stage probe (Q1053)

Q1053 puts both disjoint table shards into one Bloom filter, then uses
one candidate list and exact replays both shards. It has the same curve,
B=8,000,204 base, enumerated-set digest, and `isogeny: "none"` as
Q1052; it remains a proposal with `candidate_id: null`. A
[second-shard planted control](runs/n83_unified_second_table_planted.json)
found one exact hit and independently replayed its scalar. In the
[paired bounded public-target run](runs/n83_unified_paired_bounded.json)
at M=$2^{20}$ per shard and R=$2^{18}$ with one worker, the unified
filter reduced Bloom positives from 6,533 to 3,703, or **43.3%**.
It reduced median query time from 15.273 to 14.861 seconds, a
**1.028×** speedup while Q1051 shared the host. Both variants found
zero exact hits on that ordinary target range. The field-call model is
the same as Q1052 because group arithmetic and exact table passes are
unchanged; full-size memory, parallel throughput, natural yield, and
complete solve work remain unmeasured. The small timing gain does not
yet establish a full-size replacement for the completed Q1051 route.

### Paired-sign x-only query stage (Q1054)

The [Q1054 native kernel](native_n83_orbit_query_signed_x.cpp) shares
the denominator for $P+Z$ and $P-Z$, returning only their x coordinates.
For each pair of signs, it replaces two full point additions with six
field additions, five multiplications, and two squares, or 13 counted
field calls instead of 26. It uses the exact Q1051 curve, public target,
B=8,000,204 base, 48,194 folded columns, and set digest, with
`candidate_id: null` and `isogeny: "none"`. The
[nonzero-offset planted control](runs/n83_signed_x_nonzero_offset_planted.json)
found an exact hit and independently replayed its scalar. The checked
[Sage runtime receipt](runs/n83_signed_x_runtime_info.json) was saved
before the run.

The [ABBA paired bounded public-target comparison](runs/n83_signed_x_paired_bounded.json)
used one worker, M=$2^{20}$, R=$2^{18}$, and identical table and query
ranges. Both variants produced 3,311 Bloom positives, zero exact hits,
and identical identity counts. Original query times were 8.10–8.16 s;
paired-sign times were 6.95–7.16 s. The median query-phase speedup was
**1.152×**, with paired ratios **1.139–1.166×**. These two repetitions
give a range, not a full-size confidence interval.

A second [ABBA paired comparison](runs/n83_signed_x_paired_14worker.json)
used the planned **14 workers**, M=$2^{20}$, and R=$2^{22}$ on the same
public target. Both kernels gave 52,139 Bloom positives and zero exact
hits. Original query times were 14.13–14.39 s and Q1054 times were
12.02–12.23 s: **1.176× median speedup**, with paired ratios
**1.156–1.197×**. Its [Sage runtime receipt](runs/n83_signed_x_14worker_runtime_info.json)
was saved before the run. The filter is still much smaller than the
full $2^{31}$-descriptor filter, so these timings do not measure
full-size throughput.

The [conditional Q1054 screen](n83_signed_x_screen.json) retains
Q1051's finite-support first-hit probabilities. It predicts
**$2^{47.071}$ native field calls** for 118 completed rectangles and
95.24% modeled success, versus Q1051's $2^{48.016}$. Applying the
bounded 14-worker query speedup to the first completed full-size Q1051
timing projects **8.63 days** for 118 Q1054 rectangles, conditional on
transfer to a $2^{31}$ filter. For the *current same target*,
one Q1051 rectangle has completed and three attempts failed; charging
their full-rectangle model upper bounds plus 117 future Q1054 rectangles
gives **$2^{47.172}$** field calls. Actual work in the failures, full-size
Q1054 throughput, natural relation yield, and complete DLP work remain
unknown. The checked runtime, planted hit, and bounded speedup do not
establish a full-size solve.

The [Q1054 chunk runner](run_n83_signed_x_chunk.py) completed a bounded
M=$2^{20}$, R=$2^{14}$ public-target smoke with zero exact hits and
[retained its terminal receipt](runs/n83_signed_x_k48194_chunk_M20_R14_tstart0_qstart0_b20_h14_rb8.json).
The [campaign driver](n83_signed_x_campaign.py) schedules the 117
remaining disjoint R=$2^{30}$ ranges after Q1051's completed range. It
saves a checked Sage runtime receipt before each launch and records
separate guard telemetry if it interrupts a child. The full-size launch
gate currently refuses to start: system-volume free space is below its
12 GiB minimum, and this host recently accumulated heavy swap-outs.
No full-size Q1054 rate or relation has been measured.

### Bloom hash-count stage screen (Q1055)

The [Q1055 paired run](runs/n83_signed_x_hashes_paired.json) kept the
Q1054 signed-x kernel, exact n=83 curve, public target, 8,000,204-point
base, 48,194 folded columns, base digest, M=$2^{20}$ table, R=$2^{22}$
query, and 14 workers fixed. It ran hash counts 14, 8, 10, 12, 12, 10,
8, 14. The [runtime receipt](runs/n83_signed_x_hashes_runtime_info.json)
was saved before the measured workload. Each hash count found zero exact
hits. The 10-hash variant produced 63,442 Bloom positives, versus 52,139
with 14 hashes, and median query times of 10.957 versus 11.542 seconds.
Its **1.053× bounded query speedup** agrees with a **1.050× process CPU
speedup**. The latter includes launch and setup, so it is a diagnostic,
not one-target online time. The 10-hash query range was 10.764–11.150 s,
and the 14-hash range was 10.696–12.389 s; their overlap prevents a robust
full-size wall-time gain on this busy host. Eight hashes used less CPU
but produced 96,083 positives and only a 1.017× median wall gain.

The [10-hash planted control](runs/n83_signed_x_hash10_planted.json)
found the same nonzero-offset exact hit as Q1054 and independently replayed
the scalar. Its [separate runtime receipt](runs/n83_signed_x_hash10_runtime_info.json)
was saved before that job. It is a correctness check, not natural relation yield. The
[work screen](n83_signed_x_hashes_screen.json) counts one Bloom bit probe
per hash insertion or lookup: $h(M+166R)$ per full rectangle. Under
Q1051's heuristic 118-rectangle prefix, this is **$2^{47.597}$ probes**
at ten hashes versus **$2^{48.082}$ probes** at fourteen. The Q1054
field-call model remains **$2^{47.071}$** in either case. Bloom probes,
field calls, memory traffic, and scalar recovery have not been calibrated
into one equivalent work unit. Scaling the bounded false-positive ratio
to the full filter would suggest about 20.3 million positives for ten
hashes versus the 16.7 million measured in Q1051; this is a prediction,
not a full-size memory measurement. Ten hashes is a provisional setting
for a guarded full-filter calibration. Q1054's 14-hash campaign remains
unchanged until that calibration and an ordinary n=83 relation are measured.
The [Q1055 public-target chunk smoke](runs/n83_signed_x_q1055_k48194_chunk_M20_R14_tstart0_qstart0_b20_h10_rb8.json)
completed M=$2^{20}$, R=$2^{14}$ with zero exact hits; its
[runtime receipt](runs/n83_signed_x_q1055_smoke_runtime_info.json) was
saved before launch. The shared chunk runner now requires Q1054 to use
14 hashes and Q1055 to use 10, so future receipts cannot silently assign
the 10-hash setting to Q1054.

A [guarded larger-filter comparison](runs/n83_signed_x_m28_hashes_paired.json)
used M=$2^{28}$, R=$2^{24}$, 14 workers, the same base and public target,
and a query range starting at $2^{30}$, beyond the completed Q1051 range.
One 14/10-hash pair completed with zero exact hits in both runs and no
swap-out growth. Query times were **89.623 s** and **78.627 s**
(**1.140×**); build plus query plus exact replay took **239.925 s** and
**227.663 s** (**1.054×**). Bloom positives rose from 261,727 to
304,118; peak RSS rose from 1.016 to 1.020 GB. The [M28 screen](n83_signed_x_m28_hashes_screen.json)
keeps these measured phase costs separate from its projection: applying
the 1.162× positive ratio to Q1051's full-filter count would suggest
19.43 million positives at ten hashes, but full-filter memory and rate
have not been measured.

The next 10-hash repetition was [interrupted by the swap guard](runs/n83_signed_x_m28_hash10_R24_qstart1073741824_abba3.json)
after 11,132 additional swap-out pages. It has no native phase counts;
its actual work and hit status are unknown. The final 14-hash repetition
did not start. This leaves a single completed M28 pair, not a robust
large-filter speedup estimate or an n=83 natural-relation measurement.
Charging both completed M28 calibrations and a full-rectangle structural
upper model for the interruption to the existing same-target Q1051 work
and 117 hypothetical future full rectangles gives **$2^{47.173}$ modeled
native field calls**. It is neither measured consumed work nor a complete
operation-equivalent DLP cost.

### Byte-table quotient-key conversion (Q1056)

The optional `ECC2K83_FAST_KEYER` path in [the native pair source](native_n83_pairs.cpp)
uses a 44 KiB byte lookup to convert polynomial-basis coordinates to the
Frobenius-cycle bit vector. The minimum-rotation key, group arithmetic,
Bloom filter, and exact replay are unchanged. The default build retains
the original conversion. The [standalone control](runs/n83_fast_keyer_microbenchmark.json)
matched all 1,048,576 fast keys to the original method and checked 1,024
Frobenius images. Four passes per variant measured median **96.009 ms**
for the reference and **63.665 ms** for the lookup path over 1,048,576
keys, a **1.508× isolated key-kernel speedup**. The reference range was
95.199–96.065 ms; the fast range was 63.230–63.736 ms. The checked
[Sage runtime receipt](runs/n83_fast_keyer_runtime_info.json) was saved
before measurement.

The [guarded paired query benchmark](runs/n83_fast_keyer_paired.json)
subsequently completed on the same M=$2^{20}$, R=$2^{22}$, 14-worker
public-target workload as Q1054, after a fresh
[checked-Sage runtime receipt](runs/n83_fast_keyer_paired_runtime_info.json).
The ABBA order gave reference query times 22.864 and 25.518 s, and fast
times 18.840 and 17.640 s. The medians are **24.191 versus 18.240 s**,
a **1.326× bounded-query speedup**; median build + query + exact replay
was 24.836 versus 18.673 s, a **1.330× native-stage speedup**. Every run
had the same 52,139 Bloom positives, zero exact hits, and zero swap-out
growth during its timed execution. Peak RSS was 328.1–329.2 MB. An earlier
[preflight](runs/n83_fast_keyer_paired_preflight.json) had refused to
start with 1.404 GB free against the 2 GiB gate; it recorded no native
work. The Q1054 campaign checks native pair and Bloom-core source digests
for each future full-size receipt. Full M=$2^{31}$ filter performance,
natural relation yield, and complete DLP work remain unmeasured.

The separate Q1057 [cyclic-gap screen](runs/n83_gap_rotation_screen.json)
tested a minimum-rotation shortcut: a binary cyclic key must begin at a
longest zero run. Its [standalone control](bench_n83_gap_rotation.cpp)
matched the original key on 1,048,576 field inputs, all 3,403 two-bit
patterns, and 1,024 Frobenius images. Four passes per variant measured
63.665 ms for Q1056's byte-table key and 76.521 ms with gap scanning.
This implementation is **1.202× slower**, so it is not enabled in the
native query solver. The result rejects this implementation's speed claim;
it is not evidence about natural n=83 relation yield.

### Disjoint low-memory table shards (Q1058)

The [Q1058 screen](n83_low_memory_screen.json) keeps the same exact
`EC1N83Ckb1h876c2921cb64` curve, public target, and factor base:
**B=8,000,204** distinct usable points before folding, 48,194 signed
Frobenius columns, set digest
`7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02`.
It uses Q1054's paired-sign x-only arithmetic and Q1055's ten-hash Bloom
filter. Eight disjoint M=$2^{28}$ table shards cover the same M=$2^{31}$
descriptor range as Q1051. Its query ranges are also disjoint. The first
R=$2^{30}$ range was already completed against the entire M=$2^{31}$ table
under Q1051 with zero exact hits, so Q1058 schedules only the remaining
117 query ranges per shard: **936 future rectangles**. The two completed
M28/R24 calibrations overlap one of those future ranges and do not increase
the distinct modeled coverage.

| Table size per rectangle | Table shards | Future rectangles | Future native field-call model | Filter bit array, ideal |
| ---: | ---: | ---: | ---: | ---: |
| $2^{28}$ | 8 | 936 | $2^{50.001}$ | 0.625 GiB |
| $2^{29}$ | 4 | 468 | $2^{49.009}$ | 1.25 GiB |
| $2^{30}$ | 2 | 234 | $2^{48.026}$ | 2.5 GiB |
| $2^{31}$ | 1 | 117 | $2^{47.059}$ | 5 GiB |

All four schedules have the same **95.24% unconditional** success probability
under Q1051's finite-support heuristic. Given the completed first range's
zero hit, the model predicts **95.11% conditional** success over the remaining
ranges. This is a model of at least one four-point decomposition, not a
measured relation yield. For M28, the Q1051 completed rectangle plus future
rectangles is $2^{50.004}$ modeled calls. Adding full-rectangle structural
upper proxies for three prior Q1051 interruptions and the M28 interrupted
calibration, along with the two completed M28 calibration call models, gives
the [selected-receipt accounting field](n83_low_memory_screen.json),
**$2^{50.016}$ modeled native field calls**. Other same-target research
trials are omitted, and actual interrupted work is unknown. This number
is not a bound on all historical work; none of these exponents is complete
solve work.

The single completed M28/R24 ten-hash run measured 1.020 GB peak RSS and
78.627 seconds of query time. Scaling that query rate to R=$2^{30}$ gives
**54.5 days of query time alone** for 936 rectangles on the same 14-worker
host; full-size replay and wall time remain unmeasured. Scaling only the
observed candidate-vector capacity gives an **illustrative 1.71 GB peak**
for one M28/R30 rectangle. This is not a memory bound; full-size candidate
tables, allocation, and swapping could cost more. The
[guarded campaign driver](n83_low_memory_campaign.py) requires 4 GiB free
on the system volume and low swap-out growth before launching one rectangle.
It retains failed receipts with unknown work and requires an explicit
`--retry-failed` after inspection; it will not silently retry or switch
to a variant whose full-size rectangles have already run.
The system volume was below the launch guard during preflight, so no Q1058 full
rectangle has been launched. `Q1058` has `candidate_id: null`,
`isogeny: "none"`, zero measured natural relations, and no IC DLP or rho
speedup claim.

### Fast-keyer low-memory variant (Q1059)

[Q1059](n83_fast_low_memory_screen.json) uses the same curve, target,
factor-base digest, actual B, 48,194 folded columns, and disjoint Q1058
table/query ranges. It compiles the Q1056 exact byte-table keyer with the
Q1055 ten-hash filter. The fast-keyer runner flag is accepted for the
named Q1059 and Q1060 stages, and [the guarded driver](n83_low_memory_campaign.py)
refuses to switch variants after one has completed a full rectangle, so it
cannot silently duplicate coverage. The
[nonzero-offset planted control](runs/n83_fast_low_memory_planted.json)
found the same exact hit as Q1055 and independently replayed its scalar.
A [paired small public-target check](runs/n83_low_memory_smoke_paired.json)
then exercised Q1058 and Q1059 on identical M=$2^{20}$, R=$2^{14}$
positions. The native outcomes matched exactly: 247 Bloom positives and
zero exact hits in both. The planted and public-target runs have
checked-Sage runtime receipts. The small rectangle is a correctness
control, not a full-size speed comparison.

Q1059 has Q1058's **$2^{50.001}$ future native field-call model** and
**95.11% conditional finite-support success probability**. Dividing
Q1058's 54.5 projected query-only days by Q1056's measured 1.326×
M=$2^{20}$, R=$2^{22}$ 14-hash speedup gives **41.1 query-only days**,
conditional on *both* the M28/R24-to-R30 rate and the M20/14-hash-to-M28/10-hash
speedup transfers. The latter transfer has not been measured. The full
M28/R30 memory, wall time, natural relation yield, and complete operation
equivalent remain unknown. `Q1059` retains `candidate_id: null` and
`isogeny: "none"`.

### Spilled-candidate low-memory variant (Q1060)

Q1060 keeps Q1059's exact curve, target, factor base, ten-hash filter,
fast keyer, and disjoint table/query schedule. Its separate
[native kernel](native_n83_orbit_query_spill.cpp) writes Bloom-positive
query records to unlinked files on the SSD, then reads them for exact
table replay. The files close and disappear when the process exits. Its
[checked-Sage controls](runs/n83_spill_controls.json) matched Q1059's
planted hit and independently replayed the scalar; the public-target
M=$2^{20}$, R=$2^{14}$ outputs also matched exactly, with 247 Bloom
positives and zero exact hits. The [named runner smoke](runs/n83_spill_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json)
recorded the spill mode and zero exact hits. These are correctness
controls, not natural relation yield.

The [Q1060 screen](n83_spill_low_memory_screen.json) retains the
**$2^{50.001}$ future native field-call model** and Q1059's **95.11%**
conditional finite-support success model. If the single M28/R24
ten-hash positive rate transfers to R30, one rectangle would spill
about **467 MB** of candidate records and need about **779 MB** of
exact-table slots. A base-memory calculation suggests **1.12 GB** peak
if releasing the Bloom filter returns its pages to the OS, or **1.79 GB**
if those pages remain resident. These are scenarios, not bounds; M28/R30
RSS, spill I/O cost, and wall time have not been measured. The Q1060
[campaign driver](n83_low_memory_campaign.py) requires 1.5 GiB free on
the system volume, 1 GiB free on the spill volume, and stable swap-outs.
`--spill-dir` selects an absolute existing directory on the runner host;
the local default is `/Volumes/SSD990/llm/tmp`.
The first [full Q1060 M28/R30 rectangle](runs/n83_spill_lowmem_k48194_chunk_M28_R30_tstart0_qstart1073741824_b20_h10_rb8.json)
finished on 2026-09-29 at 22:02 UTC. It tested $2^{28}$ table descriptors
against $2^{30}$ query representatives on the frozen public target. It
measured 19,454,731 Bloom positives, **zero exact hits**, a 466.9 MB
candidate spill, 1.773 GB peak RSS, 5,429.44 s query time, 87.74 s
exact replay, and 5,517.18 s target online time. The full native
subprocess took 5,623.69 s including the 106.00 s table build. The
declared arithmetic boundary gives $2^{40.131}$ native field calls for
this rectangle; it does not count keying, Bloom work, memory or SSD
traffic, or historical failed attempts.

The reproducible [post-run work report](n83_q1060_full_rectangle_work.json)
checks the receipt and original factor-base identity, then applies the
*frozen finite-support heuristic* after both the Q1051 and first Q1060
zero-hit rectangles. Conditional on a hit within the remaining plan,
its expected completed-rectangle arithmetic is $2^{48.169}$ field
calls including those two completed rectangles. Its modeled median
first-hit point is $2^{47.879}$ and its 95% first-hit point is
$2^{49.995}$; the plan ends at $2^{50.004}$, with 4.90% modeled
no-hit probability. These are predictions under a random-base
placement model, not measured natural relation yield or complete-solve
work. Transferring the single measured subprocess rate to all 935
remaining rectangles gives about 60.86 days, also only a projection.
The next disjoint rectangle starts at table descriptor $2^{28}$ and the
same query range. That [second full Q1060 receipt](runs/n83_spill_lowmem_k48194_chunk_M28_R30_tstart268435456_qstart1073741824_b20_h10_rb8.json)
has now completed with 19,465,369 Bloom positives, **zero exact hits**,
467.17 MB candidate spill, 1.773 GB peak RSS, and 4,973.11 s target
online time. Both completed shards are charged in the current Q1062
coverage-aware work report. Q1060 retains `candidate_id: null`,
`isogeny: "none"`, and no measured natural relation or complete IC DLP.

### Portable CPU quotient stage (Q1061)

Q1061 keeps Q1060's frozen curve, target, factor base, signed-x key,
ten-hash Bloom filter, exact replay, and SSD candidate spool. Its
[separate native source](native_n83_orbit_query_spill_portable.cpp) selects
ARM PMULL, x86 PCLMUL, or a generic carryless-multiply loop at compile
time. The [CPU controls](verify_n83_portable_controls.py) matched every
frozen Q1060 exact outcome on this ARM host and in both x86 backends
under Rosetta. Each planted run produced the same exact hit and an
independently replayed scalar. Each small public-target run produced
247 Bloom positives and zero exact hits. Rosetta is a translation check,
not physical x86 performance evidence. The
[x86 CI workflow](../../.github/workflows/n83-portable-quotient-controls.yml)
runs both backends and one bounded public-target chunk on an x64 Linux
runner. Its corrected [physical x86 receipt](runs/n83_portable_physical_x86_ci_run36627669403.json)
archives the successful PCLMUL and generic controls, compiler and OS,
source and binary hashes, and the bounded public-target stage result.

The [Q1061 screen](n83_portable_cpu_stage_screen.json) and
[M24/R20 receipt](runs/n83_portable_q1061_k48194_chunk_M24_R20_tstart0_qstart1073741824_b20_h10_rb8.json)
record one measured n=83 ARM stage chunk: 16,777,216 table descriptors,
1,048,576 query representatives, 18,675 Bloom positives, zero exact
hits, and about 366 MB peak RSS. The native field-call model for that
chunk is about $2^{30.58}$; this is a stage arithmetic count, not a
complete DLP cost. Q1061's prospective 936-rectangle field-call model
remains $2^{50.001}$, conditional on the Q1060 schedule. It excludes
keying, Bloom and spill I/O, memory traffic, all historical interrupted
attempts, verification, and the possibility of finding no relation.
Q1060 now supplies one full M28/R30 wall-time measurement. Natural
relation yield and complete-solve work in $2^x$ units remain unknown.

The first physical x86 CI run passed exact controls but exposed a Linux
RSS unit error: `ru_maxrss` was labeled as bytes without conversion
from KiB. The separate portable source now converts that field, and
round-two controls and stage receipts retain their own source hashes.
The round-two M24/R20 run overlapped the full Q1060 run, so its wall
time is retained as a stage record but is not used for an isolated
performance comparison. The corrected physical x86 CI run passed and
checked that peak RSS is at least the allocated Bloom-filter size.

The current source revision reuses the pair-addition and signed-x scratch
vectors for every worker. The preceding source allocated those vectors
on every representative batch; an R30 rectangle has $2^{27}$ batches
at batch size eight. This eliminates 806,879,232 repeated vector
allocations across one modeled M28/R30 query, build, and exact replay.
ARM, translated x86, and native x86 exact controls still match the
frozen Q1060 outputs and planted scalar replay. The
[native x86 ABBA receipt](runs/n83_portable_scratch_x86_ci_36629800449.json)
compares the round-two and scratch-reuse sources on one M24/R20
workload: query ratios (old/new) were 1.0100 and 1.0050, median
**1.0075×**. The two positive ratios are a small stage result, with
full-size and verified-target speedups unmeasured. The structural
field-call model is unchanged.

Q1061 is a stage proposal with `candidate_id: null` and `run_id: null`.
Its receipts retain the canonical field and curve record under
`EC1N83Ckb1h876c2921cb64`, actual usable factor-base count
`B=8000204` before folding, the 48,194 signed-Frobenius columns,
the enumerated-set digest, and `isogeny: "none"`. No volcano level or
isogeny route is asserted. The native-only
[chunk runner](run_n83_portable_chunk.py) uses pure Python verification
and records failed attempts with unknown work. It requires at least
1 GiB free on the candidate spill volume and never overwrites a
terminal receipt.

### Full-filter spilled-candidate route (Q1062)

Q1062 reuses Q1060's frozen native signed-x, fast-keyer, ten-hash Bloom,
SSD-spill, and exact-replay source. Its [separately named runner](run_n83_full_spill_chunk.py)
uses a full M=$2^{31}$ table filter against each R=$2^{30}$ query range.
That covers all eight Q1060 table shards in one query pass. The
[bounded checked-Sage control](runs/n83_full_spill_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.cpu_v2.json)
exactly matched Q1060's same-input outcome: 247 Bloom positives, zero
exact hits, and 5,928 candidate-spill bytes. Its runner also records
native child user and system CPU seconds, separately from wall time and
Python scalar verification. The second control receipt freezes a wrapper
that also records a monotonic native-subprocess elapsed interval and an
explicit null run ID on failed attempts; a synthetic native failure
confirmed these fields and start-marker cleanup. Q1062's M31/R30 memory,
wall time, and natural relation yield are not measured.

The [Q1062 screen](n83_full_spill_screen.json) gives $2^{40.188}$
modeled native field calls per full range and $2^{47.059}$ for the 117
ranges after Q1051's completed first range. Adding the completed Q1051
field-call model gives $2^{47.082}$. The frozen finite-support heuristic
predicts 95.11% success conditional on Q1051's first zero-hit range.
The two completed Q1060 M28 shards overlap Q1062's first full
range; they remain separately charged historical work. The frozen
Q1062 screen predates the second shard; the current work report below
reconciles both zero-hit terminal receipts. Interrupted historical
attempts also retain unknown actual work. None of these figures is a
complete measured DLP cost.

The [coverage-aware work report](n83_full_spill_work.json) scans
completed terminal receipts and counts M28-by-R30 shard-range cells in
their union. With Q1051's first range and two Q1060 shards completed,
it finds ten cells. The frozen model predicts a first hit after 33.16 additional
Q1062 full ranges on average *conditional on a hit within the plan*.
That is $2^{45.398}$ selected-route native field calls including the
three completed rectangles; the 95% point is $2^{47.105}$, with 4.92%
modeled no-hit probability at plan end. These estimates are updated by
rerunning the report after each terminal receipt. They omit failed
attempts, other same-target research work, keying, Bloom operations,
SSD traffic, and scalar replay, so `complete_solve_work_log2` remains
`null`.

The [identity contract](n83_identity_contract.py) recomputes the curve ID
from canonical sorted-key field/curve JSON, verifies the known-log base
artifact and the actual pre-folding point count, and requires the exact
field, curve, base, target, and absent-isogeny records in every completed
or failed receipt used by the Q1062 campaign and work report. These are
proposal-stage records: `candidate_id` and `run_id` remain null. The
campaign status and work report include the contract source hash.

The [independent Sage receipt verifier](verify_n83_quotient_receipt_sage.py)
rebuilds four factor-base points and their signed-Frobenius logs from the
archived key/log artifact. It converts the type-II normal-basis coordinates
to Sage's polynomial basis, checks each point against the generator, adds
the four points, and replays the recovered scalar against the receipt's
target. Its [planted control](runs/n83_sage_planted_relation_verify_v2.json)
passes all four-point and scalar checks, while the
[public zero-hit control](runs/n83_sage_public_zero_receipt_verify.json)
reports no verified relation. A one-unit change to the planted recovered
scalar was rejected at the factor-base-log sum assertion. Both controls
used the checked [Sage runtime](runs/n83_sage_relation_verify_runtime_info.json).
The planted control is a correctness check, not a natural-relation yield
measurement. A future natural public-target certificate must pass this
verifier before its DLP is counted independently verified.
The same verifier also accepted an existing
[portable Q1061 public zero-hit receipt](runs/n83_sage_portable_q1061_zero_receipt_verify.json),
and a [physical x86 Q1061 public zero-hit receipt](runs/n83_sage_physical_x86_zero_receipt_verify.json),
confirming that an x86 segment artifact can use the same independent
Sage replay path. Neither bounded receipt found a relation.

The [guarded Q1062 campaign](n83_full_spill_campaign.py) inspects all
117 named full ranges, refuses a competing n=83 start marker or an
already verified Q1060 scalar, and requires 10 GiB of system-volume
headroom, 1 GiB on the spill volume, and stable swap-outs before one
full-range launch. A failed range requires an explicit retry and keeps
its unknown actual work. The [one-shot handoff](n83_full_spill_handoff.py)
waited for the second Q1060 rectangle and attempted the first Q1062
range after its exact zero-hit receipt and cleared start marker. The
original 12 GiB system-volume gate refused that attempt at 12.075 GB
free, before any full-size Q1062 process started. The revised 10 GiB
launch gate is documented in the [resource decision](n83_full_spill_guard_revision.json):
Q1051's measured M31 peak was 6.42 GB, the host reports 48 GiB of
physical memory with 56% free, and Q1060 produced no additional
swap-outs. The 4 GiB running stop, spill-space, and swap-growth guards
are unchanged. This does not establish Q1062 full-size feasibility. Q1062
retains the exact field and curve
`EC1N83Ckb1h876c2921cb64`, B=8,000,204 actual usable points before
folding, 48,194 signed-Frobenius columns, the enumerated-set digest,
`isogeny: "none"`, and `candidate_id: null`. No natural relation or
complete IC DLP is claimed.

The [bounded sequential supervisor](n83_full_spill_supervisor.py) can
advance up to a declared number of Q1062 ranges, one guarded campaign
invocation at a time. Its default mode only inspects state. In run mode
it writes a durable report and log before launching, records every
terminal receipt hash, and stops on a verified DLP, an unverified exact
hit, a failed attempt, a resource refusal, a competing run, or the
declared limit. It does not retry failed ranges or clear start markers.
Each child still runs through the checked Sage launcher and saves a
separate runtime-info receipt before the measured work. The first full
Q1062 range started but was stopped by the 4-GiB system-volume guard.
Its [failed terminal receipt](runs/n83_full_spill_k48194_chunk_M31_R30_tstart0_qstart1073741824_b20_h10_rb8.json)
records 2,431.79 native wall seconds and 18,534.24 child CPU seconds;
the [guard receipt](runs/n83_full_spill_k48194_chunk_M31_R30_tstart0_qstart1073741824_b20_h10_rb8.guard.json)
records system free space falling from 12.10 GB to 3.73 GB with no
additional swap-outs. Native phase counts and actual field calls are
unknown. The attempt supplies no natural-relation result or completed
range coverage. The [validated followthrough](n83_full_spill_followthrough.py)
waits for its terminal receipt and clears no marker. It stops on a failed
run, unverified exact hit, verified DLP, identity/source/parameter mismatch,
or a first-range peak over 10 GiB. A zero-hit terminal receipt passing
those checks starts the supervisor for at most the remaining 116 ranges;
every later range still gets the one-range resource preflight and guard.
The followthrough has synthetic controls for all five stop/continue
outcomes. It correctly stopped on this failed first attempt. A retry
requires explicit `--retry-failed` and stable resource headroom.

The [segmented Q1062 fallback](n83_full_spill_segment_campaign.py) uses
the unchanged checked-Sage runner and native kernel with eight disjoint
$R=2^{27}$ query segments in each original $R=2^{30}$ range. It retains
the same $M=2^{31}$ table, exact replay, resource guards, target, and
factor base. Each segment has its own terminal receipt, so an interrupted
later segment does not erase earlier completed coverage. The
[coverage-aware screen](n83_full_spill_segment_work.json) includes the
completed Q1051 and Q1060 rectangles, the completed Q1061 x86 segment,
and the failed Q1062 attempt, without assigning the failed attempt field
calls or coverage. The completed receipts occupy 86 of 7,552 disjoint
$M=2^{28}$ by $R=2^{27}$ cells and carry $2^{42.192}$ modeled native
field calls. The frozen heuristic gives 95.07% conditional success over
the remaining support; it predicts 261.46 more segments given a hit
within the plan, or $2^{45.742}$ selected-route native field calls. The
95% first-hit point is 931 additional segments and $2^{47.482}$ calls.
Rebuilding the table eight
times per original range costs 1.314 times the original full-range
field-call model. These are predictions, not relation yield or complete
solve work. No Q1062 full-size segment has run. The fallback remains
Q1062 with `candidate_id: null`; its receipt records the changed query
shape.

The default command below only inspects the 935-segment plan. The guarded
run command is appropriate only after system-volume free space is stably
above 10 GiB; it explicitly acknowledges the archived failed full range.
Both commands use the required checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-pair-claw-20260929/n83_full_spill_segment_campaign.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-pair-claw-20260929/n83_full_spill_segment_campaign.py --run-next --acknowledge-failed-full-range
```

The [physical x86 segment workflow](../../.github/workflows/n83-portable-quotient-segment.yml)
provides one independently hosted $M=2^{31}$, $R=2^{27}$ attempt using
Q1061's already controlled portable PCLMUL implementation. It records
the host, compiler, available memory and disk; refuses inadequate
resources; runs a bounded same-host control; and uploads a terminal or
failure artifact. Its receipt belongs to Q1061, so any completed result
must be reconciled by exact query/table coverage before being combined
with the Q1062 work report. A natural hit must also pass the independent
Sage relation verifier. The first full-size x86 segment is recorded below.
The [CI artifact ingester](n83_portable_ci_ingest.py) checks the exact
field, curve, base, target, source hashes, backend, host preflight, and
terminal status before copying an uploaded receipt into the local run
ledger. After a successful host preflight and bounded control, it
preserves a failed or incomplete full-size attempt as such; a native
verified hit still needs separate Sage replay before a complete DLP claim.
Host preflight and bounded-control failures are archived with explicit
statuses and no query coverage. The ingester's `--archive-root` option
allows isolated receipt checks without adding synthetic runs to the ledger.
The segmented work report and local campaign inspector read archived
Q1061 CI bundles, count completed query coverage once across Q1061 and
Q1062, and stop local progression on an exact hit awaiting that replay.

The [physical x86 run 36663733518](https://github.com/aburan28/cryptanalysis/actions/runs/36663733518)
completed its $M=2^{31}$, $R=2^{27}$ public-target segment on an AMD
EPYC 7763 host. Its [archived receipt](runs/n83_portable_q1061_M31_R27_ci_36663733518/full.json)
records 22,280,142,848 lifted query pairs, 2,436,870 Bloom positives,
zero exact hits, 58.48 MB of candidate spill, and 5.69 GB peak RSS.
The target-dependent query plus exact replay took 2,904.70 s; the full
segment, including reusable table construction, took 3,733.77 s.
The [independent checked-Sage replay](runs/n83_portable_q1061_M31_R27_ci_36663733518/sage_verify.json)
accepted its exact curve/base/target identity and recorded zero natural
relations. The workflow's final receipt-check step failed because its
original code looked for the base digest at the wrong JSON level; the
full computation and artifact upload succeeded, and the check is fixed
in this PR. The corrected assertions pass against the archived control
and full receipts. The segment contributes six new coverage cells because the
first two table shards overlapped completed Q1060 work. Extrapolating
3,733.77 s across the heuristic's 261.46 expected additional segments
gives 11.30 serial host-days **only if** this single x86 segment's time
transfers to every later one; this is not a measured solve time. The
native field-call model is $2^{37.582}$ for this completed segment;
complete operation-equivalent work remains unknown.

For that x86 segment, table build and the full-table exact replay took
828.50 s and 809.06 s, respectively: 43.9% of full wall time. The
next disjoint four $R=2^{27}$ query segments start at 1,207,959,552.
The portable workflow now groups them into one $R=2^{29}$ call, so its
native kernel builds and replays the same $M=2^{31}$ table once for the
four-segment group. The [coverage ledger](n83_full_spill_segment_work.py)
accepts both $R=2^{27}$ and aligned $R=2^{29}$ CI receipts and expands a
completed group into four disjoint cells. Its native field-call model
for this group is 654,554,693,632 calls, 79.5% of four separate calls.
The prior linear-query forecast was 2.78 hours versus 4.15 hours for
four separate runs; the completed grouped wall time was 2.77 hours.
After the completed M32 zero-hit result below, the
[work report](n83_full_spill_segment_work.json) schedules 227 prospective
$R=2^{29}$ groups and five $R=2^{27}$ singles. Its frozen-heuristic
first-hit estimate, conditional on a hit by plan end, is 68.56 additional
grouped calls and $2^{45.547}$ selected-route native field calls. The
conditional hit probability by the finite plan end is now 94.716%, so
the 95% first-hit quantile is beyond that plan and remains null. The
extra M32 table cells are recorded but omitted from this conservative
future-hit projection. Group boundaries
charge an entire call even if a relation would first occur within it.
These are prospective arithmetic models, distinct from the measured
R27 and R29 x86 segment timings.

The [eight-job physical x86 wave plan](n83_portable_wave_plan.json)
reached its activation gate after the first grouped run's zero-hit
terminal receipt and independent checked-Sage replay. Its
[workflow](../../.github/workflows/n83-portable-quotient-wave.yml) is
enabled only for this PR branch; failed or exact-hit first-group receipts
would have kept it inactive.
It selects two $R=2^{29}$ groups in each of four later, disjoint $R=2^{30}$
ranges, for 256 new grid cells if all jobs finish. The declared wave cost
is $2^{42.252}$ native field calls and its frozen-heuristic probability of
at least one hit, conditional on archived zero-hit coverage, is 9.97%.
Neither is a measured solve result. The artifact ingester's `--matrix-job`
option gives each job a separate immutable bundle under the shared GitHub
run ID; the coverage ledger will charge overlapping or failed work only
according to terminal receipts. Four jobs later completed with zero hits
and four queued jobs were cancelled before starting, as documented below.
Any exact hit in a wave job requires independent Sage replay before it can
count as a relation or DLP.

The [first grouped x86 run 36669737583](https://github.com/aburan28/cryptanalysis/actions/runs/36669737583)
completed its $M=2^{31}$, $R=2^{29}$ rectangle at query start
1,207,959,552. Its [terminal receipt](runs/n83_portable_q1061_M31_R29_ci_36669737583/full.json)
records 89,120,571,392 lifted query pairs, 9,739,284 Bloom positives,
zero exact hits, 233.74 MB of candidate spill, and 5.69 GB peak RSS.
Target-dependent query plus exact replay took 9,152.57 s; full segment
wall time including reusable table construction was 9,974.55 s.
The [independent checked-Sage replay](runs/n83_portable_q1061_M31_R29_ci_36669737583/sage_verify.json)
accepted the exact curve, base, and public target and found zero verified
natural relations. The coverage ledger credits 24 new $M=2^{28}$ by
$R=2^{27}$ cells after overlap with previously completed table shards.
Before the later M32 run, completed selected-route work was $2^{42.369}$
modeled native field calls; complete solve work remained unknown. The
frozen [wave plan](n83_portable_wave_plan.json)
is ready after this terminal zero-hit receipt and Sage replay, and its
one-shot branch-scoped workflow has been enabled for the eight disjoint
grouped jobs. Their prospective $2^{42.252}$ field calls and 9.97%
conditional hit probability remain model values until terminal receipts
are checked.

### Bounded Bloom hash-count screen (Q1063)

The [paired ARM receipt](runs/n83_portable_hash8_vs10_paired.json) uses
the frozen Q1061 native source, public target, curve, base, table/query
schedules, $M=2^{24}$, $R=2^{20}$, four query workers, and a 20-bit-per-key
filter. Only the number of Bloom hashes changes in ABBA order: 10, 8,
8, 10. All four runs gave zero exact hits. Eight hashes raised Bloom
positives from 18,675 to 27,463, while its two paired query-time ratios
were 1.0134 and 1.0074 in favor of eight hashes. The median full native
wall ratio was 1.0283, with individual ratios 1.0511 and 1.0055.
The [checked Sage runtime](runs/n83_portable_hash8_vs10_runtime_info.json)
was captured before the runs. This is a small bounded ARM stage gain with
visible paired variation. It does not alter the native field-call model,
establish physical x86 full-size performance, or produce a natural
relation, so Q1063 remains a proposal and the active campaign keeps ten
hashes.

### Equal-area table/query shape screens (Q1064 and Q1065)

The portable kernel schedules distinct cross-orbit pair descriptors over a
domain of $\binom{48,194}{2}\cdot166$, so $M=2^{32}$ remains well below
that domain. At fixed $MR=2^{60}$, the [field-call model](n83_full_spill_screen.py)
charges $2^{39.252}$ calls for $M=2^{31},R=2^{29}$ and $2^{38.582}$
for $M=2^{32},R=2^{28}$: 37.1% fewer calls in the latter shape.
Its 20-bit-per-key Bloom allocation doubles from about 5 to 10 GiB;
the archived x86 host had 15.4 GB available before its $M=2^{31}$ run.
The completed M32 measurement below resolves full-size feasibility for
one physical AMD EPYC 7763 runner.

Two checked-Sage, ABBA paired ARM screens used the same frozen n83 public
target, factor base, affine schedules, native source, Bloom settings, and
table/query product $2^{44}$. The [4-to-16 ratio receipt](runs/n83_portable_shape_4to16_paired.json)
compares $M=2^{23},R=2^{21}$ with $M=2^{24},R=2^{20}$: the latter's
paired full-wall speedup ratios have median 1.0957. The [16-to-64 ratio
receipt](runs/n83_portable_shape_paired.json) compares $M=2^{24},R=2^{20}$
with $M=2^{25},R=2^{19}$: the latter's median full-wall speedup is
0.8100, despite 9.0% fewer modeled field calls. Table building and
full-table replay rise enough to erase its query saving. All eight
bounded runs had zero exact hits. These ARM measurements favor moving
from a ratio of 4 to 16, then stopping; they do not establish the
full-size x86 speedup or equal natural relation yield. Q1064 and Q1065
remain stage proposals with null candidate/run IDs. The completed physical
x86 $M=2^{31},R=2^{29}$ job and the activated wave retain their frozen shape.

The [Q1065 one-shot x86 plan](n83_m32_shape_plan.json) fixes
$M=2^{32},R=2^{28}$ and query start 6,442,450,944, disjoint from the
completed grouped query and all eight wave jobs. It uses the same
public target and unchanged Q1061 portable kernel. The plan predicts
$2^{38.582}$ native field calls and 1.305% hit probability for this one
rectangle under the frozen quotient-collision heuristic. The 10 GiB
Bloom allocation gave an 11.06 GB RSS forecast by adding its size
increase to one earlier physical x86 peak. The
[one-shot workflow](../../.github/workflows/n83-portable-quotient-shape.yml)
requires at least 13 GiB available memory, runs a bounded same-host
control first, and uploads terminal or failed receipts. The
[Q1065 artifact ingester](n83_m32_ci_ingest.py) checks curve, base,
target, shape, source hashes, terminal status, and host resources before
archiving that artifact. The workflow has no PR trigger and its job is
disabled, so later PR updates cannot repeat the same search.

[Physical x86 run 36673555074](https://github.com/aburan28/cryptanalysis/actions/runs/36673555074)
completed from its frozen checkout. The [terminal receipt](runs/n83_portable_q1065_M32_R28_ci_36673555074/full.json)
records 44,560,285,696 lifted query pairs, 4,869,720 Bloom positives,
zero exact hits, and an 11.06 GB peak RSS. Table build, target query,
and exact replay took 1,653.79 s, 4,196.40 s, and 1,611.66 s;
full subprocess wall time was 7,462.91 s. The same-model physical x86
M31/R29 job took 9,974.55 s on its different runner, so this single
M32/R28 run is 1.337 times faster in full wall time at equal $MR=2^{60}$.
Host-to-host variance is unmeasured. The
[independent checked-Sage replay](runs/n83_portable_q1065_M32_R28_ci_36673555074/sage_verify.json)
accepted the curve, base, target, and zero natural relations. The
[coverage/work ledger](n83_full_spill_segment_work.py) charges all
411,595,440,128 ($2^{38.582}$) modeled native field calls and credits
16 new primary grid cells plus 16 separate extra-table cells. It now
records 126/7,552 primary cells and $2^{42.470}$ completed modeled
field calls. The ledger also sums the measured search work from successful
terminal receipts: 11,274,289,152 table descriptors processed,
4,160,749,568 query representatives, 690,684,428,288 ($2^{39.329}$)
lifted query pairs tested, and 72,685,811 Bloom positives sent to exact
replay. Repeated table/query work is included. The 34,715.84 target-online
seconds are a sum across different hosts, not one continuous elapsed time;
the failed Q1062 attempt has unknown operation counts. A complete DLP and
operation-equivalent solve work remain unknown.

For zero-hit receipts, the Sage verifier checks the archived identity,
subgroup, field conversion, and receipt hash. It independently replays a
four-point witness only when the receipt contains one. The absence of
exact matches in this M32 search rests on the native kernel's complete
exact scan of its Bloom positives; the Sage audit does not rescan them.

### Bounded Bloom density screen (Q1066)

The [paired ARM receipt](runs/n83_portable_bloom16_vs20_paired.json)
uses the same frozen n83 public target, factor base, $M=2^{24}$,
$R=2^{20}$, affine schedules, four workers, and ten Bloom hashes in
ABBA order with 20, 16, 16, and 20 bits per key. The 16-bit filter
raised positives from 18,675 to 93,121 and candidate spill from 0.45
to 2.23 MB. It cut the filter from 42.01 to 33.62 MB. Its two paired
query-time speedup ratios were 1.1212 and 1.0663; the median full-wall
speedup was 1.0509. All four runs had zero exact hits. The
[checked Sage runtime](runs/n83_portable_bloom16_vs20_runtime_info.json)
was captured before the runs. At $M=2^{32}$ the allocation formula
would reduce the filter from about 10 to 8 GiB, but full-size physical
x86 speed, total RSS, and false-positive replay cost remain unmeasured.
Q1066 is a stage proposal with null candidate/run IDs; the live x86
jobs keep their frozen 20-bit filters.

### Disjoint M32 grouped follow-up design (Q1068)

The [frozen Q1068 design](n83_m32_group_followup_plan.json) places an
$M=2^{32},R=2^{29}$ search at query start 6,710,886,400. Its query
interval begins exactly where the completed M32/R28 run ended and stays
clear of all eight planned wave ranges. It retains the exact n=83 curve,
8,000,204-point usable base, 48,194 signed-Frobenius columns, public
target, portable Q1061 kernel, ten Bloom hashes, and `isogeny: "none"`.
The proposal has null candidate/run IDs.

One grouped call models 710,766,755,840 ($2^{39.371}$) native field
calls, 13.66% fewer than two separate M32/R28 calls because it builds
and replays the same table once. Reusing the completed M32 phase times
gives a 3.24-hour full-wall forecast under one table build, twice the
R28 query time, and one exact replay. The frozen quotient-collision
heuristic gives a 2.59% hit probability for this rectangle. The initial design
would have waited for the whole wave. The later
[one-shot launch plan](n83_m32_group_launch_plan.json) selected a
concurrent disjoint run to add coverage while the wave remained active.
[Physical x86 run 36698966100](https://github.com/aburan28/cryptanalysis/actions/runs/36698966100)
started from frozen commit `0647fdcb`, passed its host preflight and
same-host bounded control, and completed the full search with **zero exact
hits** among 9,739,636 Bloom positives. Its archived [receipt and
checked-Sage audit](runs/n83_portable_q1068_M32_R29_ci_36698966100/sage_verify.json)
pin the exact curve, base, target, sources, and absent isogeny. Full
segment wall time was 11,495.48 s (3.19 h), including 1,622.38 s of
target-independent filter setup; target-online query and replay took
9,872.92 s. Peak RSS was 10.30 GiB. The forecast was close in this one
run, while the placement probability remains unvalidated by natural
yield. The workflow was disabled for subsequent PR commits.

The [coverage-aware work ledger](n83_full_spill_segment_work.json) also
projects a distinct future M32/R29 route. After all eight Q1069 wave
receipts and Q1071, it retains 574 completed primary M28-by-R27 cells
and 336 completed extra-table cells, then orders the remaining aligned
R29 rectangles by new coverage. Under the frozen finite-support placement
model, 226 future M32/R29 calls cover the entire M32-by-query domain,
with a 99.633% conditional chance of at least one hit. Conditional on a
hit within that finite plan, the expected first hit is after 38.36
additional calls and $2^{45.292}$ selected-route modeled native field
calls including completed receipts. The median is 27 calls
($2^{44.993}$); the 95% quantile is 117 calls ($2^{46.492}$).
These are **model outputs**, not measured relation yield, elapsed time,
or complete operation-equivalent solve work. The interrupted Q1073 attempt
has unknown arithmetic work and receives no coverage credit.

The work exponent has a fixed boundary in this ledger:

| Quantity | $2^x$ native field calls | Status |
| --- | ---: | --- |
| One complete M32/R29 rectangle | $2^{39.371}$ | Modeled attempt cost, with no hit required |
| Completed disjoint search receipts | $2^{43.847}$ | Modeled calls over measured terminal coverage |
| First hit on the selected M32 route | $2^{45.292}$ | Finite-support expectation, conditional on a hit by plan end |
| Complete one-target IC solve | unknown | No natural n=83 relation or independently verified IC scalar yet |

The n=53 control did recover and independently verify one target in
117.94 seconds online with $2^{20.739}$ logical pair samples across cold
table construction and target search. Q1076 measured its field API call
vector and gives a separately labeled $2^{28.173}$ cold inversion-weight
model; no calibrated common operation total is available. On the exact
n=83 base, the eight completed physical x86 Q1069
M32/R29 rectangles took 9,672.04–12,158.11 seconds of target-online
query and replay each, with zero exact hits; each rectangle models
$2^{39.371}$ native field calls including its reusable table build.
The n=53 sample count, n=83 modeled field calls, and online wall times
have different boundaries and cannot be fitted into a measured n=83
solve exponent.

The field-call boundary counts table construction and replay and the
representative-query point arithmetic. It excludes Bloom/key operations,
memory and disk traffic, failed attempts with unknown operation counts,
base construction, and scalar replay. These omissions prevent the
conditional first-hit model from being reported as complete solve work.
For one n=83 rectangle with $M$ table descriptors and $R$ query
representatives, the frozen arithmetic count is
$C(M,R)=26M+13R+13\cdot83R+90(2\lceil M/1024\rceil+2\lceil R/8\rceil)$.
The [ledger's field-API vector](n83_full_spill_segment_work.json) exposes the
terms for one M32/R29 rectangle: 331,249,352,704 additions,
268,435,456,000 multiplications, 98,247,376,896 squarings, and
142,606,336 inversions on the regular batch path. The native Itoh-Tsujii
inversion calls eight multiplications and 82 squarings, so expanding those
inversions gives 710,766,755,840 ($2^{39.371}$) field API calls. The two
table passes each use seven additions, five multiplications, and one
squaring per descriptor; a query representative uses the same vector,
then each of its 83 signed-x lifts uses six additions, five multiplications,
and two squarings. This is a call count, not a calibrated common-cost
equivalent: additions, squarings, and multiplications need not have equal
hardware cost. Exceptional pairs and all work outside these batch paths
remain excluded. Table build is included in $C$ but excluded from the
single-target online wall interval because the table is reusable.

### First M31 wave receipts and disjoint M32 wave (Q1069)

The first four jobs of [physical x86 run 36684977689](https://github.com/aburan28/cryptanalysis/actions/runs/36684977689)
completed at query starts 2,147,483,648, 2,684,354,560,
3,221,225,472, and 3,758,096,384. Their native receipts report
**zero exact hits** after 38,962,099 Bloom positives. Each receipt has an
archived [bundle and independent checked-Sage audit](runs/n83_portable_q1061_M31_R29_ci_36684977689_qstart2147483648/sage_verify.json)
with the exact curve, base digest, target, and zero supplied witnesses.
Together they add 128 primary M28-by-R27 cells and 2,618,218,774,528
($2^{41.252}$) modeled native field calls. Their summed target-online
time is 35,763.92 s across four separate x86 hosts. GitHub marked the
remaining four queued matrix jobs cancelled before any steps ran; they
have no terminal search receipt, measured work, or credited coverage.
Before Q1068, the [coverage ledger](n83_full_spill_segment_work.json)
had 254/7,552 primary cells and $2^{42.986}$ completed modeled field
calls. Q1068 added 32 primary and 32 M32-extension cells and
710,766,755,840 more modeled field calls; Q1069 then added 256 primary
and 256 M32-extension cells. The current totals appear above.

The [Q1069 frozen launch plan](n83_m32_wave_launch_plan.json) chooses
eight M32/R29 rectangles at query starts 7,516,192,768 through
11,274,289,152, all beyond the Q1068 interval and the cancelled M31
jobs. The unchanged Q1061 portable kernel and exact n=83 curve, public
target, B=8,000,204 base, 48,194 folded columns, base digest, and
`isogeny: "none"` are pinned in the plan. It models $2^{42.371}$ native
field calls for all eight jobs and an 18.96% heuristic chance of a hit.
The [physical x86 workflow](../../.github/workflows/n83-portable-quotient-m32-wave.yml)
used eight parallel jobs, per-host resource gates, a bounded control,
and terminal receipts. [Run 36706324060](https://github.com/aburan28/cryptanalysis/actions/runs/36706324060)
completed all eight jobs with **zero exact hits** among 77,891,536 Bloom
positives. Each archived bundle was checked by the
[ingester](n83_m32_wave_ci_ingest.py) and an independent checked-Sage
identity [audit](runs/n83_portable_q1069_M32_R29_ci_36706324060_qstart7516192768/sage_verify.json).
The eight job walls range from 11,143.17 to 13,916.41 s, and target-online
query plus replay ranges from 9,672.04 to 12,158.11 s. The latter sum to
84,208.29 s across separate hosts and must not be interpreted as one
continuous solve time. The wave charges $2^{42.371}$ modeled native field
calls and adds 256 primary plus 256 M32-extension cells. Q1069 remains a
stage proposal with null candidate and run IDs; its 18.96% frozen hit
probability was a model prediction, not measured natural yield. No n=83
IC DLP or complete-solve work is established.

### Representative-batch timing screen (Q1070)

The [paired ARM receipt](runs/n83_portable_rep_batch_paired.json) compares
representative batches 8, 16, and 32 in ABCCBA order on the same frozen
n=83 public target, M=$2^{24}$ table, R=$2^{20}$ query, base, schedules,
20-bit Bloom filter, ten hashes, four workers, and native source. The
[checked Sage runtime](runs/n83_portable_rep_batch_runtime_info.json)
was saved before the measurement. All six runs had the same 18,675 Bloom
positives and zero exact hits. Against batch 8, batch 16's two paired
query-time ratios were 1.0372 and 0.9963; batch 32's were 1.0278 and
0.9899. Both comparisons straddle one, while the median full-wall ratios
were 0.9578 and 0.9599. This bounded ARM screen does not support a
full-size x86 speedup, so Q1068 and Q1069 retained their
frozen batch-8 policy. Q1070 remains a stage diagnostic with null
candidate/run IDs and no complete-solve work claim.

### Disjoint local ARM rectangle (Q1071)

The [frozen Q1071 plan](n83_local_arm_m32_q1071_plan.json) extends the
same one-target M=$2^{32}$ table with an R=$2^{29}$ representative-query
range $[11,811,160,064,12,348,030,976)$. It starts exactly where the
Q1069 wave ends, so the range does not duplicate its eight x86 jobs. The
checked [Sage runtime receipt](runs/n83_local_arm_m32_q1071_runtime_info.json)
was saved before the local physical ARM search started. The terminal
[receipt](runs/n83_local_arm_m32_q1071.json) and independent checked-Sage
[audit](runs/n83_local_arm_m32_q1071_sage_verify.json) pin the exact
curve, base digest, B, folded columns, target, source hashes, and
`isogeny: "none"`. The wrapper identifies the shared Q1061 search kernel;
Q1071 is the frozen local dispatch of that kernel. The batch-8 choice
followed the Q1070 screen. Its native scan found **zero exact hits** among
9,739,019 Bloom positives. Full wall time was 8,494.23 s, with 6,875.79 s
target-online query and replay and 10.30 GiB peak RSS. It added 32
primary and 32 M32-extension cells. Q1071 retains `candidate_id: null`
and `run_id: null`; its $2^{39.371}$ field calls are a modeled attempt
cost, not measured complete-solve work.

### Bloom early-exit screen (Q1072)

The [paired ARM benchmark](runs/n83_bloom_early_exit_paired.json) compares
the frozen Bloom lookup with a variant that returns as soon as a missing bit
is found. The [benchmark source](bench_n83_bloom_early_exit.py) generates the
variant from an exact checked source anchor and records both generated
source hashes. A [small exact control](runs/n83_bloom_early_exit_smoke.json)
and the full M=$2^{24}$, R=$2^{20}$ ABBA screen had identical Bloom
positives and exact hits across variants. The full screen had 18,675 Bloom
positives and zero exact hits. Early exit's two paired query-speed ratios
were **0.9598** and **0.9599** (frozen/variant); full-wall ratios were
0.9935 and 0.9795. The local Q1071 search was active during this screen,
so it is a concurrent-load ARM stage diagnostic. Both query pairs were
slower, and Q1072 is not promoted to a full-size search. Its candidate and
run IDs remain null, and it provides no complete-solve work estimate.

### Conditional larger-table ARM follow-up (Q1073)

The [frozen M33/R29 plan](n83_local_arm_m33_q1073_plan.json) starts at
query position 12,348,030,976, exactly after Q1071's interval. It keeps
the same n=83 curve, public target, exact factor base, signed-Frobenius
folding, `isogeny: "none"`, and portable kernel. The 20-bit Bloom filter
would occupy about 20 GiB. A complete rectangle models $2^{39.582}$
field calls and a 5.12% hit chance under the same finite-support placement
heuristic. The plan is gated on terminal status for the active searches,
independent replay of any supplied hits, no verified DLP, and at least
24 GiB of free host memory and 2 GiB of free spill
space. The [guarded launcher](launch_n83_local_arm_m33_q1073.py) checks
the exact curve and factor-base identities, source hashes, disjoint query
range, audited prior zero-hit receipts, terminal Q1069 bundles, and current
host resources. It records the checked Sage runtime before starting the
M33/R29 workload. All gates passed in the
[preflight receipt](runs/n83_local_arm_m33_q1073_preflight.json); the
[checked Sage runtime](runs/n83_local_arm_m33_q1073_runtime_info.json)
was saved before the physical ARM run started at 2026-09-30 15:01 UTC.
The wrapper and native process later disappeared without a terminal
receipt. The preserved [interruption record](runs/n83_local_arm_m33_q1073_interrupted.json)
binds the [start marker](runs/n83_local_arm_m33_q1073.started.json),
preflight, and runtime hashes; its operation counts, exact-hit result,
and completed coverage are **unknown**. No Q1073 coverage is credited.
Its candidate, run, measured relation yield, and complete-solve-work
fields remain null. A retry needs separate artifacts and must charge this
interrupted attempt as unknown work.

The [retry-2 launcher](launch_n83_local_arm_m33_q1073_retry2.py) binds
the preserved interruption, repeats the same frozen query rectangle,
and writes distinct artifacts. Its [controller](runs/n83_local_arm_m33_q1073_retry2_controller.json)
started a detached physical ARM search after passing a fresh
[preflight](runs/n83_local_arm_m33_q1073_retry2_preflight.json) and saving
the checked [Sage runtime](runs/n83_local_arm_m33_q1073_retry2_runtime_info.json).
The [retry start marker](runs/n83_local_arm_m33_q1073_retry2.started.json)
is not a terminal result. The earlier unknown work stays charged as an
interrupted attempt; no new coverage or relation is credited while retry 2
is running.
The [host-resource intervention record](runs/n83_local_arm_m33_q1073_retry2_resource_intervention.json)
documents a temporary system-volume free-space drop below 300 MiB while
the native worker remained live. Two idle temporary worktrees' ignored
Rust build caches were cleared, restoring about 2.5 GiB free; the worker
resumed CPU work. A second free-space decline led to clearing two more
idle ignored build caches, with about 2.8 GiB free afterward. Any
eventual Q1073 retry wall time must be read with
this host-pressure event attached. It gives no result or coverage credit.

### Conditional one-table R30 continuation (Q1074)

The [frozen Q1074 plan](n83_local_arm_m33_r30_q1074_plan.json) starts at
query position 12,884,901,888, exactly where Q1073 ends, and covers one
full R=$2^{30}$ range with the same M=$2^{33}$ table. Reusing one table
and one exact-replay pass models 1,421,533,511,680 ($2^{40.371}$) native
field calls, **13.66% fewer** than two separate M33/R29 calls covering
the same query range. The frozen finite-support placement heuristic gives
a 9.98% hit probability for this rectangle. Both figures are predictions,
not measured natural yield or complete-solve work.

The [guarded launcher](launch_n83_local_arm_m33_r30_q1074.py) requires
Q1073 retry 2 to finish with zero exact hits and an independent checked-Sage
audit, then requires that receipt to be credited in the regenerated
coverage ledger with no verified DLP or unresolved exact hit. It checks
the curve, actual B, folded columns, base digest, source
hashes, public target, query disjointness, physical ARM backend, and
fresh host memory and spill space before saving the checked Sage runtime
and starting a job. Its negative preflight test stopped at Q1073's start
marker without launching Q1074. Because Q1073 has no audited zero-hit
terminal receipt, Q1074 remains closed. The proposal retains null
candidate and run IDs; no Q1074 performance or relation is yet measured.

### Next disjoint physical x86 wave (Q1075)

The [frozen eight-job plan](n83_m32_wave_q1075_plan.json) starts at query
position 13,958,643,712, exactly after Q1074's proposed interval, and
ends at 18,253,611,008. All eight M=$2^{32}$, R=$2^{29}$ intervals are
disjoint from completed search receipts and from Q1073/Q1074. The plan
retains the same fixed public target, curve ID, exact 8,000,204-point
factor base, 48,194 signed-Frobenius columns, and `isogeny: "none"`.
Together the jobs model $2^{42.371}$ native field calls and an 18.96%
finite-support hit chance. These are predictions, not measured solve work
or natural relation yield. The [one-shot workflow](../../.github/workflows/n83-portable-quotient-m32-wave-q1075.yml)
uses physical x86 PCLMUL, per-host memory and disk gates, a bounded exact
control, terminal checks, and artifact upload. The
[ingester](n83_m32_wave_q1075_ci_ingest.py) preserves failures and exact
hits for independent checked-Sage replay. Q1075 keeps null candidate
and run IDs until a complete method is identified.
[Run 36751667950](https://github.com/aburan28/cryptanalysis/actions/runs/36751667950)
has all eight jobs in the full-search step. No Q1075 relation, DLP, or
completed work is claimed before terminal artifacts are audited.

The [Q1077 conditional design](n83_m32_wave_q1077_design.json) reserves
eight further M32/R29 intervals from query start 18,253,611,008 through
22,548,578,304, all disjoint from Q1073, Q1074, and Q1075 and inside the
frozen query domain. It models another $2^{42.371}$ native field calls,
but leaves the hit probability and measured work null until Q1073 and
Q1075 have terminal checked-Sage audits and the coverage ledger is
recomputed. Q1077 is not an executable or dispatched wave; a verified
target DLP or unresolved exact hit closes its launch gate.

### Exact zero-run orbit keyer screen (Q1078)

The Q1078 keyer observes that the smallest cyclic bit rotation begins at a
longest run of zero bits. Whole-word cyclic ANDs identify every such start;
Q1078 compares the resulting full rotations exactly, including ties. The
[one-million-input benchmark](runs/n83_rotation_keyer_bounded_comparison.json)
checked equality with the existing keyer on zero, one, polynomial and
normal-basis vectors, normal-basis pair and spaced-triple supports, and
deterministic pseudorandom 83-bit inputs. On this physical ARM host, the
zero-run keyer took a median 0.0210 s versus 0.0649 s for the existing
keyer, a 3.09× keyer-only gain. A separate Booth implementation was 5.39×
slower than the existing keyer and is not promoted.

The [paired native stage screen](runs/n83_zero_run_stage_bounded_comparison.json)
generated an alternate source from the frozen Q1061 source without changing
the source used by the live Q1073 and Q1075 searches. Two M20/R18
public-target runs per arm had identical Bloom positives and exact outcomes:
zero natural hits. The median query phase was 2.00× faster with zero-run
keying; query plus exact replay was 2.02× faster. The host was also running
the four-worker Q1073 search, so these short timings do not establish an
isolated full-size speedup. The alternate native kernel found the same
planted exact hit, and [checked Sage](runs/n83_zero_run_stage_planted_sage_verify.json)
independently verified its four-point relation and scalar. The
[source generator](bench_n83_zero_run_stage.py) records hashes for the frozen
and generated sources. A [one-shot physical x86 screen](../../.github/workflows/n83-zero-run-keyer-x86-q1078.yml)
is prepared for a later PR synchronization; it has not run. Q1078 uses the
same exact curve and factor base, `isogeny: "none"`, and null candidate/run
IDs. Natural n=83 relation yield, complete solve work, and physical x86
performance remain unknown.
The frozen native field-call model is unchanged because Q1078 replaces
only orbit-key selection; its bounded wall-time gain does not lower the
$2^{39.371}$ modeled field calls per M32/R29 rectangle or establish a
complete solve exponent.

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
./sage -python experiments/koblitz-pair-claw-20260929/bench_native_n83_parallel.py
python3 experiments/koblitz-pair-claw-20260929/n83_knownlog_screen.py
python3 experiments/koblitz-pair-claw-20260929/n83_bloom_resource_screen.py
python3 experiments/koblitz-pair-claw-20260929/n83_parallel_chunk_screen.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_bloom_shard.py
python3 experiments/koblitz-pair-claw-20260929/n83_bloom_shard_screen.py
# Inspect the stopped direct-shard campaign; its M=2^32 run exceeded host headroom.
./sage -python experiments/koblitz-pair-claw-20260929/n83_bloom_campaign.py
# --aggregate writes completed-chunk accounting and rejects overlap.
./sage -python experiments/koblitz-pair-claw-20260929/verify_query_orbit_reuse.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_query_orbit_reuse.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_n83_orbit_query.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_n83_orbit_ABBA.py
python3 experiments/koblitz-pair-claw-20260929/n83_query_orbit_reuse_screen.py
./sage -python experiments/koblitz-pair-claw-20260929/n83_orbit_campaign.py
# Once host memory and system-volume space are sufficient for M=2^31:
# ./sage -python experiments/koblitz-pair-claw-20260929/n83_orbit_campaign.py --run-next
./sage -python experiments/koblitz-pair-claw-20260929/build_n83_knownlog_base_k48194.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_knownlog_base_k48194.py
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_large_orbit_planted.py
python3 experiments/koblitz-pair-claw-20260929/n83_large_knownlog_base_screen.py
python3 experiments/koblitz-pair-claw-20260929/n83_large_orbit_solve_work.py
./sage -python experiments/koblitz-pair-claw-20260929/n83_large_orbit_campaign.py
# --run-next launches one guarded Q1051 rectangle when no competing marker exists.
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_two_shard_planted.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_n83_two_shard_paired.py
python3 experiments/koblitz-pair-claw-20260929/n83_two_shard_screen.py
python3 experiments/koblitz-pair-claw-20260929/n83_two_shard_solve_work.py
./sage -python experiments/koblitz-pair-claw-20260929/run_n83_two_shard_chunk.py --table-log2 20 --query-reps-log2 14 --workers 1
./sage -python experiments/koblitz-pair-claw-20260929/n83_two_shard_campaign.py
# After Q1051 exits: --calibrate-full-table first, then assess its resource receipt.
# --run-next launches one guarded Q1052 rectangle after competing runs finish.
./sage -python experiments/koblitz-pair-claw-20260929/verify_n83_unified_planted.py
./sage -python experiments/koblitz-pair-claw-20260929/bench_n83_unified_paired.py
python3 experiments/koblitz-pair-claw-20260929/n83_low_memory_screen.py
./sage -python experiments/koblitz-pair-claw-20260929/n83_low_memory_campaign.py
# --run-next launches one Q1058 rectangle only after the 4 GiB system-volume guard passes.
python3 experiments/koblitz-pair-claw-20260929/n83_fast_low_memory_screen.py
./sage -python experiments/koblitz-pair-claw-20260929/n83_low_memory_campaign.py --proposal-id Q1059
# --run-next launches one Q1059 fast-keyer rectangle under the same guard.
python3 experiments/koblitz-pair-claw-20260929/n83_spill_low_memory_screen.py
./sage -python experiments/koblitz-pair-claw-20260929/n83_low_memory_campaign.py --proposal-id Q1060
# --run-next launches one Q1060 SSD-spill rectangle under its separate guard.
# Q1061 controls can run with ordinary Python; they do not import Sage.
python3 experiments/koblitz-pair-claw-20260929/verify_n83_portable_controls.py --backend arm_pmull --spill-dir /Volumes/SSD990/llm/tmp
# The CI workflow runs x86_pclmul and x86_generic on a physical x64 Linux runner.
python3 experiments/koblitz-pair-claw-20260929/n83_full_spill_screen.py
python3 experiments/koblitz-pair-claw-20260929/n83_full_spill_work.py
./sage -python experiments/koblitz-pair-claw-20260929/n83_full_spill_campaign.py
# --run-next launches one Q1062 full-filter range only after competing runs exit and its guard passes.
./sage -python experiments/koblitz-pair-claw-20260929/n83_full_spill_handoff.py
# One-shot handoff from the active Q1060 rectangle to the guarded first Q1062 range.
```
