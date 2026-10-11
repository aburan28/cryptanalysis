# Q20261010184000: N53 x-weight-four solver-setting sweep

Use Q20261010183500's exact archived ordinary formula, public point,
factor base, and CryptoMiniSat binary. Run four prespecified single-thread
cells at 100,000 conflicts and a 300-second external wall cap each:
`polar=false`/automatic restart, `polar=true`/automatic restart,
`polar=false`/Luby restart, and `polar=false`/geometric restart with seed
one. Preserve solver streams, child CPU, wall, memory, exact status, and
model replay for every cell. Run all four cells even if one returns SAT.

This is a parameter screen, not a calibrated CPU speedup. A SAT model
must satisfy the serialized native-XOR XCNF and the exact projected base
and full-point group law. A capped attempt remains `BOUNDED_UNKNOWN`.
Freeze the source/input/configuration before launching; refuse overwrite.
Commands: `python3 sweep.py freeze`, `python3 sweep.py run`, then
`python3 audit.py`.
