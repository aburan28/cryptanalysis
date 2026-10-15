# Bounded EC discrete-log scan: scoped performance result

Date: 2026-10-15. Classification: **engineering**. Status: **retrospective exploratory measurement**; the protocol and results are published together. This result covers `src/pohlig.c` only.

## Change and correctness

- `ca_dlog_prime_order` now selects BSGS for an EC interval when `hi - lo >= 256` under `CA_SOLVER_AUTO`; the Z_p threshold stays at 4096. The 4,095-candidate case therefore uses the existing verified BSGS implementation. A caller-specified BSGS cap below an EC interval under 4096 keeps the existing brute-force fallback.
- Explicit `CA_SOLVER_BRUTE` and smaller EC AUTO scans use 64-candidate batches when `hi - lo >= 63`. Prefix doubling builds fixed offsets; each block shares one field inversion. Candidates are compared in increasing exponent order. Setup, computed candidates, and block advances are charged to `group_ops`.
- `tests/test_pohlig.c` checks the serial/batched boundary, both sides of the AUTO switch, a caller-specified low BSGS cap, first and last candidates, misses, and an interval ending at `UINT64_MAX`. `build-speed-pohlig-cand/test_pohlig` returned `ok: 245 checks`. Each benchmark answer was also independently replayed as `got * G == Q` inside its timed loop.

## Frozen input and build

Baseline revision: `53a53f6824be9915d93e0cadfdbcb55c0348a7ba` (`origin/main` at branch creation). Candidate: this PR's `src/pohlig.c` and `tests/test_pohlig.c` changes. Both static libraries used `cmake -S . -B <build> -DCMAKE_BUILD_TYPE=Release -DCA_BUILD_TESTS=ON -DCA_BUILD_TOOLS=ON -DCA_BUILD_SHARED=OFF`, then `cmake --build <build> --target ca_perfbench test_pohlig -j 4`. Compiler: Apple clang 17.0.0, arm64 Darwin 25.6.0. Baseline library SHA-256 `5b4ac89a233162d9ad50a856962ed475e4cbb197406b30681c7b772b156f0613`; candidate library SHA-256 `ff0ea00374d5ee0725af2cfb7263ecbb432622a1173c65b945f2c2497089e2ba`.

The fixed EC instance is `y² = x³ + x + 230` over p=`2147483659`, declared prime order `2147540641`; `ca_group_find_generator` selects `G` with seed 1. For each width, 48 separate targets use `lo=987654`, `x_i = lo + (997*i + 111) % width`, `Q_i = x_i G`, and interval `[lo, lo + width - 1]`. The runner calls the public API separately for each target with BRUTE, BSGS, and AUTO. Target construction is outside the timer; each timer includes solver work and a separate scalar replay. No table is shared between calls.

The full-width wall probe source SHA-256 is `7d279871e1428276a8126e2d67f1d4d28599b90bb3f01d095422e00663508d5d`. The width-64 variant replaces `width = 4095` with `width = 64` (SHA-256 `a73f0c75cb5ef654498779fa8a13d12e8fa52fdfa52f72158c213f2a3b3d3765`). The CPU probe replaces `CLOCK_MONOTONIC` with `CLOCK_PROCESS_CPUTIME_ID` (SHA-256 `1a5a49bc77f89aba514ab7b9aa0a40ded71dcd47122c8b470d16f16ab32b909f`). Each binary was linked to its matching static library using `cc -O3 -Iinclude <probe>.c <library>.a -lm -lpthread`. The baseline/candidate full-width wall binary SHA-256 values are `071b5120c439f03182f2764988c92733b1afe4e50ec258533197193d2395ad02` / `bf705a22b08099ef42a9156eaf2d6ce9ed94ced49ae13b7710af1c57241b7640`; the process CPU binary values are `f8bf420026a627af00368b068f60dfae75265bb130efe4ed4befc31c48e77b34` / `b4e43781f1864cfe964ed30bccbb6271b5cad9a278117c897244671ab40052a2`. Binaries are temporary; the hashes and source below permit recreation.

## Measurements

Each receipt records six interleaved process invocations in order `base, candidate, base, candidate, candidate, base`. Each invocation executes five rounds of all three modes; tables below use the median of those five rounds for 48 independent solves. The paired ratios use invocation pairs (0,1), (2,3), and (5,4). All runs exited zero and all 48 scalar replays passed in every mode and round.

