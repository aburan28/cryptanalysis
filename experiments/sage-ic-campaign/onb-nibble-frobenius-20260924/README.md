# Adaptive ONB Frobenius table setup

The local and IC runner ONB field copies delay construction of the hot
exponent-1/2 byte tables on degree-131 fields until the 36th call for each
exponent. Earlier calls use the original exact bit-permutation loop. The
degree-5 and degree-9 route is unchanged. Both field copies remain identical.

The initial `intent.json` and `window_probe.py` cover 4-8 bit lookup windows.
The smaller windows reduced setup but missed its frozen warm-throughput gate.
`intent-adaptive.json` freezes the accepted experiment's workload and gates.
`adaptive-run-a.json` and `adaptive-run-b.json` hold alternating warm paired
timings. `adaptive-cold.json` and `adaptive-cold-b.json` contain independent
sets of seven alternating fresh processes per side and point outcome. The
parent source is frozen at `baseline/field.py`.

Run from repository root:

```sh
python3 experiments/sage-ic-campaign/onb-nibble-frobenius-20260924/verify_archive.py
```

These are arithmetic-stage CPU measurements; complete verified IC or DLP cost
is not established here.
