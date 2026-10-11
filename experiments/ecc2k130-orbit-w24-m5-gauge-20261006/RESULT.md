# First-leaf Frobenius gauge does not unlock W24/m5 SAT at the frozen bounds

**Decision: stop this exact native-XOR SAT branch before ordinary-query
collection.** On the same planted public point as the
[ungauged W24/m5 control](../ecc2k130-orbit-w24-m5-sat-20261006/RESULT.md),
fixing the first leaf's Frobenius exponent to zero left a satisfiable
142,303-variable formula. CryptoMiniSat returned `INDETERMINATE` with no
model at both the matched 100,000-conflict bound and the preregistered
2,000,000-conflict deeper bound. Neither result is UNSAT, a natural-yield
estimate, a recovered logarithm, or a general no-go for index calculus.

The [protocol](PROTOCOL.md) and [config](CONFIG.json) were committed as
`2b3d29b0` and opened in
[PR #372](https://github.com/aburan28/cryptanalysis/pull/372) before this
run. The producer and independent XCNF verifier were pushed as `a56318e9`
before formula construction. The parent PR #369 result and artifacts are
hash-pinned in `CONFIG.json`. Its planted point is
`Q=(601332210504500677883949919650448457844,
298564623023626972324407206129036117158)`.
The parent witness has first exponent zero; no target or control was changed.

The producer rebuilt the parent's 6,484,547-byte XCNF **byte for byte**,
then appended eight negative unit clauses on variable IDs `43..50`.
An independent verifier checked the exact original CNF and XOR rows were
unchanged, the header and eight inserted clauses were the only difference,
and every row against the archived planted assignment. It found zero
violations among 239,947 CNF and 61,519 XOR rows. Flipping the first
exponent bit caused 81 violations, so the gauge is active. No masks, other
exponents, rationality witnesses, S3 intermediates, or fiber selector were
pinned. The [audit receipt](AUDIT.json) verifies the archived formula,
both raw solver streams, checked Sage runtime receipts and null downstream
fields; its status is `PASS_BOUNDED_GAUGE_SEARCH_WITH_NO_MODEL`.

| Same planted `Q`; CryptoMiniSat 5.14.7, one thread, seed 0 | Ungauged parent | Gauge primary | Gauge deeper |
| --- | ---: | ---: | ---: |
| Variables / AND gates | 142,303 / 79,574 | 142,303 / 79,574 | same XCNF |
| CNF / native-XOR rows | 239,939 / 61,519 | 239,947 / 61,519 | same XCNF |
| Raw XCNF bytes | 6,484,547 | 6,484,595 | same XCNF |
| Conflict limit / reported conflicts | 100,000 / 100,001 | 100,000 / 100,001 | 2,000,000 / 2,000,001 |
| Solver status / recovered model | `INDETERMINATE` / none | `INDETERMINATE` / none | `INDETERMINATE` / none |
| Solver wall, exploratory | 8.143 s | 12.641 s | 232.419 s |
| Peak polled solver RSS | 93,995,008 B | 99,581,952 B | 140,165,120 B |

The primary gauge wall time is about 1.55 times the ungauged run's wall time,
but this unisolated host does not justify a controlled timing ratio. The
structural and search-status observations are the decision basis. The
unchanged 4-GiB memory envelope was respected and live RSS monitoring
worked in both valid runs. The exact gauged raw XCNF SHA-256 is
`af19ac5fab2142f3dc45ecdee6e3d3311ec108b327b363317276ca74305e9d9c`.
The [primary](runs/primary/receipt.json) and
[deeper](runs/secondary/receipt.json) solver receipts preserve the commands,
status, conflicts, raw-stream hashes and exploratory phases. The
[independent witness check](runs/primary/verification.json) is a
*satisfiability control*, not a solver recovery.

For a genuine decomposition with first exponent `k`, applying
`Frob^(131-k)` to the target makes that first exponent zero; this is why
the gauge is mathematically complete only when **all 131 target
conjugates** are searched and every miss is charged to the one target.
The planted primary gate failed, so the frozen ordinary target was not
attempted. Natural PDP yield, verified relation rank, final matrix work,
factor logs, target descent, scalar replay, paired one-target rho time and
online speedup remain `null`. The result does not earn an `IC1` candidate ID.

The next evidence-ranked PDP test should change the representation rather
than increase this SAT search limit again: screen a bounded target-adaptive
pair/root index or compact S3 elimination on frozen ordinary queries, with
group replay and rank per query. A [separate capacity audit in PR #327](https://github.com/aburan28/cryptanalysis/pull/327)
already ruled out a literal full raw-point pair/triple table under 4 GiB;
the proposed index must be sparse, implicit, sharded or query-adaptive.
That is a proposal, not a measured crossover. The end-to-end ECC2K-130
feasibility goal remains open.

Reproduce the archive checks from this branch with
`shasum -a 256 -c experiments/ecc2k130-orbit-w24-m5-gauge-20261006/SHA256SUMS`.
Then run `audit.py --out /tmp/w24-m5-gauge-audit.json` with the checked
`/Volumes/SSD990/cryptanalysis/sage -python` launcher and compare the
generated JSON to `AUDIT.json`. The original solver XCNF and stdout are
retained as deterministic gzip archives; `audit.py` expands and hashes their
exact raw bytes. Any new measured Sage job must first save
`/Volumes/SSD990/cryptanalysis/sage --runtime-info` beside its results.
