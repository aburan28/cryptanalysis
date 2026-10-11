"""Fresh-process runner for one (algorithm, N) pair of the SSS positive control.

Invoked by sss_benchmark.py as

    python3 sss_runner.py <upstream_dir> <algorithm> <N> <result_json_path>

Imports (and the sympy prime sieve warm-up the upstream code performs at
import) happen *before* the clock starts; only the factorisation call is
timed.  Upstream prints the factors rather than returning them in two of the
three algorithms, so stdout is captured and parsed; the parsed factors are
written to the result file and re-verified by the parent.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import resource
import sys
import time

upstream, algorithm, n_str, out_path = sys.argv[1:5]
N = int(n_str)
sys.path.insert(0, upstream)
sys.path.insert(0, os.path.join(upstream, "sssif"))

# Upstream ssiqs.py's SymPy SIQS parameter table (test.py), for 30-digit inputs.
def sympy_params(digits: int) -> tuple[int, int]:
    table = [(34, 200, 65536), (36, 300, 65536), (38, 400, 65536), (40, 500, 65536), (42, 600, 65536),
             (44, 700, 65536), (48, 1000, 65536), (52, 1200, 65536), (56, 2000, 65536), (60, 4000, 65536 * 3)]
    for lim, nf, m in table:
        if digits <= lim:
            return nf, m
    return 6000, 65536 * 3


buf = io.StringIO()
if algorithm == "sss":
    import sss  # noqa: E402  (upstream sssif/sss.py)

    def run():
        sss.SSS(N)

elif algorithm == "psiqs":
    import psiqs  # noqa: E402

    def run():
        f = psiqs.siqs(N, verbose=False)
        print(f"Proper factors found: {f} | {N // f}")

elif algorithm == "ssiqs":
    import ssiqs  # noqa: E402
    from sympy.ntheory.generate import prime  # noqa: E402

    nf, m = sympy_params(len(str(N)))
    bound = prime(2 * nf)

    def run():
        ssiqs.qs(N, bound, m)

else:
    raise SystemExit(f"unknown algorithm {algorithm}")

rc = 0
cpu0 = time.process_time()
t0 = time.perf_counter()
try:
    with contextlib.redirect_stdout(buf):
        run()
except SystemExit as e:  # upstream exits through sys.exit on some paths
    rc = 0 if e.code in (None, 0) else 1
    buf.write(f"\n[SystemExit {e.code}]\n")
except Exception as e:  # pragma: no cover
    rc = 2
    buf.write(f"\n[Exception {type(e).__name__}: {e}]\n")
elapsed = time.perf_counter() - t0
cpu_elapsed = time.process_time() - cpu0
peak_rss_kB = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

text = buf.getvalue().replace("\b", "")
m = re.search(r"Proper factors found:\s*(\d+)\s*\|\s*(\d+)", text)
factors = [int(m.group(1)), int(m.group(2))] if m else None
with open(out_path, "w") as fh:
    json.dump(
        {
            "algorithm": algorithm,
            "N": N,
            "elapsed_s": elapsed,
            "process_cpu_s": cpu_elapsed,
            "peak_rss_kB": peak_rss_kB,
            "factors": factors,
            "returncode": rc,
            "stdout_tail": text[-600:],
        },
        fh,
    )
