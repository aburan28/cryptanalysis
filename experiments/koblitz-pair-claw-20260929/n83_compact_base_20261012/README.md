# Compact signed-Frobenius factor-base access for N83

The native pair-claw collector can access a factor base through one canonical
point per 166-point signed-Frobenius orbit. A precomputed byte table converts
rotated normal-basis coordinates into the collector's polynomial basis; the
canonical polynomial point is cached. The implementation expands a point only
when its index is used. It preserves the exact index order and group-law
meaning of the eager 166-point expansion.

On the fresh public point of workload `1bd8900e972e`, the 23,859-orbit base
has **3,960,594 actual usable points before folding**. The compact and eager
collectors gave equal values for all twelve recorded M20/R18 lookup fields,
including query counts, false positives, exact hits, and hit witnesses. With
the complete point audit enabled, the compact native process reported
6,242,304 peak RSS bytes; the eager reference reported 164,069,376 bytes.
These runs were on an unisolated local ARM host. Their CPU times are stage
diagnostics. The matched lookup found zero exact hits in this bounded cell.

`compact_base.inc` is the current access implementation. The v1 and v2
sources are retained beside it because their measured source hashes occur in
the frozen first two receipts. The third receipt was built with
`COMPACT_BASE_AUDIT=1` and checked every expanded point against repeated
Frobenius squaring and sign conversion. `verify.py` checks the three receipts,
their source hashes, the parent workload and base, exact result parity, and
the memory reduction.

`build_large_base.py` extends the verified seeded scalar stream from 48,194
to 200,000 distinct orbits. The resulting base has 33,200,000 usable points
before folding and a 3,319,983,400,000-descriptor pair domain. Its compact
access and independent Sage log replay are separate gates. The build receipt
includes the full parent-set equality check, file hashes, and selected
group-law replays. `verify_large_sage.py` checks every canonical log in an
independent polynomial-basis Sage model using the repository's checked Sage
launcher. `run_large_stage.py` then pairs eager and compact collectors on
identical M20/R18 descriptor and target ranges, preserving build and runtime
failures in `large_stage.json`. The source and workload receipts bind each
stage; no `IC1` candidate ID is assigned until the complete pipeline is
specified.

The 200,000-orbit base builder completed in 736.94 exploratory local seconds,
matched the entire 48,194-orbit parent set, and saved a 6,400,000-byte
canonical key/log file. In its matched M20/R18 stage, both collectors
processed 1,048,576 table descriptors and 262,144 query representatives,
with 29,114 Bloom positives, all false positives, and zero exact hits. Peak
RSS was 1,333,346,304 bytes for eager access and 18,972,672 bytes for
compact access. The independent checked-Sage replay verified all 200,000
canonical logs in 276.48 exploratory local seconds. A second native build
with `COMPACT_BASE_AUDIT=1` checked all 33,200,000 indexed points against
repeated field squaring and sign conversion, then reproduced the same twelve
lookup fields. `verify_large.py` checks the Sage receipt, full expansion
audit, source hashes, and eager/compact stage parity together.

Reproduction from the repository root:

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_compact_base_20261012/verify.py
python3 experiments/koblitz-pair-claw-20260929/n83_compact_base_20261012/build_large_base.py
./sage --runtime-info > experiments/koblitz-pair-claw-20260929/n83_compact_base_20261012/sage_runtime_info.json
./sage -python experiments/koblitz-pair-claw-20260929/n83_compact_base_20261012/verify_large_sage.py
python3 experiments/koblitz-pair-claw-20260929/n83_compact_base_20261012/run_large_stage.py
python3 experiments/koblitz-pair-claw-20260929/n83_compact_base_20261012/run_large_audit.py
python3 experiments/koblitz-pair-claw-20260929/n83_compact_base_20261012/verify_large.py
```

Each producer refuses to overwrite a frozen terminal artifact. Save
`./sage --runtime-info` before the Sage replay.
This experiment measures base representation and stage lookup parity. A
single-target online comparison still needs target-dependent query waves,
scalar recovery and independent replay, plus same-point rho under the declared
resource tier.
