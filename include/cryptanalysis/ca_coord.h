/*
 * ca_coord.h - distributed Pollard rho: a coordinator with a URL, and
 * agents that dial out to it.
 *
 * `ca_rho_solve` divides one instance across the threads of one process.
 * This header divides it across machines that cannot reach each other.
 * The arrangement it is built for is the one a cloud deployment actually
 * has: the workers sit in private subnets, behind NAT, on spot instances
 * and in containers with no inbound rule, while exactly one host -- an
 * EC2 instance, or a load balancer in front of one -- is reachable by
 * all of them.
 *
 *     agent (private subnet)  ----+
 *     agent (spot fleet)      ----+--->  http://coordinator:8080
 *     agent (laptop, NAT)     ----+          GET /v1/channel
 *                                            Upgrade: ca-rho/1
 *                                       <--- the hub pushes back down
 *                                            the socket the agent opened
 *
 * Every connection is opened by the agent.  Once one is up the hub uses
 * that same socket in the other direction -- the *reverse channel* -- to
 * push other agents' distinguished points and the solution to a machine
 * it could never have dialled.  Nothing polls.
 *
 * What is shared is van Oorschot-Wiener's observation that parallel rho
 * divides by *start point*, not by search space: every agent walks the
 * same function (the branch table is derived from the job id, so
 * everyone derives the same one) and reports only distinguished points,
 * so a collision between any two agents' trails solves the instance
 * exactly as a collision on one machine would.  What is partitioned is
 * the walker index space: walker i starts at a_i*G + b_i*H with
 * (a_i, b_i) derived from the job id, and a *work unit* is a contiguous
 * range of i.  Agents claim units themselves under a lease; nobody hands
 * work out.
 *
 * Every fact on the wire is verifiable from the job alone: a check-in
 * carries (walker, steps, point, a, b) with a*G + b*H == point, which
 * costs the receiver two scalar multiplications to check against the
 * 2^dp_bits steps it stands for.  So the hub is a rendezvous, not an
 * authority, and a participant who lies can only waste their own time.
 *
 * Threading: a ca_coord_state is guarded by its own lock and may be
 * shared by any number of lanes, hubs and agents in one process.  A
 * ca_coord_ctx is immutable after ca_coord_ctx_open and may be shared
 * freely.
 *
 * Portability: the networking here is POSIX (sockets, pthreads).  The
 * job, state, walk and wire format are plain C11 and build anywhere.
 */
#ifndef CA_COORD_H
#define CA_COORD_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Longest peer name, including the terminator.  A peer name is one
 * lane's id ("<node>.<lane>") and must be printable ASCII without space,
 * ';', ',' or '|' -- the wire format's separators. */
#define CA_COORD_PEER_MAX 64
/* Distinguished points carried by one check-in. */
#define CA_COORD_DPS_MAX 64
/* Unit reports carried by one check-in. */
#define CA_COORD_UNITS_MAX 8
/* Longest wire line, including the terminator. */
#define CA_COORD_LINE_MAX 8192
/* The protocol token in the channel's Upgrade: header. */
#define CA_COORD_PROTOCOL "ca-rho/1"
/* Environment variables the CLI falls back to. */
#define CA_COORD_URL_ENV   "CA_COORDINATOR_URL"
#define CA_COORD_TOKEN_ENV "CA_COORDINATOR_TOKEN"

/* ---- the job ----------------------------------------------------------- */

/*
 * The document every participant shares.  Its canonical encoding
 * (ca_coord_job_encode) is hashed into the job id, so two agents agree
 * on the walk exactly when they agree on every field here.
 *
 * The id is 64 bits.  That is an agreement check, not a security
 * boundary: a wrong id is refused, and a right one still buys nothing,
 * because every record under it is verified against the group.
 */
typedef struct ca_coord_job {
    ca_group_kind kind;   /* CA_GROUP_ZP or CA_GROUP_EC */
    uint64_t p;           /* field characteristic / modulus */
    uint64_t a, b;        /* curve coefficients (EC only) */
    uint64_t order;       /* n: order of the subgroup worked in */
    uint64_t base[4];     /* G, in ca_group_decode() words */
    uint64_t target[4];   /* H, likewise */
    int32_t dp_bits;      /* trailing zero bits of the DP hash */
    uint32_t r;           /* adding-walk multipliers */
    int32_t negation_map; /* 1 to walk on {Y, -Y} classes */
    uint64_t unit_size;   /* walkers per work unit */
    uint64_t seed;        /* mixed into every derivation */
    uint64_t id;          /* derived; set by init/decode, not by you */
} ca_coord_job;

