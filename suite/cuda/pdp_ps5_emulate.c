/*
 * pdp_ps5_emulate.c - run the PS-5 kernel's source on the host.
 *
 * pdp_ps5_device.cuh is compiled as C, with the generated program, and
 * `lop3` replaced by a bitwise model of the instruction with the same
 * immediate.  A job is one device thread's work and jobs do not interact
 * (no shared memory, no barrier, one atomic counter), so the emulation of a
 * grid is a loop over jobs: this is the device kernel's arithmetic, not a
 * model of it.  What it does not model: the instruction schedule, registers,
 * memory system and atomics' ordering (the hit list's order differs on a
 * device; hosts sort it).
 *
 * Built with -DPS5_PARAMS_H='"<prefix>.h"' -I<dir of the generated files>.
 */
#include "pdp_ps5_device.cuh"

/* Jobs [first, first + count) with a private counter and record list.
 * Returns 0. */
int pdp_ps5_emulate(const ps5_u32 *jobs, ps5_u32 first, ps5_u32 count, const ps5_u32 *xb,
                    const ps5_u32 *yb, const ps5_u64 *rows, ps5_u32 m, ps5_u32 nblk,
                    ps5_u32 *nhits, Ps5Hit *hits, ps5_u32 cap)
{
    for (ps5_u32 job = first; job < first + count; ++job)
        ps5_job(job, jobs, xb, yb, rows, m, nblk, nhits, hits, cap);
    return 0;
}

/* What the program is, for the host driver to check against its own build. */
void pdp_ps5_info(ps5_u32 out[8], const char **sha256)
{
    out[0] = PS5_N;
    out[1] = PS5_L;
    out[2] = PS5_TASKS;
    out[3] = PS5_OPS;
    out[4] = PS5_GATES_FUSED;
    out[5] = PS5_GATES_UNFUSED;
    out[6] = PS5_INPUTS;
    out[7] = PS5_OUTPUTS;
    *sha256 = PS5_PROGRAM_SHA256;
}
