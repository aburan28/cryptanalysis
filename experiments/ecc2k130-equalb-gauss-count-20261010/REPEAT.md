# Frozen R2 repeat of the Gaussian matrix-count gate

R1 measured two/five peak-RSS ratios 0.695306 on normal4 and 0.613987 on
W24. Because normal4 is only 0.004694 inside the 0.70 threshold and the
host has no CPU-isolation receipt, run **exactly one** additional complete
four-cell repetition, `R2`, before reporting a stable memory-gate decision.
This decision is frozen after seeing R1 and before launching R2; it is not a
new formula or solver-policy search.

Use the committed `CONFIG.json`, parent sources and binary hashes, same
normal4/five, normal4/two, W24/two, W24/five order, one thread, 60-second
internal limit, 70-second external guard, and 4-GiB RSS guard. Do not reuse
or overwrite R1 outputs. Preserve all R2 statuses, errors, transcripts,
guards, and sampled RSS, then run the same independent audit. Report both
repetitions, not a best-of-two selection.

Call the sampled-memory gate reproducible under this two-repeat protocol
only if both formulas have a two/five ratio at most 0.70 in **both** R1 and
R2, and an at-least-8,000-by-12,000 selected matrix with positive printed
elimination calls is observed for each two-matrix formula in at least one
repetition. If a process guard prevents the elimination summary, record
activity as unknown and keep this part of the gate unresolved. No change to
the held-out 16/256-query advancement rule follows from RSS alone.
