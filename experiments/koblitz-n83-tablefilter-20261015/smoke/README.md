# Local smoke (correctness only, no timing evidence)

Cloud-agent VM (shared 4 vCPU Intel Xeon guest, THP `madvise`), rustc 1.97.0
(the runner pins 1.99.0), 2026-10-15/16. Binaries built from this directory's
derived producer (`70233510…`, `make_online_source.py`) and profiler
(`cf2de8aa…`) against the digest-checked r770 library. The derivation first
reproduces the probe-pipeline producer's frozen digest `840b1648…`. The build
has no warnings in the derived examples.

- **Tests.** `cargo test --release --locked --bins`: 9 producer tests pass,
  among them the three new `table_filter_tests` (slot round trip and overflow
  refusal; the same key → value map in every layout and no filter false
  negatives on a 9-orbit n = 83 base; on 24 planted four-point targets with
  lift and full canonicalizers and both scan orders, every layout, including
  a 2^13-bit filter that passes most probes, gives the pipeline's exact
  relation and probe count, finds no rejected key, and has table hits ≤
  filter passes ≤ probes). The 4 rho tests pass.
- **Full K600, one process per layout** (`producer_k600_layouts.json`; Q0,
  w08, w11; lift, Feistel, prefetch): `base`, `compact`, `filter` and
  `filter_plant` all give Q0's archived Feistel relation [77273, 22971,
  54962, 62539], probes 1,988,184 and scalar 3141592653589793, and w08 / w11
  their archived probes 161,864 / 160,866; every layout stores 29,878,182
  keys in 2^27 slots (4 GiB base, 2 GiB compact, plus a 32 MiB filter with
  41.7% of its bits set); `planted_rejected_found` = 0; filter passes on Q0
  48,439 of 1,988,184 probes (2.44%).
- **Runner, wrapper, gates and verifier** on segment P1 (64 primary points)
  and O1 (Q0 + B's 16 fresh points) with `run_schedule.py --segments P1,O1
  --one-per-arm` (one process per arm, the first rho run): 9/9 rows valid.
  `verify_receipt.py --correctness-only` gives `correctness_P1_O1.json`:
  every check true. All six IC arms have identical probes and relations on
  all 64 P1 points (134,897,365 probes in total), one scalar per point
  across them, the rho scalar on p054 equal, every scalar replayed in the
  pinned oracle; oP and oT reproduce the archived Feistel probes,
  relations and scalars on all 17 old points, and Q0 equals the validation
  sidecar. No rejected key was found in any process (pX looked up every
  one). Per-process identities: `identities_P1_O1.json`.
- A dry run of the full analysis on a copy of this partial receipt worked;
  its output was discarded (VM clocks, one slice, not evidence).
- **Profiler** (`profile/`): the diagnosis in the main README, with 2 MiB
  pages (`GLIBC_TUNABLES=glibc.malloc.hugetlb=1`) and with 4 KiB pages.

The first smoke attempt reported every new-layout process invalid because a
local variable in `arm.py`'s `check_setup` shadowed the layout argument (a
wrapper bug, not a producer one; the decoded producer output of those runs
was already identical across arms). It was fixed and the protocol refrozen
before the smoke above; no Tier 1 run had started.
