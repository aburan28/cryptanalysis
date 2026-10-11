# Cofactor-correct five-sum follow-up (PDP stage)

This is a bounded point-decomposition experiment on the Koblitz model
`y²+xy=x³+1`. It does not measure final relation linear algebra, target
descent, or a complete discrete-log computation. Targets are uniform nonzero
prime-subgroup multiples, frozen before solver execution; planted controls
are excluded from natural yield.

## 1. Correct target fibers

The archived n=83 base contains `[4]P` for original points with `x(P)<2^17`.
The original-point equation must use one of the four lifts of a subgroup
target `R`: `[4^-1 mod r]R+K`, where `K` runs through the rational four-torsion.
The compact graph records all four lifted points and their digests in
`n83-v2-chain.json`. The exact point control verifies each signed witness by
independent Python curve addition. The exhaustive small n=13 `l=3` control
in `n31-l9-rank8-v2-chain.json.xz` checks membership in the four-point fiber
against `[4]sum=R` on all 161,051 ordered five-tuples in that small signed
base (2,935 matching tuples).

The n=31 subgroup base uses `[1492]P`, because its curve order is
`4*373*1439393`. Its complete target fiber has **1492** points. The graph
constructs 373-torsion and combines it with four-torsion; treating this
base as a four-lift problem would be wrong.

## 2. Compact encoding and bounded S6 probe

`implicit_five_chain.py` records a compact exact constraint graph: five
original curve points with bounded x coordinates, three intermediate points,
four group-add gates, and the lifted target. Each `ADD` gate is the full curve
law, including exceptional cases. This representation stays small because it
has **not** been Boolean-expanded or compiled into SAT/Gröbner equations.
Its `solver_status` is `not-run`, and neither solving degree nor relation
yield follows from the graph's construction time.

`s6_bounded_probe.py` independently attempts the conventional expanded S6
Boolean descent on each correct n=83 lift, with a 512 MiB address-space cap
and a 30-second per-branch watchdog. All four correct lifts built S6 with
190,252 terms in about 5.2–5.4 seconds and then failed with `MemoryError`
during Boolean descent after about 25 seconds total each. The observed peak
RSS at the completed S6 stage was about 459,000 KiB; the peak at failure is
not separately measured. `n83-s6-probe.json` retains stage receipts and
failure traces. The probe is an encoding-size measurement, not a relation
collector.

## 3. Paired ordinary n=31 controls

The primary development manifest is `n31-l9-rank8-v2-manifest.json`, its
summary is `n31-l9-rank8-v2-run/results.json`, and the hash-bound raw and
audited receipts are in `n31-l9-rank8-v2-receipts.tar.xz`. It fixes five streams of eight
ordinary subgroup targets, exact original x-subspace base, `[1492]` subgroup
projection, both signed points, 512 MiB, at most 50,000 triple checks and
five seconds per query. The base has `B=550` signed projected points and 275
sign-folded columns. The two point-lookup arms consume identical targets;
each found row has an exact point-sum replay and rank over the certified
prime `r=1439393`.

| Seed | Three-sum rank | Five-sum rank |
| --- | ---: | ---: |
| 210031 | 8 | 8 |
| 210032 | 8 | 8 |
| 210033 | 8 | 8 |
| 210034 | 8 | 8 |
| 210035 | 8 | 8 |

Charged time includes construction apportioned across five streams, target
generation, input and process setup, all attempts and witness auditing. The
median charged time is about 1.81 seconds for either direct arm (see the
machine-readable per-stream values). This is **not** a 2× improvement. A
smaller `l=6`, `B=66` development screen gave rank 24 in all five-sum streams
but the three-sum control reached ranks 0,2,0,0,0; that screen is not a valid
rank-eight paired speed comparison.

No compact S6 SAT, F4, or F5 candidate has completed a natural relation in
these runs. Their throughput remains unknown, rather than being imputed
from the direct point lookup.

## 4. Full n=83 base

`n83-v2-manifest.json.xz` freezes the actual 130,604 signed points, 65,302
columns and five ordinary 24-target streams. The direct pair lookup would
require **8,528,767,710** pair entries and is rejected at its 1.5-million
entry cap before allocation. `n83-v2-run/results.json` records zero attempts,
rank zero, all five cap statuses and the charged base/target/input costs.
The implicit graph constructs all four corrected branches within 512 MiB,
but no solver runs them. There is no measured n=83 natural five-sum relation
or same-base rank-eight comparison, so the 2× gate is **unknown**.

The next implementation gate is a bit-level backend for the exact implicit
group-add constraints, with an explicit memory and attempt limit. It must
produce natural original-point witnesses, then replay `[4]sum(P_i)=R` and
compare verified independent rank per charged wall time against a same-base
control. Final matrix and target descent costs remain separate.

## Reproduction

```sh
xz -dc experiments/pdp-scaling/five-sum-next-20260929/n83-v2-manifest.json.xz \
  > /tmp/n83-v2-manifest.json
python experiments/pdp-scaling/five_sum_next.py run \
  experiments/pdp-scaling/five-sum-next-20260929/n31-l9-rank8-v2-manifest.json \
  /tmp/five-sum-n31-replay
python experiments/pdp-scaling/implicit_five_chain.py \
  /tmp/n83-v2-manifest.json \
  /tmp/five-sum-n83-chain.json
python experiments/pdp-scaling/s6_bounded_probe.py run \
  /tmp/n83-v2-manifest.json \
  /tmp/five-sum-n83-s6.json --seconds 30
```

The manifest binds the solver source digests and the n=83 base archive hash.
Replays require a fresh output directory and a C++17 compiler.