| Width | Clock | Mode | Baseline medians (ms per 48) | Candidate medians (ms per 48) | Paired baseline/candidate ratios |
|---:|---|---|---|---|---|
| 4095 | process CPU | AUTO | 8.773, 8.709, 8.648 | 0.496, 0.290, 0.271 | 17.688, 30.031, 31.911 |
| 4095 | process CPU | BRUTE | 8.937, 8.291, 8.173 | 1.332, 1.302, 1.294 | 6.709, 6.368, 6.316 |
| 4095 | process CPU | BSGS control | 0.376, 0.292, 0.294 | 0.295, 0.277, 0.271 | 1.275, 1.054, 1.085 |
| 64 | wall | AUTO | 0.265, 0.176, 0.177 | 0.146, 0.146, 0.154 | 1.815, 1.205, 1.149 |
| 64 | wall | BRUTE | 0.394, 0.176, 0.177 | 0.146, 0.152, 0.153 | 2.699, 1.158, 1.157 |

At width 4095, the solver's charged `group_ops` across the 48 targets changed from 95,205 to 5,812 for AUTO and from 95,205 to 101,492 for explicit BRUTE. The latter counter rises because every computed point in a batch and its offset setup is charged, even when the answer appears early in the block; the wall and CPU savings come from sharing expensive field inversions. The unchanged BSGS control stayed at 5,812 operations. At width 64, BRUTE/AUTO went from 2,856 to 7,632 charged operations for the same reason.

The width-4095 **wall** medians and the unchanged BSGS control varied sharply: baseline AUTO wall medians were 235.340, 27.522, and 107.269 ms, while baseline BSGS was 0.294, 0.388, and 0.643 ms. Host load averages observed during the work rose from about 137 to 578. These wall data are retained below but do not support a stable wall-speedup verdict. The process CPU paired ratios above are a scoped observation; they exclude time descheduled by the host and are not a substitute for an isolated wall comparison. Baseline AUTO A/A process CPU ratios across its three invocations were 1.007 and 1.007; candidate AUTO's first invocation was slower than its later two (0.496 versus 0.290 and 0.271 ms), and the unchanged BSGS control ratios ranged from 1.054 to 1.275. The CPU improvement is large on this fixture, but the first pair and controls prevent a low-noise headline estimate. No full performance-index score or end-to-end cryptanalysis comparison is inferred from this kernel.

The change is limited to the C single-word EC generic solver. It does not alter Rust, GPU, or index-calculus pipelines. A later isolated paired wall run with baseline A/A and the repository performance-index gate would be needed for a headline wall result. The raw receipts and runner follow verbatim.

## Reproduction probe (`probe.c`)

```c
#include "cryptanalysis/cryptanalysis.h"
#include <inttypes.h>
#include <stdio.h>
#include <time.h>

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec + 1e-9 * (double)t.tv_nsec;
}

int main(void) {
    ca_group g;
    ca_elem G, Q[48];
    uint64_t xs[48];
    const uint64_t lo = 987654, width = 4095;
    if (ca_group_ec_init(&g, 2147483659ULL, 1, 230, 2147540641ULL) != CA_OK ||
        ca_group_find_generator(&g, &G, 1) != CA_OK) return 1;
    for (unsigned i = 0; i < 48; i++) {
        xs[i] = lo + ((uint64_t)i * 997 + 111) % width;
        ca_group_mul(&g, &Q[i], &G, xs[i], NULL);
    }
    for (unsigned round = 0; round < 5; round++) {
        for (unsigned si = 0; si < 3; si++) {
            ca_solver mode = (ca_solver[]){CA_SOLVER_BRUTE, CA_SOLVER_BSGS, CA_SOLVER_AUTO}[(si + round) % 3];
            ca_dlog_params p;
            ca_dlog_params_default(&p);
            p.solver = mode;
            uint64_t ops = 0;
            double start = now();
            for (unsigned i = 0; i < 48; i++) {
                uint64_t got = UINT64_MAX;
                ca_stats st = {0};
                ca_status rc = ca_dlog_prime_order(&g, &G, &Q[i], lo, lo + width - 1, &p, &got, &st);
                if (rc != CA_OK || got != xs[i]) {
                    fprintf(stderr, "bad mode=%d i=%u status=%d got=%" PRIu64 " want=%" PRIu64 "\n", mode, i, rc, got, xs[i]);
                    return 2;
                }
                ca_elem check;
                ca_group_mul(&g, &check, &G, got, NULL);
                if (!ca_group_equal(&g, &check, &Q[i])) return 3;
                ops += st.group_ops;
            }
            double end = now();
            printf("round=%u mode=%d ms=%.3f ops=%" PRIu64 "\n", round, mode, 1000.0 * (end - start), ops);
        }
    }
    return 0;
}
```

