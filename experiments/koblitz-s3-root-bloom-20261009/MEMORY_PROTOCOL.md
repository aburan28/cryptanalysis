# Supplemental peak-memory probe

The five-pair timing panel's internal `ps` RSS field is null in this sandbox.
This supplemental probe starts a **fresh Python interpreter for each solver
process** and reads `resource.RUSAGE_CHILDREN.ru_maxrss` after the child exits.
On macOS the raw value is bytes. The probe uses the same frozen binaries,
public point, 14 workers, and source-bound workload as the timing panel.

Run three fresh-process pairs in order `AB, BA, AB`, where `A` is the exact
table and `B` the canonical-root Bloom candidate. Each solver has a 20-second
wall cap and each worker process a 30-second outer cap. Keep timeout and
process-failure rows. Verify output status and first-witness semantics before
comparing peak memory. This panel measures memory only; online wall values
from these runs are diagnostics, not an isolated CPU speed result.
