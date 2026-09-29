# Four-point pair claw: n=23 control, n=53 relation, n=83 work screen

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
to the completed toy pipeline and `Q1037`–`Q1041` to the later stage
controls. Only `Q1036` has a final `IC1` candidate identity.

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
n=83 relation yield, and complete-work exponent `null`; `verified_n83_dlp`
is false. It does
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
