# Q1424: full four-leaf S3 solver parameter screen

The frozen Q1424 screen kept all four variable factor-base leaves and their
three factored S3 links. Across eight N53 and four N83 CryptoMiniSat settings,
every locked control was SAT and passed a check of the serialized CNF/XOR
assignment; every ordinary search reached the 200,000-conflict cap. Solver
configuration alone yielded no verified ordinary relation in this panel.

## Frozen instances

N53 uses `EC1N53Ckb1hf77aab617904`, the exact Q1301 W≤3 base with
`B=24,062` before folding and `K=227` columns, and ordinary workload
`74f2979b3e68`. N83 uses `EC1N83Ckb1h876c2921cb64`, the exact Q1325
cofactor-projected W≤5 base with `B=30,977,592` and `K=186,612`, and
ordinary workload `bab50a1e5f66`. `Q1424` remains a stage proposal with
`candidate_id: null` and `isogeny: none` (`ISO0`). The exact public targets,
base digests, archived input XCNFs, executable, source hashes, and caps are
bound by [freeze.json](freeze.json).

The N53 formula has 23,055 variables and 19,822 AND gates. The N83 raw
preimage formula has 65,221 variables and 62,001 AND gates. The N53 XCNF
rebuilt from exact base keys and the N83 XCNF rebuilt from the four target
preimages match their archived SHA-256 byte for byte. Every variant solves
the corresponding known-satisfiable Q1419 locked formula before its ordinary
search. The locked control is a solver-configuration check; the ordinary
search is the relation-yield measurement.

## Search results

Each ordinary attempt used one solver thread, at most 200,000 conflicts,
45 solver seconds, 55 external seconds, and 1,536 MiB sampled RSS. All 12
attempts stopped on the conflict cap. Wall times are exploratory because the
host lacks a CPU-isolation receipt.

| Field | Variant | Ordinary status | Reported conflicts | Solver wall s | Sampled peak MiB |
| ---: | --- | --- | ---: | ---: | ---: |
| 53 | baseline | BOUNDED_UNKNOWN | 200,001 | 9.408 | 137.1 |
| 53 | seed 17 | BOUNDED_UNKNOWN | 200,002 | 8.023 | 128.2 |
| 53 | polarity false | BOUNDED_UNKNOWN | 200,001 | 11.148 | 106.4 |
| 53 | random polarity | BOUNDED_UNKNOWN | 200,001 | 7.651 | 94.9 |
| 53 | geometric restarts | BOUNDED_UNKNOWN | 200,002 | 7.323 | 85.2 |
| 53 | Luby restarts | BOUNDED_UNKNOWN | 200,001 | 9.499 | 92.1 |
| 53 | VSIDS schedule | BOUNDED_UNKNOWN | 200,002 | 5.687 | 84.6 |
| 53 | wide XOR Gaussian | BOUNDED_UNKNOWN | 200,002 | 50.993 | 411.5 |
| 83 | baseline | BOUNDED_UNKNOWN | 200,002 | 40.956 | 514.4 |
| 83 | seed 17 | BOUNDED_UNKNOWN | 200,002 | 38.600 | 270.0 |
| 83 | Luby restarts | BOUNDED_UNKNOWN | 200,001 | 42.090 | 666.9 |
| 83 | wide XOR Gaussian | BOUNDED_UNKNOWN | 200,002 | 38.604 | 619.4 |

The wide XOR setting activated matrices, but the N83 log rejected candidate
matrices wider than 10,000 columns; one rejected matrix had 20,916 columns.
The VSIDS N53 run consumed fewer exploratory seconds to reach the same
conflict cap, without resolving the query. Neither observation measures
operations to a relation or an end-to-end speedup. All source and output
hashes, 24 compressed solver logs, cap statuses, and sampled memory are
checked by [verification.json](verification.json); the variant table and
matrix diagnostics are in [analysis.json](analysis.json).

The matched N53 pair-table record has a verified relation on the same public
point and exact base. Its solver and resource envelope differ, so this grid
does not yield a wall-time ratio to that method. No natural relation rate or
cost per useful row can be fit from these capped attempts. The complete N131
cold and one-target-online `2^x` fields remain null.

## Next solver change

The solver settings did not remove the four-leaf bottleneck. Q1419's
partial-pinning controls isolate the free S3 intermediates as a productive
structural target: couple the exact field S3 root oracle to leaf-pair search
as an external propagator, constrain each discovered pair's zero or two
intermediate roots, and keep all four leaves variable. First rerun Q1419's
known-satisfiable `free_mids` N53/N83 controls, then seek an unpinned
ordinary N53 relation and an ordinary N83 Q1325 relation. Measure field-root
calls, SAT refinements, memory, verified useful rows, and novel rank before
attempting an N131 projection.