/* Fill `job` for this group and instance.  dp_bits < 0 selects the
 * library default (a quarter of log2 n, clamped); r == 0 selects 32;
 * unit_size == 0 selects 256.  Fails if the group has no order, if the
 * negation map is asked for in a group that has none, or if base or
 * target is not a valid element. */
CA_API ca_status ca_coord_job_init(ca_coord_job *job, const ca_group *g, const ca_elem *base,
                                   const ca_elem *target, int32_t dp_bits, uint32_t r,
                                   int negation_map, uint64_t unit_size, uint64_t seed);

/* Write the canonical one-line encoding (the id's preimage, and what
 * GET /v1/job serves).  Returns the length written, or 0 if cap is too
 * small.  Always NUL-terminates when it returns non-zero. */
CA_API size_t ca_coord_job_encode(const ca_coord_job *job, char *buf, size_t cap);

/* Parse one canonical line.  Recomputes and checks the id, so a
 * truncated or edited document is refused rather than silently walked. */
CA_API ca_status ca_coord_job_decode(ca_coord_job *job, const char *line);

/* Rebuild the group the job describes. */
CA_API ca_status ca_coord_job_group(const ca_coord_job *job, ca_group *g);

/* ---- the derived context ----------------------------------------------- */

/*
 * Everything derivable from the job: the group, the branch table, the DP
 * mask.  Deriving is deterministic, so two agents that agree on the job
 * id agree on all of it without exchanging any of it.
 */
typedef struct ca_coord_ctx ca_coord_ctx;

CA_API ca_status ca_coord_ctx_open(ca_coord_ctx **out, const ca_coord_job *job);
CA_API void ca_coord_ctx_close(ca_coord_ctx *ctx);
CA_API const ca_coord_job *ca_coord_ctx_job(const ca_coord_ctx *ctx);
CA_API const ca_group *ca_coord_ctx_group(const ca_coord_ctx *ctx);
/* Start point of walker i: R = a*G + b*H with (a, b) derived from the id. */
CA_API void ca_coord_walker_start(const ca_coord_ctx *ctx, uint64_t walker, ca_elem *out,
                                  uint64_t *a, uint64_t *b);
/* Expected total steps, sqrt(pi n / 2) (over sqrt 2 with the negation map). */
CA_API double ca_coord_expected_steps(const ca_coord_ctx *ctx);
/* Expected distinguished points at the solve. */
CA_API double ca_coord_expected_dps(const ca_coord_ctx *ctx);

/* ---- records ----------------------------------------------------------- */

/* One distinguished point, self-certifying: a*G + b*H == point. */
typedef struct ca_coord_dp {
    uint64_t walker;   /* which walker's trail reached it */
    uint64_t steps;    /* steps taken to get there */
    uint64_t point[4]; /* the point, in ca_group_decode() words */
    uint64_t a, b;     /* its coefficients mod n */
} ca_coord_dp;

/* Cumulative progress on one work unit by one peer. */
typedef struct ca_coord_unit {
    uint64_t unit;
    uint64_t walkers_done; /* cursor: walkers finished in this unit */
    uint64_t steps;
    uint64_t dps;
    uint64_t dead_trails; /* walkers that hit the step cap */
    int32_t completed;
} ca_coord_unit;

/* The only message in the protocol. */
typedef struct ca_coord_checkin {
    uint64_t job_id; /* the job this is about; a foreign one is refused */
    char peer[CA_COORD_PEER_MAX];
    uint64_t seq;  /* per peer, strictly increasing */
    uint64_t time; /* the sender's unix clock, advisory only */
    uint32_t num_units;
    uint32_t num_dps;
    ca_coord_unit units[CA_COORD_UNITS_MAX];
    ca_coord_dp dps[CA_COORD_DPS_MAX];
    int32_t has_solution;
    uint64_t solution;
} ca_coord_checkin;

/* ---- the shared state (a CRDT) ----------------------------------------- */

/*
 * The merge of every check-in seen.  Each component is conflict-free --
 * a grow-only DP table (a repeat key with different coefficients *is*
 * the collision), a per-peer max-register for unit progress, a
 * write-once verified solution, and the log keyed by (peer, seq) -- so
 * merging is commutative, associative and idempotent and peers converge
 * whatever order anything arrives in, however often.
 */
typedef struct ca_coord_state ca_coord_state;

/* What applying one check-in did. */
typedef struct ca_coord_outcome {
    int32_t fresh; /* 1 if this (peer, seq) was new */
    uint32_t accepted_dps;
    uint32_t rejected_dps; /* failed verification; the sender is lying or broken */
    int32_t solved_now;
} ca_coord_outcome;