## Raw paired wall receipt (`paired-wall.json`)

```json
{
  "platform": "macOS-26.6-arm64-arm-64bit",
  "runs": [
    {
      "width": 64,
      "revision": "base",
      "start_unix": 1792106875.1258109,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=0.394 ops=2856\nround=0 mode=1 ms=7.929 ops=1854\nround=0 mode=0 ms=0.311 ops=2856\nround=1 mode=1 ms=1.066 ops=1854\nround=1 mode=0 ms=0.936 ops=2856\nround=1 mode=5 ms=0.429 ops=2856\nround=2 mode=0 ms=0.265 ops=2856\nround=2 mode=5 ms=0.605 ops=2856\nround=2 mode=1 ms=0.191 ops=1854\nround=3 mode=5 ms=0.176 ops=2856\nround=3 mode=1 ms=0.804 ops=1854\nround=3 mode=0 ms=0.177 ops=2856\nround=4 mode=1 ms=0.188 ops=1854\nround=4 mode=0 ms=0.177 ops=2856\nround=4 mode=5 ms=0.176 ops=2856\n",
      "stderr": ""
    },
    {
      "width": 64,
      "revision": "cand",
      "start_unix": 1792106875.3584058,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=0.146 ops=7632\nround=0 mode=1 ms=0.187 ops=1854\nround=0 mode=0 ms=0.146 ops=7632\nround=1 mode=1 ms=0.182 ops=1854\nround=1 mode=0 ms=0.147 ops=7632\nround=1 mode=5 ms=0.254 ops=7632\nround=2 mode=0 ms=0.144 ops=7632\nround=2 mode=5 ms=0.144 ops=7632\nround=2 mode=1 ms=0.185 ops=1854\nround=3 mode=5 ms=0.147 ops=7632\nround=3 mode=1 ms=0.183 ops=1854\nround=3 mode=0 ms=0.146 ops=7632\nround=4 mode=1 ms=0.258 ops=1854\nround=4 mode=0 ms=0.146 ops=7632\nround=4 mode=5 ms=0.144 ops=7632\n",
      "stderr": ""
    },
    {
      "width": 64,
      "revision": "base",
      "start_unix": 1792106875.366234,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=0.178 ops=2856\nround=0 mode=1 ms=0.188 ops=1854\nround=0 mode=0 ms=0.176 ops=2856\nround=1 mode=1 ms=0.183 ops=1854\nround=1 mode=0 ms=0.226 ops=2856\nround=1 mode=5 ms=0.176 ops=2856\nround=2 mode=0 ms=0.176 ops=2856\nround=2 mode=5 ms=0.176 ops=2856\nround=2 mode=1 ms=0.185 ops=1854\nround=3 mode=5 ms=0.176 ops=2856\nround=3 mode=1 ms=0.181 ops=1854\nround=3 mode=0 ms=0.176 ops=2856\nround=4 mode=1 ms=0.182 ops=1854\nround=4 mode=0 ms=0.176 ops=2856\nround=4 mode=5 ms=0.176 ops=2856\n",
      "stderr": ""
    },
    {
      "width": 64,
      "revision": "cand",
      "start_unix": 1792106875.3751822,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=0.152 ops=7632\nround=0 mode=1 ms=0.188 ops=1854\nround=0 mode=0 ms=0.146 ops=7632\nround=1 mode=1 ms=0.182 ops=1854\nround=1 mode=0 ms=0.146 ops=7632\nround=1 mode=5 ms=0.146 ops=7632\nround=2 mode=0 ms=0.146 ops=7632\nround=2 mode=5 ms=0.147 ops=7632\nround=2 mode=1 ms=0.219 ops=1854\nround=3 mode=5 ms=0.154 ops=7632\nround=3 mode=1 ms=0.187 ops=1854\nround=3 mode=0 ms=0.154 ops=7632\nround=4 mode=1 ms=0.186 ops=1854\nround=4 mode=0 ms=0.153 ops=7632\nround=4 mode=5 ms=0.153 ops=7632\n",
      "stderr": ""
    },
    {
      "width": 64,
      "revision": "cand",
      "start_unix": 1792106875.3844202,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=0.263 ops=7632\nround=0 mode=1 ms=0.248 ops=1854\nround=0 mode=0 ms=0.154 ops=7632\nround=1 mode=1 ms=0.187 ops=1854\nround=1 mode=0 ms=0.154 ops=7632\nround=1 mode=5 ms=0.153 ops=7632\nround=2 mode=0 ms=0.153 ops=7632\nround=2 mode=5 ms=0.153 ops=7632\nround=2 mode=1 ms=0.186 ops=1854\nround=3 mode=5 ms=0.153 ops=7632\nround=3 mode=1 ms=0.185 ops=1854\nround=3 mode=0 ms=0.154 ops=7632\nround=4 mode=1 ms=0.307 ops=1854\nround=4 mode=0 ms=0.145 ops=7632\nround=4 mode=5 ms=0.145 ops=7632\n",
      "stderr": ""
    },
    {
      "width": 64,
      "revision": "base",
      "start_unix": 1792106875.3944378,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=0.178 ops=2856\nround=0 mode=1 ms=0.189 ops=1854\nround=0 mode=0 ms=0.176 ops=2856\nround=1 mode=1 ms=0.182 ops=1854\nround=1 mode=0 ms=0.176 ops=2856\nround=1 mode=5 ms=0.176 ops=2856\nround=2 mode=0 ms=0.177 ops=2856\nround=2 mode=5 ms=0.176 ops=2856\nround=2 mode=1 ms=0.181 ops=1854\nround=3 mode=5 ms=0.484 ops=2856\nround=3 mode=1 ms=0.187 ops=1854\nround=3 mode=0 ms=0.183 ops=2856\nround=4 mode=1 ms=0.182 ops=1854\nround=4 mode=0 ms=0.259 ops=2856\nround=4 mode=5 ms=0.177 ops=2856\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "base",
      "start_unix": 1792106877.3739488,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=8.339 ops=95205\nround=0 mode=1 ms=0.293 ops=5812\nround=0 mode=0 ms=213.489 ops=95205\nround=1 mode=1 ms=1.077 ops=5812\nround=1 mode=0 ms=31.794 ops=95205\nround=1 mode=5 ms=293.337 ops=95205\nround=2 mode=0 ms=277.238 ops=95205\nround=2 mode=5 ms=70.436 ops=95205\nround=2 mode=1 ms=0.294 ops=5812\nround=3 mode=5 ms=74.449 ops=95205\nround=3 mode=1 ms=1.095 ops=5812\nround=3 mode=0 ms=409.017 ops=95205\nround=4 mode=1 ms=0.290 ops=5812\nround=4 mode=0 ms=235.340 ops=95205\nround=4 mode=5 ms=349.500 ops=95205\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "cand",
      "start_unix": 1792106877.804323,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=1.386 ops=101492\nround=0 mode=1 ms=0.293 ops=5812\nround=0 mode=0 ms=0.276 ops=5812\nround=1 mode=1 ms=0.271 ops=5812\nround=1 mode=0 ms=0.270 ops=5812\nround=1 mode=5 ms=1.375 ops=101492\nround=2 mode=0 ms=0.271 ops=5812\nround=2 mode=5 ms=1.295 ops=101492\nround=2 mode=1 ms=0.270 ops=5812\nround=3 mode=5 ms=1.294 ops=101492\nround=3 mode=1 ms=0.270 ops=5812\nround=3 mode=0 ms=0.269 ops=5812\nround=4 mode=1 ms=0.270 ops=5812\nround=4 mode=0 ms=0.269 ops=5812\nround=4 mode=5 ms=194.905 ops=101492\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "base",
      "start_unix": 1792106879.852405,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=16.431 ops=95205\nround=0 mode=1 ms=0.681 ops=5812\nround=0 mode=0 ms=15.350 ops=95205\nround=1 mode=1 ms=278.899 ops=5812\nround=1 mode=0 ms=12.226 ops=95205\nround=1 mode=5 ms=412.200 ops=95205\nround=2 mode=0 ms=188.920 ops=95205\nround=2 mode=5 ms=371.610 ops=95205\nround=2 mode=1 ms=0.388 ops=5812\nround=3 mode=5 ms=362.722 ops=95205\nround=3 mode=1 ms=0.289 ops=5812\nround=3 mode=0 ms=27.522 ops=95205\nround=4 mode=1 ms=0.297 ops=5812\nround=4 mode=0 ms=299.199 ops=95205\nround=4 mode=5 ms=9.739 ops=95205\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "cand",
      "start_unix": 1792106879.885447,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=1.259 ops=101492\nround=0 mode=1 ms=0.292 ops=5812\nround=0 mode=0 ms=0.275 ops=5812\nround=1 mode=1 ms=0.294 ops=5812\nround=1 mode=0 ms=0.439 ops=5812\nround=1 mode=5 ms=1.411 ops=101492\nround=2 mode=0 ms=0.272 ops=5812\nround=2 mode=5 ms=1.257 ops=101492\nround=2 mode=1 ms=0.270 ops=5812\nround=3 mode=5 ms=1.295 ops=101492\nround=3 mode=1 ms=0.269 ops=5812\nround=3 mode=0 ms=0.270 ops=5812\nround=4 mode=1 ms=0.270 ops=5812\nround=4 mode=0 ms=0.269 ops=5812\nround=4 mode=5 ms=1.294 ops=101492\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "cand",
      "start_unix": 1792106879.8997781,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=1.261 ops=101492\nround=0 mode=1 ms=0.292 ops=5812\nround=0 mode=0 ms=0.275 ops=5812\nround=1 mode=1 ms=0.271 ops=5812\nround=1 mode=0 ms=0.269 ops=5812\nround=1 mode=5 ms=1.294 ops=101492\nround=2 mode=0 ms=0.270 ops=5812\nround=2 mode=5 ms=1.294 ops=101492\nround=2 mode=1 ms=0.270 ops=5812\nround=3 mode=5 ms=1.294 ops=101492\nround=3 mode=1 ms=0.270 ops=5812\nround=3 mode=0 ms=0.269 ops=5812\nround=4 mode=1 ms=0.269 ops=5812\nround=4 mode=0 ms=0.269 ops=5812\nround=4 mode=5 ms=1.282 ops=101492\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "base",
      "start_unix": 1792106882.672689,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=8.425 ops=95205\nround=0 mode=1 ms=0.292 ops=5812\nround=0 mode=0 ms=107.269 ops=95205\nround=1 mode=1 ms=0.296 ops=5812\nround=1 mode=0 ms=461.970 ops=95205\nround=1 mode=5 ms=245.671 ops=95205\nround=2 mode=0 ms=7.665 ops=95205\nround=2 mode=5 ms=560.100 ops=95205\nround=2 mode=1 ms=0.643 ops=5812\nround=3 mode=5 ms=370.123 ops=95205\nround=3 mode=1 ms=1.425 ops=5812\nround=3 mode=0 ms=349.010 ops=95205\nround=4 mode=1 ms=4.556 ops=5812\nround=4 mode=0 ms=74.105 ops=95205\nround=4 mode=5 ms=539.593 ops=95205\n",
      "stderr": ""
    }
  ]
}
```

