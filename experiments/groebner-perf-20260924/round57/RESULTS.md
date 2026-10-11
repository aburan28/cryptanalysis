# Initial local validation and timing admission

The physical Apple M4 Pro preflight passed all 214 case/arm/sanitizer rows:
106 verified results and 108 retained work-budget failures. The verified rows
comprise 70 complete planted PDP queries and 36 algebra controls. Both native
implementations and their independent checkers were rebuilt on this host.
Every F4 proof and integer trace matched the frozen round56 screen, successful
canonical bases agreed across arms, and the independent Python audits passed.
All seven measurement rejection/acceptance tests passed.

The first timing attempt admitted no queries. Both admission observations had
one-minute load 83.3193, above the frozen threshold of 14 logical CPUs. The two
rejected admissions and all 31 remaining unrun trials are retained. Thus:

- Qualified trials: zero.
- Measured complete-query speedup: unknown.
- Primary performance acceptance: false.
- The 2x target: not established.

These are missing measurements, not evidence of a performance regression. Do not
use the preflight's diagnostic durations as eligible timing samples.

Two earlier setup failures are retained separately. The first was macOS rejecting
the legacy evaluation build's dynamic UBSan runtime before queries began; the
benchmark now uses trap-mode UBSan with unchanged optimized evaluation flags.
The second was the local sandbox denying CPU-model metadata. The successful
preflight and admission attempt ran with the required hardware-metadata access.
Neither setup failure produced a native query correctness result.

`results/index.json.gz` hashes the retained preflight, timing report, analysis,
build receipt, exact source snapshot, setup failures and unit-test log. The full
rebuilt binaries remain with the external local evidence and are uploaded by CI.
Linux/macOS CI each executes the same frozen plan on its own rebuilt binaries.
Each runner's timing outcome must be assessed separately; a correctness pass or
a hosted-platform result is not a physical-M4 or universal speedup claim.
