# R2 launch correction

R1 preserved all four `PRODUCER_FAILURE` cells. Each stopped before search
because the sandbox denied `ps -o rss= -p <pid>`, which the runner uses for its
4 GiB fail-closed RSS guard. The frozen formulas, solver binary, four-cell
order, matrix settings, and caps in `CONFIG.json` remain unchanged.

R2 uses `--run-id R2` with the same runner under local execution where the
RSS probe is permitted. The `ps -o rss= -p $$` preflight returned exit code 0
and a numeric RSS reading. The runner change only makes the run directory
explicit; it refuses to reuse R1. Both attempts remain in the repository,
and only R2 may be interpreted as a solver-stage measurement if it reaches
matrix initialization and live search.
