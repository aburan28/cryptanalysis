# Five Sage elliptic-curve opportunities: measured outcome

All five ideas were implemented and checked. Three passed the final gates and are installed in the local Sage runtime. Singleton addition and native table construction remain on HOLD; their public dispatch changes were omitted. The shared extension retains their private experimental helpers.

## Final decisions

| Mechanism | Decision | Primary geometric mean (95% paired CI) | Confirmation geometric mean (95% paired CI) |
| --- | --- | --- | --- |
| Direct singleton addition | HOLD | 1.641x (0.973–1.867) | 1.702x (1.074–2.581) |
| NTL-to-PARI point conversion | PASS_LOCAL | 4.377x (3.896–5.071) | 4.236x (3.852–4.984) |
| Native pair preparation / Cartesian traversal | PASS_LOCAL | 1.279x (1.091–1.509) | 1.357x (1.206–1.441) |
| Native Frobenius lookup table | HOLD | 1.044x (0.830–1.291) | 1.217x (1.068–1.478) |
| Frobenius followed by addition | PASS_LOCAL | 1.732x (1.516–2.248) | 1.944x (1.704–2.172) |

PARI passed timing and fallback gates in `run-003`, but its single separate-process RSS comparison failed (255,164,416 versus 275,595,264 bytes). This failure remains in that immutable summary. A separately frozen seven-pair resource audit (`memory-intent-v1.json`) used new seeds, balanced fresh-process order, cold cache creation and warm reuse. Both mode medians passed the original memory bound: cold 265,068,544 versus 246,185,984 bytes, warm 266,403,840 versus 247,119,872 bytes (incumbent versus candidate). Candidate PARI stack usage stayed at 26,416 bytes over repeated calls, with an unchanged 8,000,000-byte stack allocation. `FINAL_DECISION.json` links both decisions explicitly; the failed row was not discarded.

## Complete-operation results

Final timing measurements included the public operation, exact output verification and output cleanup. Fixture generation, independent reference generation, process launch and common curve setup were excluded. The primary fields were GF(2^19) and GF(2^131); fresh confirmation inputs used GF(2^31) and GF(2^163). The suite used 12 balanced paired rounds, 64 calls per arm per round (8 for cold plan construction), 16 points per warm scalar call, 256 pairs, 24-by-24 Cartesian products and 256-point Frobenius calls. Cold scalar conversion used one point and charged candidate generator creation every call. These are arithmetic-component workloads, not IC/DLP measurements.

| Accepted operation | Range across the four final field cases |
| --- | --- |
| Warm small-scalar multiplication (`17P`) | 7.01–11.64x |
| Warm full-width scalar multiplication | 1.50–4.79x |
| First-use conversion plus one `17P` | 2.92–4.25x |
| `add_pairs` | 1.25–1.61x |
| `add_cartesian` | 1.08–1.31x |
| Frobenius-then-add, including final Sage points | 1.44–2.18x |

The native table candidate reduced cold-call cost in most cells, but warm-call controls and the primary confidence bound failed in the longer follow-up. The singleton candidate had promising 1.64x/1.70x aggregate medians, but its primary lower confidence bound remained below one and an unsupported-model wall-time control failed. CPU changes in these controls were much smaller than their wall-time changes. These results do not isolate a cause; both candidates remain on HOLD rather than treating scheduling variability as a proven implementation regression or ignoring failed gates.

## What changed

- Standard NTL-backed finite-field points convert polynomial coefficient bits directly to PARI FFELTs, with one generator cached on the exact field object. The prime-field fallback avoids importing or probing the native module. Custom point subclasses retain generic conversion.

- Pair validation and coordinate extraction use a guarded native standard-point path. Cartesian enumeration uses rolling native indices, avoiding Python pair tuples and block list copies while retaining block inversion.

- `frobenius_add_pairs(curve, pairs, power=1)` computes `Frobenius^power(P) + Q` with native intermediate coordinate elements and one final Sage point per nonexceptional result. The ordinary, non-NTL/custom-class fallback composes the existing APIs.

- Meson now declares the extension's cypari2/PARI build dependency.

The normal Sage Meson/Cython/C++ target also built successfully. The installed
library remains the exact binary used for the reported timings; the normal
build is an additional integration check.

```python
from sage.schemes.elliptic_curves.binary_batch import frobenius_add_pairs
results = frobenius_add_pairs(E, [(P, Q), (R, S)], power=7)
```

## Validation and provenance

- Seven new candidate test groups cover exact small-field enumeration, context switches, non-normalized points, alternate moduli, custom classes, fallbacks, scalar edge cases and exact lookup tables. Two additional groups cover PARI word boundaries through degree 256, variable names and cached point orders.

- The final installed APIs passed 33 regression groups and all 1,096 doctests (19 batch API examples and 1,077 elliptic-point examples).

- The final timing suite verified 8,866,824 outputs; the earlier completed suite verified 1,144,584. All timing rows matched independent references.

- Initial build/test/harness failures are retained: the PARI private-header include, an incorrect generic fallback ancestor, and the cold-plan thread keyword. Completed timing cells from the interrupted first run were reused with explicit receipts in `run-002`, without rerunning them.

- `intent-v1.json` through `intent-v3.json`, raw trials, execution hashes and build logs are retained. `receipt-locations.json` resolves historical source paths after candidate revisions and installation. The exact original bindings live under each run's `sources/`; the maintained bindings explicitly load the archived baseline so future reruns do not accidentally benchmark against the newly installed candidate.

- The installed native binary is exactly the measured `candidate/` binary. Selected public function ASTs match their measured versions. `install-001/` retains the installed hashes and backups; `selected.patch` applies to the archived baseline.

- Post-install profiles are in `profile-installed/`. These are diagnostic profiles, not additional speedup measurements.

The scalar-17 profile now attributes about 4% of its instrumented total to the
point input-conversion wrapper; result construction and field coercion are
visible remaining costs. This is a profile of the new runtime, not a new
acceptance measurement or a directly comparable percentage to the earlier
separated-phase audit.

No speedups from earlier campaigns were multiplied into these results. PASS_LOCAL applies to this host and frozen arithmetic workload.

## Published archive

The supporting intents, decisions, raw measurements, source snapshots, and
validation logs named above are retained in `measurement-evidence.tar.gz`.
Extract it in this directory to inspect those records. Native binaries are
identified by their recorded hashes and are not distributed in this archive;
rebuild extensions for the target platform. Reconstruct the accepted source
with the repository release manifest and run the installed compatibility suite.
