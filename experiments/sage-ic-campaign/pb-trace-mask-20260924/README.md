# Polynomial-basis trace mask

This archive measures `CurvePb.trace` in both local and tracked runner curve
sources. The incumbent repeatedly squares a field element and XORs its
conjugates. The candidate uses Newton identities on the irreducible field
polynomial to derive the trace of each polynomial-basis coordinate, then
returns the parity of the masked input. The mask is built lazily on the first
canonical trace. Noncanonical inputs retain the old calculation.

Frozen intents bind exact baseline and candidate curve snapshots, field
sources, benchmark, and runner by SHA-256. Primary and independent
confirmation runs each contain eight fresh-process cells for the two source
copies at degrees 11, 15, 53, and 131. Each cell measures the first single
call, including mask construction, then 12 balanced rounds of 256 traces and
64 complete `pointFromX` calls. Receipts retain exact checks, operation,
verification and cleanup times, and peak RSS. Fixture generation is excluded.

`test_trace.py` compares every trace input in degrees 2–8, random wide-field
traces, and point recovery over odd-degree fields. `pointFromX` uses half
trace and is exercised only at supported odd degrees. Verify the frozen
receipts with:

```sh
python3 experiments/sage-ic-campaign/pb-trace-mask-20260924/verify_archive.py
```

These are trace and point-recovery costs, not an end-to-end index-calculus
speedup. A complete DLP claim still requires all phases and verified log
recovery on a frozen workload.
