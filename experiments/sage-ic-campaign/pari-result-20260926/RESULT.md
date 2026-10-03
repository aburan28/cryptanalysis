# Direct scalar result conversion: PASS_LOCAL

Installed the exact measured candidate v2 on this host. The incumbent was the
already optimized September 25 build, including direct PARI input conversion.
These are arithmetic-component measurements, not an IC pipeline speedup.

| Suite | Geometric speedup | 95% paired-bootstrap interval |
| --- | ---: | --- |
| primary | 1.259x | 1.182–1.324 |
| confirmation | 1.227x | 1.197–1.284 |

| Field degree / backend | Workload | Speedup | Candidate/baseline CPU |
| --- | --- | ---: | ---: |
| GF(2^19), primary | small_17 | 1.532x | 0.602 |
| GF(2^19), primary | fullwidth | 1.326x | 0.776 |
| GF(2^19), primary | cold_17 | 1.217x | 0.810 |
| GF(2^131), primary | small_17 | 1.373x | 0.747 |
| GF(2^131), primary | fullwidth | 1.070x | 0.968 |
| GF(2^131), primary | cold_17 | 1.099x | 0.903 |
| GF(2^31), confirmation | small_17 | 1.597x | 0.634 |
| GF(2^31), confirmation | fullwidth | 1.099x | 0.861 |
| GF(2^31), confirmation | cold_17 | 1.255x | 0.829 |
| GF(2^163), confirmation | small_17 | 1.313x | 0.747 |
| GF(2^163), confirmation | fullwidth | 1.046x | 0.971 |
| GF(2^163), confirmation | cold_17 | 1.126x | 0.897 |
| prime | small_17 | 1.486x | 0.728 |
| pari_backend | small_17 | 1.347x | 0.706 |
| nonkoblitz_ntl | small_17 | 1.715x | 0.610 |

All 1,818,984 timed-suite outputs matched independent scalar replay.
Each interval includes the public multiplication, exact equality, and result destruction.
Fixture generation and the common PARI curve cache are outside both arms.
Module imports are outside timing; cold means the field-generator cache, not process startup.
Cold cases include removal and recreation of the field generator cache.

All frozen gain, confidence, per-cell, CPU, and memory gates passed.
RSS uses seven fresh pairs for each of two cells; median bytes are:

- n=131 small_17: baseline 275,644,416; candidate 275,447,808.
- n=163 fullwidth: baseline 275,660,800; candidate 275,775,488.

Candidate v1 remains HOLD in `run-001/summary.json`; its control regressions
and raw timing records are preserved. V2 broadens the direct point construction
to the other standard finite-field backends, uses fresh inputs and shorter
interleaved timing blocks, and retains all original acceptance thresholds.

Validation receipts: `tests-v2-001.log`, `installed-tests-001.log`,
`hardware-installed-tests-001.log` (explicit installed-backend rerun),
`doctests-001.log`, `meson-build-001.log`, and `runtime-checks-003.json`.
The regular Meson target was compiled separately; the installed binary is
the exact independently built binary used in the accepted benchmark.

The local user shim, repository launcher and existing experiment launcher
all select the checked build. Nested `sage` commands preserve that route.
The checks reject stale hashes, wrong interpreters and inherited Python
package overrides. The installed receipt and runtime manifest bind the code
to this decision. Previously running Python processes must be restarted.

`profile-installed/` contains post-install diagnostics. `selected.patch` is
incremental against the archived `baseline/`; `runtime-source.patch` preserves
the workspace launcher on child PATH. New launcher utilities live in
`experiments/sage-binary-arithmetic/`, with the repository entry point at `sage`.

## Published archive

The supporting intents, decisions, raw measurements, source snapshots, and
validation logs named above are retained in `measurement-evidence.tar.gz`.
Extract it in this directory to inspect those records. Native binaries are
identified by their recorded hashes and are not distributed in this archive;
rebuild extensions for the target platform. Reconstruct the accepted source
with the repository release manifest and run the installed compatibility suite.
