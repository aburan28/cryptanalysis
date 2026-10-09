# Q1373: N83 d12 canonical-root cardinality sample

## Measured result

The exact Q1104 d12 base has 337,146 usable points and 2,031 folded columns over the frozen GF(2^83) Koblitz curve. The pilot examined 1,000,000 deterministic coprime-stride states sampled without replacement from the 342,371,763-state pair domain. The frozen target and base receipts are in the protocol and freeze receipt.

The native stage found 1,000,000 satisfiable states and 1,997,671 distinct canonical root keys in its single-value table. Two roots were offered per satisfiable state, for 2,000,000 projected descriptor insertions; 2,329 keys collided with an earlier entry. The corrected key-retention fraction is 1,997,671 / 2,000,000 = 0.9988355. The distinct-key count is 1.997671 per sampled state.

The table intentionally stores only the first descriptor for a repeated key. A complete relation index must preserve every descriptor attached to a root key, so the small collision count does not justify dropping those records. The pilot therefore recalibrates key cardinality; it does not reduce the complete-index record requirement.

The sampled target scan tested 1,000,000 states and found zero table hits. The native run status is state_cap_no_relation. Index build time was 817.390 ms; the sampled target check took 2.663 s; total native process time was 3.873 s. Peak RSS was 276,561,920 bytes. These are stage diagnostics for the bounded sample.

## Storage gate

At the measured preflight, the 16-byte-per-descriptor Q1371 projection was 10,955,896,416 bytes. The fresh free-space snapshot was 1,581,076,480 bytes on SSD990 and 10,485,293,056 bytes on the system volume. With the frozen 1.25 GiB reserve and 64 MiB sort-temporary cap on each volume, the best modeled 24/232 bucket split still missed each reserve by about 0.85 GB. The full index build was not started.

The remaining payload budget across those two volumes was 9,247,797,248 bytes, or 13.506 bytes per projected descriptor. A successor design can test sorted key deltas with complete descriptor postings against that bound. The native single-value table is not a substitute for that complete index.

## Record correction

The generated run_record.json is preserved as written. Its field sample_unique_key_fraction contains 1.997671 because the wrapper divided distinct keys by satisfiable states. That value is a count per state, not a fraction. The corrected fraction, 0.9988355, and all source hashes are recorded in runs/q1373_d12_root_cardinality_1m_sample_20261009/run_record_correction.json.

## Reproduction and claim boundary

The checked Sage runtime receipt was saved before launching the native sample. The frozen native source, binary, factor-base keys, basis bridge, and mapped representatives are retained under inputs. The run sampled one index-state subset and one target scan. It did not build a complete index, complete an ordinary target query, collect a factor-base relation system, solve a matrix, or recover a discrete logarithm. It is not a one-target IC versus rho comparison.

Run command from the repository root:

    ./sage -python experiments/koblitz-n83-index-design-20260929/Q1373_D12_ROOT_CARDINALITY_PILOT_20261009/run_pilot.py
