# Frozen full-subgroup evidence, run-20261014T1901Z

Performance ran in crypto on the single current x86-64 VM. The snapshot was
acknowledged paused at Unix time 1792005707. The copied `PAUSE`, `paused.json`
and startup `active.json` describe that archival moment, not current health.
The live worker is outside this directory and is resumed after archival.
Never modify this directory for later progress.

- `public/`: 16 exact public jobs, eight per subgroup. No planted scalar inputs.
- `calibration-a0/`, `calibration-a1/`: per-round matched-prefix records and
  host observations; five A/B pairs per curve plus controls, no full solves.
- `reference-*`: 27 complete optimized a=1 solves, process-boundary durations
  and independent E/Jacobian verification receipts, eight distinct targets.
- `campaign/`: exact collision tables, lane histories, coefficients and state
  at the pause; completed candidates and verification receipts identify ten
  completed resumable runs at this snapshot. The first native Cantor Q_0 run
  is complete; larger a=0 jobs and later a=1 targets are censored observations.
- `replay-*`, `mirror-replay-*`: identical restart receipts from both checkouts,
  including their actual checkpoint fixtures. This is not independent-host
  replay or an ecbench audit.
- `snapshot.json`: native Rust summary; every plotted value originates here.
- source/binary binding files and `TOOLCHAIN.txt`: implementation provenance.
- `SHA256SUMS`: relative-path byte hashes of the complete frozen evidence.

Reference source: crypto d38a85f7e1ac02358223b58d71633f71f2efa7fa.
Resumable source: crypto dbd33f00da0a0ac35f285603ec168ad9d91a1d79.
Source tree dirty flags in host captures reflect untracked/generated study
artifacts; per-file source bindings and the committed revisions are retained.
The held-out witness file and executable binaries are not in this archive.
Build from the pinned source/lockfile; binary identities and original local
locations remain in the binding files. Original binary copies remain in the
current-workspace measurement directory.

All wall values are exploratory L0. No common priced-work ratio or admitted
speedup is supplied. See ../../REPORT.md and ../../RESUME.md.
