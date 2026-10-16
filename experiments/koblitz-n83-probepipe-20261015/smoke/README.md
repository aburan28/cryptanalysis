# Local validation (correctness only, 2026-10-15)

This ran on a shared 4-vCPU cloud-agent VM (rustc 1.97.0; the runner pins
1.99.0). The VM's clocks are not evidence. The only timings kept are the
diagnostic profile's ([`profile/`](profile/), used to choose the fix and
labelled as such); the timing fields of every other local run were
discarded.

- **Derivation.** `make_combined_source.py` (claude/n83-combined's
  derivation, verbatim) reproduces the combined producer's frozen digest
  `f65e518a...` from the restored r770 input; `make_online_source.py` and
  `make_profile_source.py` then give the frozen producer and profiler
  digests. A fresh restore from `/home/user/crypto` into an empty copy of
  the experiment reproduced all three digests and `schedule.json`
  (`--check`).
- **Build and tests.** `cargo test --release --locked --bins`: the
  producer's 6 tests (including the three Feistel bijection tests), the
  profiler's 6 and the tuned rho's 4 pass. B's factor-log table re-verifies
  in the pinned oracle ([`log-table-check.json`](log-table-check.json),
  PASS).
- **Exactness, three fresh points** (w11, w08, w14; K600, verified cached
  table). `KIC_PROBE_PIPELINE=off` and `prefetch` gave identical probes
  (160,866, 161,864, 183,505), relations and scalars, under both 4 KiB
  pages and THP, and equal to the earlier combined binary's
  ([`profile/producer_k600_thp_off.json`](profile/producer_k600_thp_off.json),
  [`profile/producer_k600_thp_prefetch.json`](profile/producer_k600_thp_prefetch.json)).
- **Real runner and verifier, segments P1 and O1**
  (`run_schedule.py --segments P1,O1 --one-per-arm`, then
  `verify_receipt.py --correctness-only`;
  [`correctness_P1_O1.json`](correctness_P1_O1.json),
  [`identities_P1_O1.json`](identities_P1_O1.json)). All 7 runs valid with
  0 issues:
  - `pC`, `pP`, `pPaa` and `pX` on the 64 points of slice P1 (p000-p063):
    identical probes and relation on all 64, one scalar per point, every
    scalar replays in the oracle; the tuned rho on p043 agrees;
  - `oC` and `oP` on Q0 and the 16 fresh points reproduce the archived
    Feistel probes and relations of run 38786433493 and the archived
    scalars; Q0 equals the validation sidecar.
- **Analysis dry run.** The full analysis on that partial receipt ran to a
  decision (`invalid`, as it must on an incomplete schedule). Its outputs
  were discarded.
