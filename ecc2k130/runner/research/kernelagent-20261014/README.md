# ECC2K-130 source-correlated GPU profile, 2026-10-14

## Frozen diagnostic before execution

The previous isolated profile and four paired screens leave the Frobenius walk's
source-level stall sequence unidentified. This run uses the same pinned public
CUDA source commit `1f8e6847de9e207880bd3be63835c3f56eb182d5`, production
v3 settings, one RTX PRO 6000, 120,320 workers, 64 steps, run ID 11000 and
DP32. It adds `-lineinfo` to the build so Nsight Compute can correlate CUDA
lines with SASS. The profile is diagnostic; a line-info binary is not the
ordinary timing baseline.

The driver [profile_source_correlated.py](../kernelagent-20261013/profile_source_correlated.py)
loads every runner source file from that commit, records their hashes, builds
`sm_120`, runs one ordinary launch, then profiles one kernel launch with
`SourceCounters` and the prior aggregate sections. Application replay creates a
fresh DP file for every pass. The run records the exact profiler command,
compiler and driver versions, binary hash, replay output, replay pass IDs,
unique DP paths, imported raw/details and CUDA/SASS source tables, and the
native `.ncu-rep` with a verified transfer hash. A run lacking any of these is
preserved as a diagnostic failure, not promoted to bottleneck evidence.

```sh
python3 -m py_compile ecc2k130/runner/research/kernelagent-20261013/profile_source_correlated.py
modal run ecc2k130/runner/research/kernelagent-20261013/profile_source_correlated.py \
  --output ecc2k130/runner/research/kernelagent-20261014/source-correlated-profile.json \
  > ecc2k130/runner/research/kernelagent-20261014/source-correlated-profile.log 2>&1
```

The code and this protocol are committed before that command. A source/SASS
table with a concentrated, interpretable PC stall sequence permits one
default-off candidate aimed at that sequence. Stall samples attach to the
waiting instruction, so a proposed change must inspect its producing
instructions too. An empty or ambiguous table leads to a bounded compiled
sequence probe and no production speed claim.

Any candidate first owes independent host arithmetic, the frozen 355-record
sorted DP32 corpus with zero drops, and fresh/checkpoint/resume compatibility.
Then it owes two alternating 64-launch paired screens with an A/A control; both
candidate ratios must exceed the A/A range before five warmed 128-launch
confirmation pairs. End-to-end cloud cost and target recovery remain separate
measurements.

## Results

Pending execution. Preserve failures and append measured results here.
