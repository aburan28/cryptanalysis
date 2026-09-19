/*
 * ca_dist.h - the distributed (van Oorschot-Wiener) rho protocol.
 *
 * ca_rho_solve is one process that walks, stores its own distinguished
 * points and finds its own collision.  That does not distribute: N such
 * processes with different seeds are N independent searches, so N of them
 * expect to finish in 1/N of the time only in the sense that any one of
 * them might, and the work they do is N times the work of one.
 *
 * The parallel collision search of van Oorschot and Wiener distributes
 * because every walker iterates *the same function* and reports only its
 * distinguished points.  Two walks that ever meet stay together and
 * arrive at the same distinguished point, whichever machines they ran on,
 * so P machines finish in expected 1/P of the time for the same total
 * work.  This header is that protocol, split into the two halves a fleet
 * needs:
 *
 *   ca_dist_walk    a worker: walks a unit's budget, emits points
 *   ca_dist_merger  a server: ingests points from anywhere, solves
 *
 * What makes it a protocol rather than two functions:
 *
 *   * **One walk function, fleet-wide.**  The multipliers are derived from
 *     the campaign seed alone, so every agent that is given the same
 *     ca_dist_campaign iterates the identical function.  A campaign field
 *     that differs between two agents makes their points incomparable, so
 *     ca_dist_campaign_id hashes the whole thing and the merger refuses
 *     points from a different id.
 *   * **Units are deterministic and therefore replayable.**  A unit's
 *     starting points come from (campaign seed, unit id, walk index).  A
 *     unit that is run twice -- after a crash, or by a scheduler that
 *     cannot tell whether the first agent died -- produces exactly the
 *     same points, so at-least-once delivery costs duplicates and never
 *     corruption.
 *   * **The merger trusts nothing.**  Every submitted point is checked:
 *     Y = a*G + b*H must hold and the point must really be distinguished.
 *     Verification costs two scalar multiplications, against the 2^dp_bits
 *     walk steps that produced the point, so it is affordable at the
 *     server even when the agents are not trusted at all.
 *
 * The negation map is deliberately *not* used here; see ca_dist_campaign.
 */
#ifndef CA_DIST_H
#define CA_DIST_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

/* A distinguished point on the wire: 32 bytes, little-endian, fixed.
 *
 * w0/w1 are the element's canonical words (ca_group_decode), which is the
 * x coordinate and the y coordinate on a curve, and the residue with w1=0
 * in Z_p^*.  a and b are the exponents with Y = a*G + b*H, reduced mod n. */
typedef struct ca_dist_point {
    uint64_t w0, w1;
    uint64_t a, b;
} ca_dist_point;

#define CA_DIST_POINT_BYTES 32

/* Everything that must be identical across the fleet.
 *
 * negation_map is absent on purpose.  The sqrt(2) the negation map buys
 * comes with fruitless cycles, and escaping those needs per-walk state
 * (a look-ahead rule and a sliding window) whose behaviour has to agree
 * bit for bit on every machine for the walks to stay mergeable.  A
 * distributed walk that disagrees with itself does not fail loudly; it
 * quietly stops finding collisions.  ca_rho_solve keeps the negation map
 * for the single-process case, where that risk does not arise. */
typedef struct ca_dist_campaign {
    uint64_t seed;   /* derives the multipliers; identical fleet-wide */
    uint32_t r;      /* number of multipliers; 0 => resolve from the order */
    int32_t dp_bits; /* distinguished-point bits; -1 => resolve */
} ca_dist_campaign;

/* One unit of work.  A unit is identified by its id, and the id is what
 * makes its points reproducible, so ids must not be reused within one
 * campaign for different work. */
typedef struct ca_dist_unit {
    uint64_t id;
    uint32_t walks;      /* concurrent walks; 0 => resolve (batched inversion) */
    uint64_t max_steps;  /* stop after this many walk steps (0 => no limit) */
    uint64_t max_points; /* stop after this many points (0 => no limit) */
} ca_dist_unit;

