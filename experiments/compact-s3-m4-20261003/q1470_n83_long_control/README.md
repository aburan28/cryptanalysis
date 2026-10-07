# Q1470: extended N83 unpinned chained-S3 control

Q1470 repeats Q1467's **known-representable but unpinned** N83 four-point
target on the exact same materialized CNF and solver binary. The curve is
`EC1N83Ckb1h876c2921cb64`; Q1467's W≤4 factor base has 1,934,066 usable
subgroup points and 11,651 signed Frobenius columns, enumerated-set digest
`1b4110f055c88a4b1be2bfdd4bdb1cfca62bc41f49f0a5cac7698f7d4fc35325`.
This remains a stage proposal with `candidate_id: null`, `run_id: null`,
`isogeny: "none"`, and solver code `PDP4hybrid`.

Q1467's fully pinned control recovered a verified four-point relation for
this same public target. Its unpinned run stopped at the 60-second native
wall cap after 44,577 conflicts and one exact joint check, without a model.
The [Q1470 protocol](protocol.json) was committed before running. It binds
the exact Q1467 input and binary hashes, parent receipts, checked Sage
runtime, a 600-second native wall cap, a 10,000,000-conflict cap, the same
250,000-pair joint-rule cap, and the same decision policy.

The [runner](run.py) measures CNF materialization, native solver process,
and model replay separately. Any SAT model is checked against the complete
CNF and independently replayed as a four-point curve relation. The
[archive audit](archive_audit.json) checks the source-bound receipt and all
native counters. This planted control can measure solver success or a longer
lower bound on this known-solution input. It cannot estimate natural N83
relation yield or a complete N131 solve cost.

## Result

The native solver again hit its wall cap without a model. The
[source-bound audit](archive_audit.json) passed; its raw receipt is
[here](run/receipt.json).

| Same known-solution N83 CNF and binary | Q1467 60-second cap | Q1470 600-second cap |
| --- | ---: | ---: |
| Native result | censored, wall cap | censored, wall cap |
| Solver process wall, exploratory | 60.447 s | 600.373 s |
| SAT conflicts | 44,577 | 159,108 |
| Exact joint-chain checks | 1 | 1 |
| Native field multiplication calls | 554,933 | 554,933 |
| Native field squaring calls | 3,984,876 | 3,984,876 |
| Native field inversion calls | 18,828 | 18,828 |
| Peak child RSS on Darwin | 430,145,536 B | 1,434,632,192 B |
| Independently verified unpinned relation | 0 | 0 |

The solver spent the additional time in SAT search: conflicts increased by
3.57 times while its measured field primitive calls did not change, because
it ran no further exact joint-chain check. Field-operation counts alone
therefore undercharge this hybrid solver's work. The two wall observations
are exploratory on an unisolated host, so their ratio is not a controlled
CPU performance claim. This known-solution control now establishes a
600-second lower bound for this frozen solver and input, with no successful
N83 cost to extrapolate. Natural N83 yield, late-rank collection, final
matrix work, target descent, and a complete N131 `2^x` remain unknown; the
challenge stays closed.

## Reproduce

```sh
python3 experiments/compact-s3-m4-20261003/q1470_n83_long_control/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1470_n83_long_control/audit.py --check
```

The runner refuses to overwrite its archived result. All new local Sage
jobs use the repository's checked launcher.
