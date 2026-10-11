/*
 * fuzz_coord.c - libFuzzer harness for the distributed-rho wire format
 * and the merge that trusts it.
 *
 * The parsers in coord.c are the library's only attack surface that
 * faces the network: a hub on a public address feeds every line it
 * receives to ca_coord_checkin_decode, and an agent feeds it every line
 * the hub pushes back.  So the input here is *text*, taken verbatim
 * from the fuzzer, and the contracts asserted are:
 *
 *   safety:    neither decoder may read out of bounds or leave a
 *              partially-filled record behind -- a rejected line must
 *              leave nothing usable, which is checked by requiring the
 *              counts of a failed decode to stay within their arrays.
 *   agreement: whatever ca_coord_checkin_decode accepts must re-encode
 *              and re-decode to the same record (the log stores lines,
 *              so a line that means two different things on two hosts
 *              would split the CRDT).
 *   soundness: a decoded check-in fed to ca_coord_apply with
 *              verification on can never produce a solution that fails
 *              x*G == H, however the bytes were chosen.  This is the
 *              property that lets a hub accept records from strangers.
 *
 * The group is small and fixed so one input costs microseconds; what is
 * fuzzed is the text, not the arithmetic (fuzz_dlog covers that).
 */
#include "cryptanalysis/ca_coord.h"
#include "cryptanalysis/cryptanalysis.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static ca_coord_ctx *g_ctx;
static ca_group g_group;
static ca_elem g_base, g_target;

static void fuzz_setup(void)
{
    if (g_ctx) return;
    /* p = 2q+1 with q = 1000151: a real prime-order subgroup, so the
     * verification path is the same one a deployment runs. */
    if (ca_group_zp_init(&g_group, 2000303ULL, 1000151ULL) != CA_OK) abort();
    if (ca_group_find_generator(&g_group, &g_base, 1) != CA_OK) abort();
    ca_group_mul(&g_group, &g_target, &g_base, 123456, NULL);
    ca_coord_job job;
    if (ca_coord_job_init(&job, &g_group, &g_base, &g_target, 5, 16, 0, 32, 7) != CA_OK) abort();
    if (ca_coord_ctx_open(&g_ctx, &job) != CA_OK) abort();
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    if (size > CA_COORD_LINE_MAX + 64) return 0;
    fuzz_setup();

    /* The input, as a NUL-terminated line: exactly what arrives on a
     * socket, embedded NULs and all (they end the line, as they would). */
    char *line = malloc(size + 1);
    if (!line) return 0;
    memcpy(line, data, size);
    line[size] = 0;

    /* 1. The job decoder, which an agent runs on whatever /v1/job
     *    returned before it has any reason to trust it. */
    ca_coord_job job;
    if (ca_coord_job_decode(&job, line) == CA_OK) {
        /* Accepting means the id checked out, so re-encoding is stable. */
        char re[CA_COORD_LINE_MAX];
        if (ca_coord_job_encode(&job, re, sizeof(re))) {
            ca_coord_job again;
            if (ca_coord_job_decode(&again, re) != CA_OK) abort();
            if (again.id != job.id) abort();
        }
    }

    /* 2. The check-in decoder. */
    ca_coord_checkin ci;
    if (ca_coord_checkin_decode(&ci, line) == CA_OK) {
        if (ci.num_units > CA_COORD_UNITS_MAX || ci.num_dps > CA_COORD_DPS_MAX) abort();

        char re[CA_COORD_LINE_MAX];
        size_t n = ca_coord_checkin_encode(&ci, re, sizeof(re));
        if (n) {
            ca_coord_checkin again;
            if (ca_coord_checkin_decode(&again, re) != CA_OK) abort();
            if (again.seq != ci.seq || again.num_dps != ci.num_dps ||
                again.num_units != ci.num_units || strcmp(again.peer, ci.peer) != 0)
                abort();
            char re2[CA_COORD_LINE_MAX];
            if (ca_coord_checkin_encode(&again, re2, sizeof(re2)) != n) abort();
            if (memcmp(re, re2, n) != 0) abort();
        }

        /* 3. The merge, with verification on, as a hub runs it. */
        ca_coord_state *st = NULL;
        if (ca_coord_state_init(&st, g_ctx) == CA_OK) {
            ci.job_id = ca_coord_ctx_job(g_ctx)->id; /* past the job check */
            ca_coord_outcome oc;
            ca_coord_apply(st, g_ctx, &ci, 1000, 1, &oc);
            uint64_t x = 0;
            if (ca_coord_solution(st, &x)) {
                /* Whatever the bytes said, an accepted solution is the
                 * discrete logarithm. */
                ca_elem check;
                ca_group_mul(&g_group, &check, &g_base, x, NULL);
                if (!ca_group_equal(&g_group, &check, &g_target)) abort();
            }
            ca_coord_state_free(st);
        }
    }

    free(line);
    return 0;
}
