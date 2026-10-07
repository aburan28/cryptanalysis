# Selective-preparation mixed τ alphabet: fresh holdout

The recoder, preparation graph, protocol, and deterministic Sage input
generator were frozen in `73e28e0b` before the new 256-case panel was
generated. The original 64 cases were design data. The earlier
portfolio holdout had already been inspected and was not reused as
new evidence. The new panel's scalar/base input digest is
`08b1b9f530265a68297d0292c08457018c14710b5ec644ecc7edacf927e8ef48`;
its fixture SHA-256 is
`5705602ef62fbe0c5ba41b4c996e5fe84745c48ba2e2934297508c2e27f20ca4`.

The candidate offers original and alternate digits in the same
width-four residue classes. A bounded carry preserves the original
`a+bτ` representative. A finite dynamic program chooses a complete
digit stream and charges only the seed points needed to evaluate it,
including their preparation dependencies, unit rotations, orbit
images, and cached projective powers. Its horizon is the baseline
expansion plus **16 carry-tail positions**. Every selected stream
reconstructed the exact short representative, every carry respected
`N(c)≤896`, and a separate recount matched its reported evaluator
cost. The saved result includes per-case digit hashes, used and built
seeds, preparation/evaluator costs, and search-state peaks; the maximum
was 615 states on the fresh panel.

| Panel | Cases | Frozen three-table selector `M+S` | Selective mixed `M+S` | Saving |
| --- | ---: | ---: | ---: | ---: |
| Original design | 64 | 87,632 | 87,298 | 334 (0.381%) |
| **New Sage holdout** | **256** | **350,664** | **348,775** | **1,889 (0.539%)** |

On the new panel, 162 cases have a smaller source count and 94 tie.
The mean saving is 7.38 `M+S` units per scalar. A 5,000-resample
paired bootstrap of the saved 256 savings, seeded `20261007`, gives
a descriptive 95% interval of **6.21–8.57 units per scalar**. This is
input variation, not timing uncertainty. The fixed original atlas
would cost 354,429 units and the fixed linked atlas 352,469 on these
same inputs. The mixed result saves 5,654 (1.595%) versus original
and 3,694 (1.048%) versus fixed linked, with preparation charged to
each individual scalar. These are exact **field-operation source
counts**, excluding dynamic-program search CPU work, short-scalar
reduction, and final inversion.

The checked repository Sage launcher wrote
`selective-runtime-info.json` with `status: verified` before the new
fixture job. The independent point replay first stopped on an absent
optional `expected_identity` key in the legacy 64-case fixture. That
schema failure is preserved in `selective-sage-first-attempt.json`.
After the validator fix in `bbd5258a`, checked Sage directly evaluated
every selected digit as a curve point and matched **all 320 scalar
outputs** across the original and fresh panels. Its receipt,
`selective-sage-replay.json`, records 11,158 nonzero digit terms,
source/fixture/runtime hashes, and a digest of the verified outputs.
The raw selector result SHA-256 is
`efb60638f4b443906ce8dd095af1b986c14b47f9424874ba4c7a7d0705eeec31`;
the successful Sage replay receipt SHA-256 is
`c155049fd03e79f734b615da868dda52881a890212c11778986a58926ad3aa00`.

The selective point preparation and 12-orbit evaluator have **not yet
been implemented in the native release path**. A native correctness
replay, then a paired full-operation run on an isolated physical host,
must charge the dynamic program and all conversion/point work before
any CPU speedup claim. This variable-time experiment is not ready for
secret scalars. Finite τ-adic transducers have
[prior art](https://eprint.iacr.org/2008/153.pdf); academic novelty
is unproved.
