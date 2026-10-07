# N83 shifted-base S3 encoding gate

The [frozen protocol](shifted_pdp_protocol.json) built one implicit-S3 XCNF
branch for each of the seven- and eight-summand shifted bases on the **same
first raw fiber** of the previously frozen ordinary N83 public target. The
checked Sage launcher ran each builder after a local `--runtime-info` receipt.
The outer watchdog measured process-tree RSS and enforced a 240-second,
2 GiB envelope. The [builder](build_shifted_s3_circuit.py) reports circuit
construction and XCNF serialization separately, excluding Sage startup and
input loading from those inner timings. This is an encoding diagnostic, not a
SAT solve or a complete target PDP measurement.

| Formulation | Factor coordinates | Unrestricted intermediate x coordinates | S3 links | Variables | CNF clauses | XOR rows | XCNF bytes | Build / write, exploratory | Guarded process-tree peak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Shifted `m=7,d=12` | 84 | 415 | 6 | 148,397 | 430,521 | 4,557 | 8,952,261 | 1.012 / 0.020 s | 86,310,912 B |
| Shifted `m=8,d=11` | 88 | 498 | 7 | 171,204 | 496,634 | 5,267 | 10,552,864 | 1.370 / 0.038 s | 86,851,584 B |

The earlier full W3/W4 five-summand circuit had 98,846 variables, 277,748
CNF clauses, and 5,855 XOR rows on its planted branch. Its factor-coordinate
count was 415. That prior branch was not the same target, so the comparison
is structural only; the S3 link count and side constraints differ. The new
shifted circuits have fewer factor coordinates but more S3 links and larger
variable and clause counts. Neither encoding size nor the geometric tuple
count predicts CryptoMiniSat's ordinary-query solve probability.

The first `m=7` outer launch [failed its RSS guard](runs/shifted_m7_d12_s3_encoding_v1/guard_failure.json)
because sandbox process inspection was denied. Its completed child receipt
is retained as an invalid-guard diagnostic. The [controlled retry](runs/shifted_m7_d12_s3_encoding_v2/outer_receipt.json)
and [matched `m=8` run](runs/shifted_m8_d11_s3_encoding_v1/outer_receipt.json)
both have `guard:null`, exit code zero, and `ENCODING_COMPLETE` inner receipts.
The large XCNF files remain local and are excluded from Git; each committed
receipt records its size and SHA-256 for exact regeneration.

No planted shifted-base witness has been replayed through these circuits, and
only one of four raw target fibers was encoded. There are no SAT statuses,
verified decompositions, ordinary-query yield rates, factor logs, target
DLPs, paired rho measurements, or speedup estimates. All such costs stay
`null` in the [one-target cost model](COST_ACCOUNTING.md).

The next solver design decision must price the full witness-search phase.
For a plain S3 SAT route, first test a known planted shifted decomposition
with independent group replay and small-field false-lift controls, then run
ordinary queries across all four fibers at a fixed cap. A distinct hybrid
route could index pair sums: the `m=8,d=11` geometry has 4,072,324 logical
pairs per distinct pair of slots, with 65,157,184 bytes of raw explicit-record
payload per table under the declared storage model. Four such tables would
carry 260,628,736 raw bytes before indexing, duplicates, allocator overhead,
I/O, or search. No pair table has been built or searched, so this is a design
size, not a measured MITM cost or a solver feasibility result.

The [follow-up SAT gate](SHIFTED_SAT_GATE.md) performed planted replay,
small-field controls, and all four ordinary fibers for both geometries under
one frozen solver envelope. It preserves the timeout rows and makes no
end-to-end speed claim.