/* Aggregate view, for a status line or GET /v1/status. */
typedef struct ca_coord_progress {
    uint64_t steps;
    uint64_t dps_stored;
    uint64_t dead_trails;
    uint64_t units_completed;
    uint64_t units_active; /* claimed with a live lease */
    uint64_t peers;
    uint64_t checkins;
    uint64_t rejected_dps;
    uint64_t sterile_collisions;
    double expected_steps;
    double fraction; /* steps / expected_steps */
    int32_t have_solution;
    uint64_t solution;
} ca_coord_progress;

CA_API ca_status ca_coord_state_init(ca_coord_state **out, const ca_coord_ctx *ctx);
CA_API void ca_coord_state_free(ca_coord_state *st);

/*
 * Merge one check-in.  With verify != 0 every distinguished point is
 * checked (valid element, actually distinguished, and a*G + b*H equal to
 * it) and a failing one is dropped and counted; pass 0 only for records
 * this process just produced.  `now` is the local clock in seconds --
 * leases are judged by local receipt, so a peer's skewed clock cannot
 * orphan a unit.  A check-in for another job, or one claiming an
 * unverifiable solution, is refused with CA_ERR_INVALID.
 */
CA_API ca_status ca_coord_apply(ca_coord_state *st, const ca_coord_ctx *ctx,
                                const ca_coord_checkin *ci, uint64_t now, int verify,
                                ca_coord_outcome *out);

CA_API void ca_coord_progress_get(ca_coord_state *st, const ca_coord_ctx *ctx, uint64_t now,
                                  uint64_t lease_secs, ca_coord_progress *out);

/* The solution, once some merge produced and verified it. */
CA_API int ca_coord_solution(ca_coord_state *st, uint64_t *x);

/*
 * Version vectors and deltas -- what makes any transport converge in one
 * round trip.  A vector is the peer -> max seq map; the delta for a
 * vector is exactly the check-ins its holder lacks.
 */
typedef struct ca_coord_vv ca_coord_vv;
CA_API ca_status ca_coord_vv_new(ca_coord_vv **out);
CA_API void ca_coord_vv_free(ca_coord_vv *vv);
CA_API void ca_coord_vv_set(ca_coord_vv *vv, const char *peer, uint64_t seq);
CA_API uint64_t ca_coord_vv_get(const ca_coord_vv *vv, const char *peer);
CA_API void ca_coord_state_vv(ca_coord_state *st, ca_coord_vv *out);
/* Call `fn` with every check-in the holder of `known` lacks.  Returning
 * non-zero from `fn` stops the walk and is returned. */
CA_API int ca_coord_delta_for(ca_coord_state *st, const ca_coord_vv *known,
                              int (*fn)(void *user, const ca_coord_checkin *ci), void *user);

/* ---- claiming and walking ---------------------------------------------- */

/* Tuning for one lane (one thread's worth of sequential walking). */
typedef struct ca_coord_lane_params {
    char peer[CA_COORD_PEER_MAX]; /* this lane's id, "<node>.<lane>" */
    uint64_t checkin_every;       /* walkers between check-ins (0 => 64) */
    uint64_t lease_secs;          /* a silent claim expires after this (0 => 120) */
    uint32_t claim_window;        /* candidate spread when choosing a unit (0 => 4) */
    uint64_t max_walkers;         /* stop the lane after this many (0 => until solved) */
    uint64_t max_units;           /* stop after this many units (0 => unbounded) */
} ca_coord_lane_params;

CA_API void ca_coord_lane_params_default(ca_coord_lane_params *p, const char *peer);

/* What a lane did before returning. */
typedef struct ca_coord_lane_result {
    uint64_t walkers, steps, dps, dead_trails, units_completed, checkins;
    int32_t have_solution;
    uint64_t solution;
} ca_coord_lane_result;

/*
 * Walk until the instance is solved, the budget is spent, or
 * should_stop() returns non-zero.  `on_checkin` is called with each
 * check-in *after* it has been merged locally: it is the transport hook
 * -- hand it to an agent channel, write it to a file, both.  Either
 * callback may be NULL.
 */
CA_API ca_status ca_coord_lane_run(const ca_coord_ctx *ctx, ca_coord_state *st,
                                   const ca_coord_lane_params *p,
                                   void (*on_checkin)(void *user, const ca_coord_checkin *ci),
                                   void *on_checkin_user, int (*should_stop)(void *user),
                                   void *should_stop_user, ca_coord_lane_result *out);

/* ---- the wire ---------------------------------------------------------- */

/*
 * One check-in as one line of printable ASCII, and back.  The format is
 * deliberately not JSON: a fixed, flat, separator-delimited grammar is
 * small enough to read in full, and `fuzz_coord` runs the parser
 * against arbitrary bytes.  Decoding never trusts a length or an index
 * from the input.
 */
