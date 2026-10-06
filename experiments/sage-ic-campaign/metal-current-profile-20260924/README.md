# Current installed Sage CPU/Metal rebaseline

`intent.json` freezes eight complete-call cells and installed source/binary
identities. `run-001/` retains one fresh Sage process per cell and twelve
balanced orders of native Sage, CPU table, and Apple Metal. A separate frozen
`intent-stages.json` defines four phase-profile cells in `run-stages-001/`.
Every cell verified ordinary Sage points against the native result.

The earlier 1,024-point smoke was a pilot and is excluded from the frozen
results. No machine-specific binary is committed. The portable check is:

```sh
python3 experiments/sage-ic-campaign/metal-current-profile-20260924/verify_archive.py
```

`run.py` and `run_stages.py` reproduce the device timings with the installed
Sage and Apple Metal access. They place Sage's cache under `/private/tmp`.
This is a Sage point-call comparison, not a complete IC or DLP measurement.
