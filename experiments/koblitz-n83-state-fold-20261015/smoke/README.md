# Local smoke (correctness only, no timing evidence)

Cloud-agent VM (shared 4 vCPU guest), rustc 1.97.0, 2026-10-15. Binaries
built from this directory's derived producer (`b91241c4…`) against an
identical, digest-checked r770 library.

`run_schedule.py --segments C1` ran segment C1 (point s000, all ten cold
arms) through the real wrapper, gates and verifier: 10/10 rows valid.
`verify_receipt.py --correctness-only` gives `correctness_C1.json`: every
arm matched B's index digests, one scalar (3385103015704021) across all IC
arms and the tuned rho, replayed in the pinned oracle; one relation per order
group ([42006, 4225, 41661, 53853] Feistel, [30140, 37233, 54535, 60117]
left-major); probes cB = cBF = cF = cFaa = cX = cFF = cFI = 152,738 (no
skipped state on this point), cBL 1,561,253 and cFL 1,547,641 (41 skipped
states, same relation). A dry run of the full analysis on a copy of this
partial receipt worked; its output was discarded.

Separately, one process per arm on Q0 (cB, cF, cX): the archived Feistel
relation [77273, 22971, 54962, 62539], probes 1,988,184 / 1,987,852 (one
skipped state) / 1,987,852 + 332 audit, identical digests, peak RSS 5,543
and 2,812 MiB. The rank arms (kB, kN) were not run locally (each is a full
rank stage); the producer tests cover the selected scan paths and the runner
gate requires B's factor-log table.
