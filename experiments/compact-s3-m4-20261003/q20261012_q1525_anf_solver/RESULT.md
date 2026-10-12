# Q1525: native ANF solver verifies N53 S3 handoff, then reaches bounded N53/N83 search limits

The published DPLL-ANF solver verified the frozen **N53 pinned S3 handoff** in 6,904 reported conflicts, 0.108 child user CPU seconds, and 0.19 exploratory wall seconds. Its complete internal assignment independently satisfies all 15,615 original XCNF rows and the curve-group relation. The same backend reached the 90-second wall cap on the unpinned known-positive N53 handoff, one ordinary N53 handoff, the pinned N83 handoff, and two ordinary N83 handoffs. Each capped log reported at least 480,000 conflicts in periodic progress, with no terminal conflict count or model. This backend therefore supplies no measured reduction in ordinary decomposition work on these exact circuits.

| Exact input | Curve | Outcome | Child user CPU s | Exploratory wall s | Peak RSS MiB | Conflict evidence |
| --- | --- | --- | ---: | ---: | ---: | --- |
| N53 pinned positive | `EC1N53Ckb1hf77aab617904` | `SAT_VERIFIED` | 0.108 | 0.19 | 12.0 | final 6,904 |
| N53 unpinned positive | same | `WALL_CAP` | 65.05 | 90.07 | 14.9 | periodic lower bound 480,000 |
| N53 ordinary | same | `WALL_CAP` | 76.38 | 90.05 | 14.9 | periodic lower bound 480,000 |
| N83 pinned positive | `EC1N83Ckb1h876c2921cb64` | `WALL_CAP` | 85.95 | 90.06 | 68.0 | periodic lower bound 480,000 |
| N83 ordinary selected | same | `WALL_CAP` | 84.94 | 90.07 | 80.4 | periodic lower bound 480,000 |
| N83 ordinary holdout | same | `WALL_CAP` | 73.73 | 90.06 | 77.4 | periodic lower bound 480,000 |

The command requested the solver's 30-second CPU limit and the runner set a 30/35-second CPU resource limit, but five capped children exceeded 35 child user CPU seconds on this Darwin host. The 90-second outer wall cap was the effective boundary. Actual CPU and memory are retained; no CPU-limited conclusion uses the unfulfilled requested cap. The host has no isolation receipt, so wall and CPU comparisons are exploratory.

## Exact conversion and identities

The conversion preserves the chained-S3 formula without expanding S5. In DPLL-ANF's format an equation requires XOR value **one**. A CNF clause `l₁ ∨ ⋯ ∨ lₖ` becomes the single equation `¬l₁⋯¬lₖ ⊕ 1 = 1`; an extended-DIMACS XOR row is copied as signed unary monomials with no added constant. The formulas are archived as deterministic gzip files; [archive_manifest.json](archive_manifest.json) pins both compressed and original hashes, and the runner restores the exact plain inputs. The validator evaluates every converted row under all-false, all-true, and two seeded assignments. It then independently replays the verified positive model against every original Boolean constraint, S3, and the curve group law.

The N53 base has **B=24,062** usable subgroup points and **K=227** folded columns. Its packed orbit-key digest is `05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`; Q1519's independently enumerated signed-point digest is `356ebb34476f44b89d376e04fe4b03570a0a4cf3dfe0cd722309d7ea083ccc18`. The N83 base has **B=30,977,592**, **K=186,612**, and point-file digest `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`. All six formulas and their source XCNFs have per-file SHA-256 receipts. `Q1525` remains a `PDP4sat` stage proposal with null candidate and run IDs and `isogeny: "none"`.

The external solver is [DPLL_ANF](https://github.com/antektek/DPLL_ANF) at commit `26e3b541f3a917ae4015caae1023642bd6310b79`; the local binary hash and build command are in [build_receipt.json](build_receipt.json). Its [paper](https://www.codit2025-virtual-event.com/web/content/1168?download=true&unique=08332185a80db65206de10342978b5b2225887bb) reports ECC Weil-descent benchmarks through degree 29. Those published results motivated this panel but are not measurements on the N53/N83 circuits here. Q1519's CryptoMiniSat pinned controls completed on both fields, in 0.0645 and 1.082 exploratory wall seconds respectively, under different run conditions; the current rows do not establish a controlled cross-backend speed ratio.

Two pre-driver errors remain recorded. The [first conversion](failed_encoding_v1/failure.json) reversed DPLL-ANF's parity convention, making both known-positive controls immediately `UNSAT` at zero conflicts; those rows have no mathematical UNSAT interpretation. A later [model-output check](failed_model_parse/failure.json) found that the solver's final `v` display violates 52 original rows after preprocessing, while its internal complete bitstring satisfies every row. The final runner verifies that bitstring independently and keeps the raw display for audit.

## Challenge accounting

The ordinary Q1525 rows produced zero verified relations and zero rank increments under their caps; cost per useful row is censored. They supply no cost for final sparse linear algebra, target descent, or replay. Q1505's separate conditional N131 independent-first-pair model remains **`2^123.289` batch multiplication calls** for relation supply, **62.289 bits above an abstract `2^61` reference in that unit**. No field-operation conversion from Q1525's ANF conflicts is justified, and the fully charged N131 one-target exponent remains unset. These data do not pass the challenge gate.

The next useful solver experiment should change the search representation or the number of second-base points examined per complement, then obtain a verified unpinned N53 positive solve and ordinary N83 relation/rank data. Small ANF option changes on these capped circuits have no measured relation-yield signal yet.

Validate the archived panel with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1525_anf_solver/validate.py
```
