# Q1429 first freeze: control-loader failure

The first frozen source is commit `7af5fb894`. Its
[`freeze.json`](freeze.json) was written before any Q1429 timed search.
The correctness command
`python3 experiments/compact-s3-m4-fixed-output-20261010/test_formula.py`
failed while loading the deliberately wrong fixed-output formula:
`StatsSolver.load_formula` asserted when CryptoMiniSat reported a
root-level contradiction from an XOR row. That is the expected answer
for the false-output control, but the test wrapper treated it as a
producer error. No twelve-cell measurement was started under this
freeze. Version 2 records `UNSAT_ROOT` separately in that control and
keeps the timed formula, solver limits, and frozen inputs unchanged.
