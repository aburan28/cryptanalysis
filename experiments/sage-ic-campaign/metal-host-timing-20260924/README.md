# Instrumented Sage Metal host timing

This archive keeps the installed Sage bridge unchanged. `source/` holds exact
baseline CPU, Metal, and header snapshots plus a standalone Metal source that
adds only internal timers and an optional timing query. `build.sh` compiles a
temporary library under `/private/tmp`; no binary is committed or installed.

`intent.json` froze three degree-131 point counts before instrumentation.
`intent-run.json` pins the instrumented source, profiler, build script, and
built binary before timing. `run-001/` and `run-002/` are independent fresh
process repetitions with twelve alternating installed/instrumented Metal
complete point calls per cell, each checked against native Sage output.

Because the first host timings differed greatly from the earlier three-arm
rebaseline, `intent-recheck.json` froze four identical-seed native/CPU/Metal
cells. `run-recheck-001/` retains their exact output and timing receipts.
The portable check is:

```sh
python3 experiments/sage-ic-campaign/metal-host-timing-20260924/verify_archive.py
```

Reproduction on the same installation requires Apple Metal access and runs
`sh build.sh`, `python3 run.py --run run-001`, then
`python3 run.py --run run-002` and `python3 run_recheck.py`. The runners place
Sage's cache under `/private/tmp`.
