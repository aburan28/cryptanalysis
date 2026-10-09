# Bounded projected N131 d10/m15 precomputation query

The unpinned fill-limited projected XCNF ended `CENSORED_TIME` at its
580-second parent wall cap with zero solver status or model lines. The
[independent terminal audit](ordinary_precompute_R1/independent_terminal_audit.json)
matched the frozen command and hashes, raw output, drained solver process,
and result classification. The [run record](ordinary_precompute_R1/result.json)
reports 580.097 solver-stage wall seconds and 336,920,576 bytes sampled peak
parent-plus-solver RSS under the 4-GiB cap. This is one contended-host
solver-stage observation on the frozen first d10/m15 precomputation point;
its clock excludes original formula construction and projection.

The input is the exact [fill-limited projection](../n131_d10_fill_projection_20261009/RESULT.md)
of the active d10 R1 query, with 135,446 variables, 225,092 CNF clauses,
and 61,631 native-XOR rows. The solver seed is the original query's
`2026100618`; one worker and the 10,000-row/15,000-column Gaussian limits
are unchanged. Its raw log reports that the 43,467×98,315 largest XOR matrix
was still disabled by those limits. Thus the exact variable/row reduction
did not clear this bounded relation-search gate. The outcome is censored,
not an UNSAT statement or a measured ordinary-relation yield rate.

The [separate CNF-bridge method](../n131_d10_xor_bridge_20261009/RESULT.md)
preserves this point and solver seed while moving 4,040 ternary intermediate-
coordinate XOR rows into equivalent clauses. Its exact input components
fit the frozen Gaussian limits and require their own bounded solver result.
Neither stage observation enters the original candidate's precomputation
rank or the single-target online IC timing interval.
