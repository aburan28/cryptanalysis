# Audit scratch placement and peak-memory reporting

The first independent audit invocation failed while reconstructing a control
XCNF because Python's default temporary directory resolved to the nearly
full repository volume (`OSError: [Errno 28] No space left on device`). No
solver or construction job was restarted. The auditor now accepts an explicit
`--scratch-dir`; the successful replay used `/private/tmp` and generated
temporary XCNFs from the committed gzip base plus unit deltas. A later audit
row correction includes the solver child's `ru_maxrss` peak alongside the
sampled RSS peak: the subsecond positive/negative processes can finish before
the periodic sampler observes their true maximum. The source/input hashes,
solver receipts, raw logs, and acceptance checks were unchanged.
