# Post-run transcript accounting amendment

All four frozen CryptoMiniSat cells exited through the 150-second external
wall guard, which prevented CryptoMiniSat from writing its final exact
conflict/restart summary. Their raw transcripts do contain periodic restart
rows proving active search. After those runs, `audit.py` was extended to
record each final printed restart index and rounded conflict display string
alongside the exact final summary fields when present. It does not convert a
rounded `K` display into an exact conflict count. No solver input, cap,
binary, command, transcript, or run receipt was changed or repeated.
The paired diagnostic now requires at least one printed restart row for each
bounded cell before calling it active search.
