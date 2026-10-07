# Q1494: all three S3 links with native XOR on exact window bases

Q1494 tests a different compact four-summand solver on the exact Q1481
window-orbit bases and Q1482 ordinary public targets. It starts from Q1493's
Frobenius-rotated formula with the first raw leaf's window fixed to start
zero. It adds the first-pair `S3` equation to the two links already encoded
symbolically, then passes all three links as native XOR rows with shared AND
gates to single-thread CryptoMiniSat 5.14.7. All four leaf x coordinates,
both pair midpoints, and the target-preimage selector remain free in the
ordinary attempts. No expanded `S5` or pair table is constructed.

The [pre-registered design](design_protocol.json) and [frozen
protocol](protocol.json) bind the checked Sage runtime, exact curve/base
records, Q1493 source and target inputs, CryptoMiniSat binary hash, source,
run order, and 60-second/one-million-conflict limits. The design was
published at commit `e5702e40`; source and protocol were frozen and pushed
at commit `20357112`, before running any cell. Q1494 is a `Q` proposal:
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`.

| Degree | Exact curve ID | Actual usable `B` | Folded `K` | Set SHA-256 |
| ---: | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 430,360 | 4,060 | `42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 348,006,384 | 2,096,424 | `f2d7771988cbd03fa4ea3145fc3870e5a3fc44171b9a57165257f016cdeb19d4` |

## Frozen results

The pinned [control receipt](control/r1/receipt.json) adds Q1490's 327
witness bits to the N53 rotation-44 formula. CryptoMiniSat returns SAT with
zero conflicts. The archived model satisfies every CNF clause and native
XOR row, all three exact `S3` links, exact base membership and distinct
folded columns; independent group-law replay transports the relation back
to the frozen ordinary public target. The same rotation with all witness
bits free censors at 60 seconds.

| Cell | Outcome | Charged target-dependent stage, exploratory | Exact conflicts | Propagations as printed | Peak child RSS raw |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 rotation 44, witness pinned | verified relation control | 0.217 s | 0 | 2 | 14,073,856 |
| N53 rotation 44, all witness bits free | 60 s cap, no model | 60.799 s | 548,781 | 640M | 153,157,632 |
| N53 rotation 0, all witness bits free | 60 s cap, no model | 60.736 s | 545,528 | 637M | 156,549,120 |
| N83 rotation 0, all witness bits free | 60 s cap, no model | 60.858 s | 279,237 | 618M | 196,165,632 |

The N53 XCNF has 26,510 variables, 106,889 CNF clauses and 795 native XOR
rows before witness pins. The N83 XCNF has 63,913 variables, 206,265 CNF
clauses and 1,245 native XOR rows. The [independent accounting
audit](archive_audit.json) checks source and receipt hashes, raw solver
statuses, exact conflicts and decisions, phase sums, and every failed row.
CryptoMiniSat prints propagation counts rounded with `M`; the raw display
tokens above are **approximate**, not exact arithmetic operation counts.
Peak RSS uses Darwin bytes. Wall times are exploratory without an isolated
host receipt.

The raw solver logs show a narrower XOR result than the XCNF format alone
suggests. CryptoMiniSat used **zero Gaussian matrices** at every recorded
N53 matrix initialization: its 8,586- and 6,519-column field-product
components exceeded the default limit. N83 initially used zero matrices
and later used one smaller matrix, while 20,916- and 15,936-column
components remained excluded. Q1494 therefore tests native XOR input
under default Gaussian limits; it does not test full Gaussian elimination
on the large field-product components.

These two rotation-zero cells are slices of the target orbit, not full
Frobenius sweeps. The rotation-44 cell is known satisfiable from the Q1490
ordinary witness and the pinned control. Q1494 measures bounded failed
search work; it gives no successful unpinned PDP cost, natural relation
yield, cost per useful row, N83 rank gain, or degree-131 complete `2^x`.
The challenge gate stays closed. Q1488 found a relation on the matched N53
base with a separately charged pair-table setup; Q1494 returned no
unpinned relation, so no per-relation speed ratio can be formed.

The next representation check should explicitly admit those Gaussian
components on the same frozen formulas. A structural four-leaf support/join
across window domains remains the larger solver goal. The default native
XOR circuit has not crossed the known-satisfiable unpinned N53 gate.

## Reproduce custody checks

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1494_full_xor_window_s3/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1494_full_xor_window_s3/run.py --control --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1494_full_xor_window_s3/run.py --cell n53_known_rotation_44 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1494_full_xor_window_s3/run.py --cell n53_ordinary_rotation_0 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1494_full_xor_window_s3/run.py --cell n83_ordinary_rotation_0 --check
python3 experiments/compact-s3-m4-20261003/q1494_full_xor_window_s3/audit.py --check
```
