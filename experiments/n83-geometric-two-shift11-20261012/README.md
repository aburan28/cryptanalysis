# A larger N83 width-11 factor base from a two-coordinate shift

The affine offset `gamma_27 + gamma_39` (ONB bit indices **26 and 38**)
gives **1,109 signed-Frobenius columns** and **184,094 distinct nonidentity
subgroup points before folding** on `EC1N83Ckb1h876c2921cb64`. This is
13 columns and 2,158 points more than the previous width-11 base, at the
same seed width and curve. An exhaustive screen of all 2,556 distinct
two-coordinate offsets outside `W11` found it to be the unique offset whose
usable-lift count exceeds the old base's 1,096 columns.

| Fixed-width geometry | Shift bits | Usable lifts | Folded columns `K` | Actual base size `B` |
| --- | --- | ---: | ---: | ---: |
| Winning two-coordinate offset | 26, 38 | 1,109 | **1,109** | **184,094** |
| Previous one-coordinate optimum | 81 | 1,097 | 1,096 | 181,936 |
| Next highest two-coordinate lift count | varies | 1,094 | at most 1,094 | at most 181,604 |

For each offset, the [frozen screen](screen.json) counts x-coordinates
lifting on `y²+xy=x³+1` by the Artin–Schreier trace condition
`Tr(x + 1/x) = 0`. The full cofactor projection, subgroup-usable orbit key,
and exact sorted [key file](best_keys.bin) are constructed for every offset
whose lift count could beat 1,096; only bits 26 and 38 qualify. Any folded
column needs a usable lift, so `K ≤ valid lifts`; therefore the second
highest lift count of 1,094 bounds every other two-coordinate base below
the winner's independently replayed 1,109 keys. The elementary implication
is checked in [LiftBound.lean](LiftBound.lean), with an
[#print axioms receipt](lean-build.txt) reporting no axioms. The finite
field, curve, and 2,556 census rows are computational inputs to this
conditional lemma and are not formalized in Lean.

The exact uniform-target six-subset first moment rises from
`20,831.181431...` to `22,358.376917...`, a factor of approximately
`1.073313`. This is a geometric capacity diagnostic. Ordinary-query
relation yield, novel matrix rank, target descent, and single-target online
time have not been measured for this new base. Its full packed four-summand
root-index payload at 16 bytes per root would be **3,266,563,936 bytes**;
adding the earlier x/y cache layout would raise the deterministic payload
to **9,799,691,808 bytes** before allocator overhead.

The [protocol](protocol.json) binds the N83 source, previous one-coordinate
census, basis bridge, and checked Sage runtime. All 2,556 raw counts are
retained in [progress](screen.progress.jsonl), along with the producer
[stdout](screen.stdout.txt). The primary screen took 55.121 seconds of
exploratory local wall time. [Independent Sage replay](independent_sage_replay.json)
uses separate inversion batches, checks direct curve lifts for each coset,
and reconstructs all winning projected points, prime-subgroup checks,
signed-Frobenius keys, and key-file bytes. Its own raw output is retained.
The earlier slower replay attempt was stopped and preserved, not interpreted
as evidence about the mathematics.

From the repository root, verify all receipts with:

```sh
python3 experiments/n83-geometric-two-shift11-20261012/verify.py
```

The next decisive test is an ordinary-target six-summand decomposition on
this exact new base, paired with the previous width-11 base on the same
public point and resource cap. Complete factor-base log recovery and a
matched rho comparison remain separate pipeline stages.