/* Sink for emitted points.  Return CA_OK to continue; any other status
 * stops the walk and is returned by ca_dist_walk (CA_ERR_LIMIT is the
 * conventional "I have enough"). */
typedef ca_status (*ca_dist_sink)(void *ctx, const ca_dist_point *pt);

CA_API void ca_dist_campaign_default(ca_dist_campaign *c);

/* Fill in the auto fields (r, dp_bits) from the group order.
 *
 * Idempotent and a pure function of (group order, campaign): two agents
 * that resolve the same campaign get the same numbers, which is what
 * makes their points comparable.  Resolve once in the control plane and
 * ship explicit values if you would rather not rely on that. */
CA_API ca_status ca_dist_resolve(const ca_group *g, ca_dist_campaign *c);

/* A 64-bit id for a resolved campaign: group, base, target and campaign
 * fields.  Two agents agree on the walk function if and only if they
 * agree on this (up to the 2^-64 of a hash collision). */
CA_API uint64_t ca_dist_campaign_id(const ca_group *g, const ca_elem *base, const ca_elem *target,
                                    const ca_dist_campaign *c);

/* Expected number of distinguished points in a full search: about
 * 1.25*sqrt(n) steps at one point per 2^dp_bits steps.  What a control
 * plane sizes its storage and its unit budgets from. */
CA_API double ca_dist_expected_points(const ca_group *g, const ca_dist_campaign *c);

/* Walk one unit, emitting points to the sink.
 *
 * Returns CA_OK when the unit's budget is exhausted (the normal end of a
 * unit), CA_ERR_LIMIT when the sink asked to stop, or the sink's own
 * status when it failed.  Never solves anything: solving is the merger's
 * job, and a worker that could solve would need the whole corpus. */
CA_API ca_status ca_dist_walk(const ca_group *g, const ca_elem *base, const ca_elem *target,
                              const ca_dist_campaign *c, const ca_dist_unit *u, ca_dist_sink sink,
                              void *ctx, ca_stats *st);

/* ---- the merger -------------------------------------------------------- */

typedef struct ca_dist_merger ca_dist_merger;

/* `expect` is a hint for the table size (0 => from the campaign). */
CA_API ca_status ca_dist_merger_new(ca_dist_merger **m, const ca_group *g, const ca_elem *base,
                                    const ca_elem *target, const ca_dist_campaign *c,
                                    size_t expect);

/* Verification of submitted points, on by default.  Turn it off only for
 * a corpus this process produced itself. */
CA_API void ca_dist_merger_set_verify(ca_dist_merger *m, int on);

/* Add points.  Counts (may be NULL): accepted, duplicates (the same point
 * with the same exponents), rejected (failed verification).  Returns CA_OK
 * even when every point is rejected -- a bad agent is not the server's
 * error -- and CA_ERR_NOMEM if the table cannot grow. */
CA_API ca_status ca_dist_merger_add(ca_dist_merger *m, const ca_dist_point *pts, size_t n,
                                    size_t *accepted, size_t *duplicates, size_t *rejected);

/* 1 once a collision has been turned into a verified discrete log. */
CA_API int ca_dist_merger_solved(const ca_dist_merger *m, uint64_t *x);

/* Points held, and the totals since creation. */
CA_API size_t ca_dist_merger_size(const ca_dist_merger *m);
CA_API void ca_dist_merger_stats(const ca_dist_merger *m, ca_stats *st);
CA_API void ca_dist_merger_free(ca_dist_merger *m);

/* ---- the wire format --------------------------------------------------- */

CA_API void ca_dist_point_encode(unsigned char out[CA_DIST_POINT_BYTES], const ca_dist_point *p);
CA_API void ca_dist_point_decode(ca_dist_point *p, const unsigned char in[CA_DIST_POINT_BYTES]);

#ifdef __cplusplus
}
#endif
#endif /* CA_DIST_H */