CA_API size_t ca_coord_checkin_encode(const ca_coord_checkin *ci, char *buf, size_t cap);
CA_API ca_status ca_coord_checkin_decode(ca_coord_checkin *ci, const char *line);

/* ---- the hub ----------------------------------------------------------- */

typedef struct ca_coord_hub ca_coord_hub;

typedef struct ca_coord_hub_params {
    const char *bind;    /* "0.0.0.0:8080"; ":0" or "…:0" for an ephemeral port */
    const char *token;   /* required bearer token; NULL disables auth */
    uint64_t lease_secs; /* lease length used for reporting (0 => 120) */
    uint32_t push_ms;    /* how often an idle channel is examined (0 => 500) */
    uint32_t idle_secs;  /* drop a channel silent this long (0 => 300) */
    /* Called with every check-in newly accepted from an agent, after it
     * is merged: the durability hook.  Runs on the connection's thread
     * and must be thread-safe. */
    void (*on_checkin)(void *user, const ca_coord_checkin *ci);
    void *on_checkin_user;
} ca_coord_hub_params;

typedef struct ca_coord_hub_stats {
    uint64_t agents; /* channels open now */
    uint64_t channels_total;
    uint64_t accepted;     /* check-ins merged from agents */
    uint64_t rejected;     /* refused: bad job, forged point, bad line */
    uint64_t pushed;       /* check-ins sent down reverse channels */
    uint64_t unauthorized; /* requests refused for a bad or missing token */
} ca_coord_hub_stats;

CA_API void ca_coord_hub_params_default(ca_coord_hub_params *p);
CA_API ca_status ca_coord_hub_start(ca_coord_hub **out, const ca_coord_ctx *ctx, ca_coord_state *st,
                                    const ca_coord_hub_params *p);
/* The bound address as "host:port" -- read it when you asked for port 0. */
CA_API const char *ca_coord_hub_address(const ca_coord_hub *hub);
CA_API void ca_coord_hub_stats_get(const ca_coord_hub *hub, ca_coord_hub_stats *out);
CA_API void ca_coord_hub_stop(ca_coord_hub *hub);

/* ---- the agent --------------------------------------------------------- */

/*
 * The agent's end of the reverse channel: one outbound connection, held
 * open, reconnected with exponential backoff, merging what the hub
 * pushes into `st` and carrying this agent's check-ins up.  It needs no
 * inbound reachability and no address of its own.
 */
typedef struct ca_coord_agent ca_coord_agent;

typedef struct ca_coord_agent_stats {
    uint64_t received, sent, rejected, connects, reconnects;
    int32_t connected;
    char last_error[128];
} ca_coord_agent_stats;

/* url is "http://host:port[/prefix]" or "host:port".  An https:// URL is
 * refused rather than silently downgraded: there is no TLS here, so it
 * has to be reached through a terminator (see deploy/ca-coordinator).
 * Returns immediately; the first connection happens on the worker
 * thread, so an unreachable hub never delays the walk. */
CA_API ca_status ca_coord_agent_start(ca_coord_agent **out, const char *url, const char *token,
                                      const char *peer, const ca_coord_ctx *ctx,
                                      ca_coord_state *st);
/* Queue a check-in for the hub.  Non-blocking and safe from any lane. */
CA_API void ca_coord_agent_publish(ca_coord_agent *ag, const ca_coord_checkin *ci);
/* Wait until the queue has drained, or `timeout_ms` passes.  Returns 1
 * if it drained.  Call it before exiting: the queue lives in this
 * process, and the last check-in is the one carrying the solution. */
CA_API int ca_coord_agent_flush(ca_coord_agent *ag, uint64_t timeout_ms);
CA_API void ca_coord_agent_stats_get(ca_coord_agent *ag, ca_coord_agent_stats *out);
CA_API void ca_coord_agent_stop(ca_coord_agent *ag);

/* ---- one-shot client calls --------------------------------------------- */

/* GET /v1/job: an agent configured with only a URL needs no job file. */
CA_API ca_status ca_coord_fetch_job(const char *url, const char *token, ca_coord_job *job);
/* POST /v1/sync: push what the hub lacks, merge what it returns.  The
 * pollable fallback for anything that cannot hold a socket open. */
CA_API ca_status ca_coord_sync_once(const char *url, const char *token, const ca_coord_ctx *ctx,
                                    ca_coord_state *st, uint64_t *received, uint64_t *rejected);

#ifdef __cplusplus
}
#endif
#endif /* CA_COORD_H */
