# Q20261010191500: ordinary N53 x-weight-five S3 screen

Use the same public N53 target, raw-preimage coset, balanced four-leaf S3
chain, CryptoMiniSat binary, and one-thread seed-zero settings as Q1410
and Q20261010183500. Change only each leaf's normal-x Hamming bound from
four to five. Rebuild the weight-four formula to its archived raw digest
before constructing the new XCNF. Freeze input, source, and solver hashes.

Run one ordinary search with 100,000 conflicts and 300 seconds external
wall limit. Record formula shape, solver streams, child CPU, wall, RSS,
status, and verified relation if found. For a SAT model, replay all native
XOR/CNF constraints, the selected raw target lift, all four signed points,
cofactor projection, and exact public point. The weight-five base size is
not enumerated in this bounded solver screen: retain `candidate_id: null`,
`run_id: null`, and `isogeny: "none"`; do not write an `fb` label.

Commands: `python3 experiment.py freeze`, `python3 experiment.py prepare`,
`python3 experiment.py solve`, `python3 audit.py`. Outputs refuse overwrite.
