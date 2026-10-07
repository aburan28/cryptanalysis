# Bounded-carry τ atlas portfolio: frozen holdout and native replay

The protocol, Python selector, and new scalar generator were frozen in
`9e3e1a31` before the new 256-case Sage panel was generated. The Sage
seed generator was frozen in `3f745b81` before its execution. The native
selector, independent replay gate, and isolated-manifest generator were
frozen in `31788df0` before the release build and replay. The original
64-case and earlier linked-atlas 256-case panels were design data; only
`portfolio-fixture.json` is a new holdout for this three-choice selector.

## Method and accounting

For each scalar, compute the short `a+bτ` representative and original
width-four digit stream once. Save the coefficient-state residues modulo
9. Translate that stream to the two-orbit and linked three-orbit tables
with the exact small-integer carry recurrence

`c_(i+1) = (d_i + c_i - e_i)/τ`, starting at `c_0=0`.

The baseline digit is `d_i`; `e_i` comes from the alternate table at
the saved residue plus the carry. A zero carry with an unchanged seed
copies the old digit. The translator recodes the finite carry tail
after the baseline ends. All alternate digits match independent direct
recoding and reconstruct the same `a+bτ` values. With maximum digit
norm 112, the invariant `N(c)≤896` follows from
`N(c_next)≤(sqrt(N(c))+2 sqrt(112))²/3`; the largest observed carry
norm was 108. An exhaustive superset automaton over all 81 possible
baseline residues reached 697 and 715 states for the two alternate
tables, with maximum norm 432 and no transition outside the bound.

Score each complete stream using the existing one-use evaluator source
count plus 83, 79, or 75 `M+S` units of seed/orbit preparation. Choose
the minimum; ties favor the original, then two-orbit, then linked
three-orbit. The source count includes the selected table's preparation
on **every scalar**. It excludes the CPU cost of translating and scoring
all three streams, short-representative lattice reduction, and the final
affine inversion. The native `portfolio` timing mode includes all of
those stages in its one-use interval, but no controlled timing receipt
exists yet.

| Input panel | Cases | Original | Two-orbit | Linked three-orbit | Portfolio | Saving versus original | Saving versus fixed linked |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Original design | 64 | 88,656 | 88,313 | 88,089 | 87,632 | 1,024 (1.155%) | 457 (0.519%) |
| Earlier linked panel, retrospective | 256 | 354,504 | 353,377 | 352,827 | 350,582 | 3,922 (1.106%) | 2,245 (0.636%) |
| **New frozen portfolio holdout** | **256** | **354,581** | **353,372** | **353,074** | **351,047** | **3,534 (0.997%)** | **2,027 (0.574%)** |

On the new holdout, the selector chose the original table 63 times,
two-orbit 79 times, and linked three-orbit 114 times. It improved on
the original in 193 cases and tied in 63, because the original is an
available choice. Mean source-count saving versus original was 13.80
`M+S` per scalar. A 5,000-resample paired bootstrap over the frozen
cases with seed `20261007` gives a **descriptive** 95% interval of
12.16–15.54 units per scalar. This describes variation across sampled
inputs, not CPU timing uncertainty. The two carry translations performed
39,682 active steps across the 256 cases, about 155 per scalar, and
their CPU cost could exceed the saved field operations. All per-case
costs, choices, and carry work are retained in `portfolio-result.json`,
including zero improvements.

## Reproduction and limits

The checked repository Sage launcher wrote `portfolio-runtime-info.json`
with `status: verified` before generating the new fixtures. The new
scalar fixture SHA-256 is
`04ce0bb7c195ba4993273ee1e84cdc21519e94e738a60eba858bef2f132d5c95`;
the independent Sage seed fixture SHA-256 is
`be110a1a2bab8ab3a4d03a1fda993d0631848efa1ed2b64e3ea88f965875634e`.
The native offline release binary SHA-256 is
`302f94c78a3c227f281d116b889625924f6b0e7ce2939fdc85febbbf568dc954`
on macOS ARM64 with `rustc 1.93.1`. `native-portfolio-checks.json`
retains commands, raw outputs and exits, source and fixture hashes,
compiler, and host details. Its replay passed **1,818 digit-stream
checks, 5,454 prepared seed-point checks, and 606 final scalar-output
checks** across the original, edge, earlier linked, and new portfolio
panels. Every nonedge reported choice and source cost matched the
independent Python scorer; no cached addition took an exceptional
branch. The original native path also passed its 64-case regression
gate.

`make_portfolio_manifest.py` generated a paired 64-case, distinct-base,
one-use benchmark manifest. `isolated_bench.require_manifest` passed
its **structural schema** check with synthetic CPU, NUMA, and cgroup
values. Those values are not a host-isolation record. The physical-host
preflight, noise gates, and paired full-operation benchmark have not
run, so `cpu_speedup_claim` remains `null`. This is variable-time
research code, and secret-scalar use requires separate constant-time
work. Finite-state τ-adic recoding/transducers have prior art
([Heuberger, 2008](https://eprint.iacr.org/2008/153.pdf));
`academic_novelty_claim` remains `null` pending independent review.
