# Q20261010181200: one-million-conflict N83 sorted-leaf cell

Replay Q20261010180700's exact sorted-leaf XCNF with the identical solver
binary, one thread, and seed zero. Increase only the conflict limit from
100,000 to 1,000,000; use a 600-second external wall cap. Freeze source,
input, and binary digests first. Preserve solver streams, exact conflict
count, child CPU, wall time, peak RSS, and any model with complete formula
and group-law replay. `INDETERMINATE` at the conflict or wall limit is
`BOUNDED_UNKNOWN`. Run `python3 runner.py freeze`, `python3 runner.py run`,
and `python3 audit.py`; outputs refuse overwrite.
