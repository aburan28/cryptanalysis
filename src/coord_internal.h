/*
 * coord_internal.h - shared between coord.c (job, state, walk, wire)
 * and coord_net.c (sockets).  Not installed.
 */
#ifndef CA_COORD_INTERNAL_H
#define CA_COORD_INTERNAL_H

#include "cryptanalysis/ca_coord.h"
#include "ca_internal.h"

#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

/* Everything derivable from the job, derived once. */
struct ca_coord_ctx {
    ca_coord_job job;
    ca_group g;
    ca_elem base, target;
    uint64_t n;
    uint32_t r;
    uint64_t dp_mask;
    ca_elem *M; /* branch table, r entries */
    uint64_t *alpha, *beta;
};

/* A walk in flight: y = a*G + b*H is the invariant every step keeps. */
typedef struct coord_walk {
    ca_elem y;
    uint64_t a, b;
} coord_walk;

/* One distinguished point in the shared table. */
typedef struct coord_dp_entry {
    int32_t used;
    uint64_t key; /* ca_group_hash of the canonical point */
    uint64_t point[4];
    uint64_t a, b;
    uint64_t walker;
    uint32_t peer; /* index into the peer table */
} coord_dp_entry;

/* A peer we have heard from, and how far. */
typedef struct coord_peer {
    char name[CA_COORD_PEER_MAX];
    uint64_t max_seq;
} coord_peer;

/* One peer's cumulative report on one unit. */
typedef struct coord_unit_view {
    uint64_t unit;
    uint32_t peer;
    uint64_t seq; /* the report's check-in seq; later wins */
    uint64_t walkers_done, steps, dps, dead_trails;
    int32_t completed;
    uint64_t seen_local; /* local receipt time -- leases use this, not the
                          * sender's clock, so skew cannot orphan a unit */
} coord_unit_view;

/*
 * The log is kept in its wire form.  One encoded line is exactly what a
 * delta has to send, it is what a mailbox would write, and it costs what
 * the check-in actually is rather than the maximum a check-in could be.
 */
typedef struct coord_log_entry {
    uint32_t peer;
    uint64_t seq;
    char *line;
} coord_log_entry;

/*
 * Open-addressed indices kept *beside* the log and the unit table, so a
 * check-in's dedup and unit lookups are O(1) rather than a linear scan of
 * everything ever seen.  They hold no data the arrays do not; losing them
 * would only make ingest quadratic again.  Both use power-of-two caps and
 * are grown when three quarters full.
 */
typedef struct coord_seen_slot {
    int32_t used;
    uint32_t peer;
    uint64_t seq;
} coord_seen_slot;

typedef struct coord_unit_index_slot {
    int32_t used;
    uint32_t peer;
    uint64_t unit;
    size_t idx; /* index into ca_coord_state.units */
} coord_unit_index_slot;

/* The in-process backend: the open-addressed table this library has always
 * used, now reachable through ca_coord_dp_store like any other. */
typedef struct coord_mem_store {
    coord_dp_entry *dp;
    size_t dp_cap, dp_count;
} coord_mem_store;

struct ca_coord_state {
    pthread_mutex_t lock;
    uint64_t job_id;

    /* Where points are remembered.  `mem` is the default backend and is
     * only touched through `store`; a state built with another backend
     * leaves it empty. */
    ca_coord_dp_store store;
    coord_mem_store mem;

    coord_peer *peers;
    size_t peer_cap, peer_count;

    coord_unit_view *units;
    size_t unit_cap, unit_count;

    coord_log_entry *log;
    size_t log_cap, log_count;

    /* O(1) dedup index beside the log: presence of (peer, seq). */
    coord_seen_slot *seen;
    size_t seen_cap, seen_count;
    /* O(1) index beside units: (unit, peer) -> index into units[]. */
    coord_unit_index_slot *unit_index;
    size_t unit_index_cap, unit_index_count;

    uint64_t steps, dps_total, dead_trails;
    uint64_t rejected_dps, rejected_checkins, sterile_collisions;

    int32_t have_solution;
    uint64_t solution;
};

struct ca_coord_vv {
    coord_peer *e;
    size_t cap, count;
};

/* walk helpers, shared with the tests through the public header */
int ca_coord_is_dp(const ca_coord_ctx *ctx, const ca_elem *y);
int ca_coord_walk_one(const ca_coord_ctx *ctx, uint64_t index, uint64_t cap, ca_coord_dp *out,
                      uint64_t *steps_out);
int ca_coord_dp_verify(const ca_coord_ctx *ctx, const ca_coord_dp *dp, ca_elem *out);
int ca_coord_solve_collision(const ca_coord_ctx *ctx, uint64_t a1, uint64_t b1, uint64_t a2,
                             uint64_t b2, uint64_t *x);

/* Pick the next unit for `peer` and record the claim.  Returns the unit
 * and the walker cursor to resume from. */
uint64_t ca_coord_claim_unit(ca_coord_state *st, const ca_coord_ctx *ctx, const char *peer,
                             uint64_t now, uint64_t lease_secs, uint32_t claim_window,
                             uint64_t *resume_from);

/* Next sequence number for `peer` (above anything already logged). */
uint64_t ca_coord_next_seq(ca_coord_state *st, const char *peer);

/* Parse "host:port[/prefix]" out of a URL.  Returns CA_OK and fills the
 * two buffers, or CA_ERR_INVALID with ca_set_error explaining. */
ca_status ca_coord_parse_url(const char *url, char *host_port, size_t hp_cap, char *prefix,
                             size_t pfx_cap);

#endif /* CA_COORD_INTERNAL_H */
