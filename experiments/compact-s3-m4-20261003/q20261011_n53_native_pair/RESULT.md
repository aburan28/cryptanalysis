# Q1454: a native unique-state N53 pair table supplies fifteen independent rows

A frozen native type-II ONB implementation completed the N53 two-million-state
quotient-pair table and the common 1.5-million ordinary-query schedule.
It returned **15 distinct, independently verified four-point relations** with
augmented rank **15** over the exact subgroup order. At the same table-addition
and query-addition counts, Q1451's random-with-replacement table supplied 11
rank rows. The deterministic orbit-pair schedule therefore reduced charged
pair additions per novel row from **454,540 to 333,329**, a **1.364×** gain
at this stage's named event boundary.

The curve is `EC1N53Ckb1hf77aab617904`, workload `74f2979b3e68`, and
`isogeny: "none"`. The exact factor base has B=24,062 subgroup-usable
points, K=227 signed-Frobenius columns, and enumerated-set SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
Q1454 is a `PDP4mitm` stage proposal with null candidate and run IDs.

## Frozen table-cap sweep

The same 1,500,000 query-index pairs were checked against three prefixes
of the shuffled orbit-pair schedule. Every table state consists of an
ordered representative pair block, a relative Frobenius lift, and a sign.
The prefix cap counts actual native pair additions. All matching native
signed-Frobenius keys were expanded independently into four full subgroup
points, re-added to the public target, and ranked in a separately oriented
factor-base log matrix.

| Table pair additions | Distinct keys | Matching queries | Verified distinct rows / augmented rank | Charged pair additions per novel row |
| ---: | ---: | ---: | ---: | ---: |
| 500,000 | 497,704 | 7 | 7 / 7 | 499,991 |
| 1,000,000 | 995,850 | 8 | 8 / 8 | 499,993 |
| **2,000,000** | **1,990,692** | **15** | **15 / 15** | **333,329** |

Each cap charges its table attempts plus 1,500,000 query-pair additions
and 1,499,940 target-complement additions. The last cap therefore charges
**4,999,940** pair additions, or `2^22.253` additions for this stage's
observed 15 rows. The per-row quotient is `2^18.347` additions. The
same-target homogeneous difference rank is 14. Each matching query yielded
one distinct relation and one novel rank row; no measured query yielded
multiple rows.

The conditional match rate for the two-million-state table is
**10.0×10⁻⁶ per query**. Its Wilson 95% interval is
**6.06–16.50×10⁻⁶**, under uniform-with-replacement query draws conditional
on this one fixed table and public point. The 500,000- and 1,000,000-state
rates are 4.67×10⁻⁶ and 5.33×10⁻⁶. These intervals describe query
sampling against each fixed index; they do not estimate a target population
or a degree-131 solve rate.

Against Q1451 at the identical two-million-attempt and query caps,
Q1454 stores 1,990,692 distinct keys versus 1,418,520, a **1.403×**
key-count increase. Its rank yield rises **1.364×** (15 versus 11), or
0.447 bits in the measured N53 stage work per novel row. The table schedule
is the changed variable; target, exact base, query seed, query draws, and
pair-addition event boundary are fixed.

## Native implementation and charged phases

The native field kernel implements the same symmetric 107-bit type-II ONB,
Koblitz group law, and signed-Frobenius point key as the checked Python
oracle. The independent arithmetic control passed **1,000 random nonzero
field cases** and **208 curve-add/quotient-key cases**, including doubling
and inverse pairs. The export receipt binds every base point, representative,
lift index, shuffled pair block, and query index to SHA-256 hashes.

| Native phase | Wall seconds |
| --- | ---: |
| Input loading | 0.053 |
| Table allocation | 0.001 |
| Table build | 44.232 |
| Target queries and lookup | 67.383 |
| **Native phase sum** | **111.670** |
| Launcher interval, including result serialization | **112.344** |

Peak native RSS was **192,839,680 bytes**. Independent base reconstruction
took 0.747 s, and match replay with rank computation took 0.680 s after
the native run. The host was not isolated, so these wall times are exploratory;
the stage comparison above uses charged pair additions and verified rank.
Q1453's preceding Python sweep was stopped at its frozen 1,200-second cap
while constructing the table and has no query receipt. Q1454 checked the
wall cap during both table construction and target queries and completed
the entire frozen workload.

## Degree-131 work distance

Q1447's conditional W≤7 pure pair-index model remains `2^85.18`
**logical pair actions**, 24.18 bits above an abstract `2^61` action cap.
Its `2^64.53` index-build states alone are 3.53 bits above that cap.
That model already assumes efficient quotient-pair state enumeration, so
removing repeated random table draws at N53 does not justify lowering its
N131 exponent. The N53 pair-add count and the model's logical action count
are separate units. A fully charged degree-131 solve exponent and numerical
challenge gap remain null until the exact W7 base, ordinary multi-output
and rank yield, final matrix work, and target recovery are measured together.

The next cap search should extend this **native** schedule to all
2,743,068 N53 quotient-pair states and the same query stream. It will test
whether rank yield continues to grow and whether any query produces multiple
independent rows. N83's first verified ordinary relation remains a separate
solver gate; the existing compact S3 chain should be improved against its
recorded target-link bottleneck.

## Reproduce

`freeze.json` binds the exact curve/workload receipts and executed source.
`export_receipt.json` hashes the binary fixtures, `build_receipt.json` hashes
the native binary, `native_measurement.json` records pair work and phases,
`independent_replay.json` records checked relations and ranks, and
`analysis.json` derives the per-cap work comparison. The hashed binary fixtures are included under `inputs/`; the frozen exporter
can regenerate them in `/private/tmp/q1454_n53_inputs` for a native rerun.
`native_raw.json` preserves the unmodified native output. Run:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n53_native_pair/validate.py
```
