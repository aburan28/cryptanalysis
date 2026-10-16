# Local smoke (correctness only, 2026-10-15)

This ran on a shared 4-vCPU cloud-agent VM (rustc 1.97.0; the runner pins
1.99.0). The VM's clocks are not evidence, so this receipt holds no timing
claims, and the timing fields in the raw outputs were discarded. The smoke
ran against a draft of `protocol.json` whose sources were byte-identical to
the frozen ones. The final freeze changed only the digests and the
timestamp.

- **Build and tests.** The online crate's 6 producer tests pass, including
  the three Feistel bijection tests, and so do the tuned rho's 4 tests. The
  `lift2` crate's 24 tests pass, including the exhaustive ones. B's
  factor-log table re-verifies in the pinned oracle
  (`log-table-check.json`, PASS).
- **Derivation.** On the same restored input, each parent's own
  `make_online_source.py` reproduces its frozen producer digest. The
  combined derivation then applies both edit sets in sequence, and
  `--check` is byte-identical.
- **Primary panel, points p000-p002** (`primary_slice0-3_identities.json`).
  Each of the six primary arms (`pB`, `pL`, `pF`, `pLF`, `pLFaa`, `pX`) ran
  as one `arm.py` process on slice 0:3, plus the tuned rho on each point.
  All 9 runs gave verified=1 with 0 issues.
  - lift_scan reproduced the full scan's probes and relation in the
    left-major order (3/3).
  - `pF`, `pLF`, `pLFaa` and `pX` had identical probes and relation (3/3).
  - All six IC arms and the tuned rho recovered one scalar per point.
- **Segment O1 through the real runner and verifier**
  (`correctness_O1.json`, `verify_receipt.py --correctness-only`). The four
  arms (`oB`, `oL`, `oF`, `oLF`) on Q0 and B's 16 fresh points were all
  valid, and all of these hold on all 17 points:
  - the left-major arms reproduced the archived left-major probes and
    relation of BL-arm run 38689817618;
  - the Feistel arms reproduced the archived Feistel ones of run
    38786433493;
  - every scalar equals the archived one and replays in the oracle;
  - Q0 equals the validation sidecar.
- **Analysis dry run.** The full analysis on that partial receipt, and on
  synthetic rows for all 576 primary points, ran to a decision. Its outputs
  were discarded.
