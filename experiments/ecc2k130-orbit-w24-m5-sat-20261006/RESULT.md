# Implicit orbit-closed W24/m5 SAT: planted search remains unresolved

**Decision: do not advance this native-XOR SAT encoding to ordinary-query
collection.** The preregistered unknown-witness planted formula is
satisfiable, but CryptoMiniSat returned `INDETERMINATE` after 100,001
conflicts with no model. The monitored valid attempt used 142,303 variables,
239,939 CNF clauses and 61,519 native-XOR rows. An independently evaluated
known planted assignment violates **zero** rows of the exact timed-out XCNF.
Checked Sage independently reconstructed the five group points, the public
target and the half-trace-to-normal input map. This is a bounded search
failure for this exact representation and limit, not UNSAT, zero natural
yield, a recovered logarithm or an ECC2K-130 speedup.

The [protocol](PROTOCOL.md) and [config](CONFIG.json) were committed as
`2a00e321f089d5692e73d2b3b8adc9a494464e68` and opened in
[PR #369](https://github.com/aburan28/cryptanalysis/pull/369) before the
five-point target was generated. The producer and independent verifiers
were pushed as `4c9a98fd8b380008ef53d314c67296841026abc7` before the
first run. The exact policy is the **full** source W24 rational seed set,
cofactor-four projection and all 131 Frobenius powers: `B=2,198,485,492`
geometric subgroup points and 8,391,166 sign-Frobenius columns by the
[exact orbit census](../ecc2k130-263-w24-orbit-columns-20261005/RESULT.md).
This changes the base as well as the summand count relative to original
W24/m6; the field degree is 131 and subgroup order has 130 bits.

The planted public point is
`Q=(601332210504500677883949919650448457844,
298564623023626972324407206129036117158)`. It was made by taking the
smaller-y raw lift for each of the first five archived group controls,
adding them, and applying `[4]`. The frozen masks were
`[5213401,3875025,7561715,9055285,8342917]`; their Frobenius exponents
were `[0,1,2,7,31]`. The raw sum was the third of the four `[4]` fibers
(zero-based index 2). Neither the masks, exponents, intermediate fields nor
fiber selector were pinned in the SAT formula. Exponents outside `0..130`
were forbidden by clauses inside that formula. Two self-tests checked the
barrel rotation, range clauses and frozen group construction.

| Frozen or independently checked quantity | Result |
| --- | ---: |
| Exact XCNF input | 6,484,547 bytes; SHA-256 `da2bdf429c64adcb950403030436536c1bdea8f4cad04bb1b478d7f06347a0ea` |
| Variables / AND gates | 142,303 / 79,574 |
| CNF clauses / native-XOR rows | 239,939 / 61,519 |
| Formula build, exploratory | 0.761 s |
| CryptoMiniSat 5.14.7 result | `INDETERMINATE`, exit 15, 100,001 conflicts, no model |
| Monitored solver interval, exploratory | 8.143 s, peak polled RSS 93,995,008 B |
| Independent Sage group/map replay | `PASS_PLANTED_GEOMETRY_NO_SOLVER_WITNESS` |
| Known planted assignment | 1,210 primary bits; 0 violations in all 301,458 formula rows |
| Mutated fiber selector | rejected; 2 formula-row violations |
| Ordinary frozen target | **not run**, because unknown-witness recovery failed |

The successful monitored [run receipt](runs/planted-r2/receipt.json) has
SHA-256 `4fb2b8c732b411c47bbf7cb41a0a5a92e4edca83b224a2760890d3ee0416bcdf`.
Its [gzip archive manifest](runs/planted-r2/archive.json) retains the raw
XCNF and solver-stream hashes, while the checked
[Sage replay](runs/planted-r2/sage_replay.json) has SHA-256
`34466d1b2af7607c37b20313e689cc0a569d89994deea1cdda0331c6c71239d2`.
The source and binary hashes, runtime receipt and memory gate are in the
run record. The [known-witness receipt](runs/witness-r2/receipt.json) rebuilt
byte-identical XCNF from the frozen target; the independent
[archived-XCNF verifier](runs/witness-r2/verification-archived.json)
(SHA-256 `71b443b96b64b9ba4737ab5c83c5dd8a47375aa401bbe258ce4bac185e581333`)
read every clause and XOR row without importing the circuit builder. Its
[mutation receipt](runs/witness-r2/mutation.json) records a rejected flipped
primary selector. These control certificates prove satisfiability of this
one planted formula; they do not show that SAT can discover its witness.

The first invocation was invalid because the sandbox denied `/bin/ps` at
the mandatory live RSS poll. Its XCNF, solver stdout/stderr, checked runtime
and [failure receipt](runs/monitor-denied/attempt.json) are preserved.
CryptoMiniSat also printed `INDETERMINATE` there, but the attempt has no
valid memory-monitored interval and is excluded from the bounded result.
The runner was fixed in commit `f39984ac` to record monitor errors, and the
valid `planted-r2` run used a working `/bin/ps` poll. No input, seed or
limit was changed. All wall values are exploratory on an unisolated host.

For scale only, the prior original W24/m6 free-witness formula in
[PR #332](https://github.com/aburan28/cryptanalysis/pull/332) had 91,861
variables, 50,208 AND gates, 40,197 XOR rows, 152,281 clauses and
3,863,572 raw bytes. This orbit-closed m5 formula is respectively
1.549, 1.585, 1.530, 1.576 and 1.678 times those sizes despite using one
fewer summand. These are different factor-base policies and planted inputs;
the ratios describe formula structure, not paired solve cost or attack
performance. The dense normal-to-polynomial conversion and its downstream
field products deserve a stage-count audit before any further SAT scaling.
The earlier functional S3/m6 control in
[PR #343](https://github.com/aburan28/cryptanalysis/pull/343) was larger
still and likewise timed out under its planted limit.

The next evidence-ranked test is a **Frobenius-gauge planted screen**: fix
the first leaf exponent to zero, leave all five masks and remaining four
exponents unknown, and reuse this frozen Q. A complete ordinary-target
method would have to try all 131 conjugate target/fiber systems and charge
every failed solver attempt to that one target; a planted success alone
would not establish a speedup. If the fixed-gauge control also fails under
the same bound, favor alternative PDP structure such as target-adaptive
pair/root indexing or compact elimination over adding more SAT gates.
Natural-query relation yield, useful rank, final matrix work, target descent,
verified logarithm, paired rho time and an `IC1` candidate ID remain `null`.

From this branch, verify the committed sources and receipts with
`shasum -a 256 -c experiments/ecc2k130-orbit-w24-m5-sat-20261006/SHA256SUMS`.
Run `python3 -m unittest discover -s
experiments/ecc2k130-orbit-w24-m5-sat-20261006 -p selftest.py` for the
focused circuit and group controls. The archived formula can be checked
without Sage using `verify_xcnf.py --strict-run-dir
experiments/ecc2k130-orbit-w24-m5-sat-20261006/runs/planted-r2
--witness-dir experiments/ecc2k130-orbit-w24-m5-sat-20261006/runs/witness-r2
--out /tmp/orbit-w24-m5-check.json`. Replay the archived group record with
`/Volumes/SSD990/cryptanalysis/sage -python` on `verify_sage.py`, passing
the intact `runs/planted-r2` directory and a fresh `--out` path. For a new
measured attempt, save `--runtime-info` before the producer starts; its
receipt must bind that exact runtime file.