## Raw paired process CPU receipt (`paired-cpu.json`)

```json
{
  "platform": "macOS-26.6-arm64-arm-64bit",
  "runs": [
    {
      "width": 4095,
      "revision": "base",
      "start_unix": 1792106884.967617,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=9.481 ops=95205\nround=0 mode=1 ms=0.376 ops=5812\nround=0 mode=0 ms=8.186 ops=95205\nround=1 mode=1 ms=0.290 ops=5812\nround=1 mode=0 ms=8.294 ops=95205\nround=1 mode=5 ms=9.613 ops=95205\nround=2 mode=0 ms=8.843 ops=95205\nround=2 mode=5 ms=8.846 ops=95205\nround=2 mode=1 ms=0.679 ops=5812\nround=3 mode=5 ms=8.069 ops=95205\nround=3 mode=1 ms=0.289 ops=5812\nround=3 mode=0 ms=8.808 ops=95205\nround=4 mode=1 ms=0.542 ops=5812\nround=4 mode=0 ms=8.773 ops=95205\nround=4 mode=5 ms=8.937 ops=95205\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "cand",
      "start_unix": 1792106885.369577,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=1.878 ops=101492\nround=0 mode=1 ms=0.297 ops=5812\nround=0 mode=0 ms=0.279 ops=5812\nround=1 mode=1 ms=0.295 ops=5812\nround=1 mode=0 ms=0.295 ops=5812\nround=1 mode=5 ms=1.332 ops=101492\nround=2 mode=0 ms=0.556 ops=5812\nround=2 mode=5 ms=1.723 ops=101492\nround=2 mode=1 ms=0.291 ops=5812\nround=3 mode=5 ms=1.268 ops=101492\nround=3 mode=1 ms=0.272 ops=5812\nround=3 mode=0 ms=0.622 ops=5812\nround=4 mode=1 ms=0.585 ops=5812\nround=4 mode=0 ms=0.496 ops=5812\nround=4 mode=5 ms=1.261 ops=101492\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "base",
      "start_unix": 1792106887.215851,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=8.314 ops=95205\nround=0 mode=1 ms=0.292 ops=5812\nround=0 mode=0 ms=9.357 ops=95205\nround=1 mode=1 ms=0.306 ops=5812\nround=1 mode=0 ms=7.711 ops=95205\nround=1 mode=5 ms=8.291 ops=95205\nround=2 mode=0 ms=9.277 ops=95205\nround=2 mode=5 ms=8.504 ops=95205\nround=2 mode=1 ms=0.294 ops=5812\nround=3 mode=5 ms=7.987 ops=95205\nround=3 mode=1 ms=0.292 ops=5812\nround=3 mode=0 ms=7.810 ops=95205\nround=4 mode=1 ms=0.289 ops=5812\nround=4 mode=0 ms=8.709 ops=95205\nround=4 mode=5 ms=8.078 ops=95205\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "cand",
      "start_unix": 1792106887.264271,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=1.433 ops=101492\nround=0 mode=1 ms=0.301 ops=5812\nround=0 mode=0 ms=0.357 ops=5812\nround=1 mode=1 ms=0.740 ops=5812\nround=1 mode=0 ms=0.291 ops=5812\nround=1 mode=5 ms=1.319 ops=101492\nround=2 mode=0 ms=0.290 ops=5812\nround=2 mode=5 ms=1.286 ops=101492\nround=2 mode=1 ms=0.277 ops=5812\nround=3 mode=5 ms=1.294 ops=101492\nround=3 mode=1 ms=0.272 ops=5812\nround=3 mode=0 ms=0.270 ops=5812\nround=4 mode=1 ms=0.272 ops=5812\nround=4 mode=0 ms=0.270 ops=5812\nround=4 mode=5 ms=1.302 ops=101492\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "cand",
      "start_unix": 1792106887.285028,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=2.023 ops=101492\nround=0 mode=1 ms=0.294 ops=5812\nround=0 mode=0 ms=0.277 ops=5812\nround=1 mode=1 ms=0.271 ops=5812\nround=1 mode=0 ms=0.271 ops=5812\nround=1 mode=5 ms=1.294 ops=101492\nround=2 mode=0 ms=0.271 ops=5812\nround=2 mode=5 ms=1.294 ops=101492\nround=2 mode=1 ms=0.270 ops=5812\nround=3 mode=5 ms=1.259 ops=101492\nround=3 mode=1 ms=0.273 ops=5812\nround=3 mode=0 ms=0.269 ops=5812\nround=4 mode=1 ms=0.269 ops=5812\nround=4 mode=0 ms=0.269 ops=5812\nround=4 mode=5 ms=1.259 ops=101492\n",
      "stderr": ""
    },
    {
      "width": 4095,
      "revision": "base",
      "start_unix": 1792106889.698997,
      "exit_code": 0,
      "stdout": "round=0 mode=5 ms=8.574 ops=95205\nround=0 mode=1 ms=0.294 ops=5812\nround=0 mode=0 ms=8.647 ops=95205\nround=1 mode=1 ms=0.528 ops=5812\nround=1 mode=0 ms=9.067 ops=95205\nround=1 mode=5 ms=7.692 ops=95205\nround=2 mode=0 ms=7.667 ops=95205\nround=2 mode=5 ms=7.718 ops=95205\nround=2 mode=1 ms=0.620 ops=5812\nround=3 mode=5 ms=9.717 ops=95205\nround=3 mode=1 ms=0.289 ops=5812\nround=3 mode=0 ms=8.648 ops=95205\nround=4 mode=1 ms=0.289 ops=5812\nround=4 mode=0 ms=8.693 ops=95205\nround=4 mode=5 ms=8.173 ops=95205\n",
      "stderr": ""
    }
  ]
}
```
