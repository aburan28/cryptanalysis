#ifndef CA_EC_TAU_INTERNAL_H
#define CA_EC_TAU_INTERNAL_H

#include "cryptanalysis/ca_group.h"

/* Conventional fixed-base binary comb control for public scalars and a point
 * in the declared subgroup. The 512 slots include identity; depth is
 * ceil(bitlength(subgroup order - 1)/9). Variable-time table lookup. */
#define CA_FIXED_COMB_WIDTH 9
#define CA_FIXED_COMB_ENTRIES (1u << CA_FIXED_COMB_WIDTH)
typedef struct ca_fixed_comb_precomp {
    const ca_group *g;
    ca_elem point[CA_FIXED_COMB_ENTRIES];
    unsigned depth;
    int identity;
} ca_fixed_comb_precomp;
int ca_ec_fixed_comb_prepare(const ca_group *g, const ca_elem *point,
                             ca_fixed_comb_precomp *out, uint64_t *doubles,
                             uint64_t *adds, uint64_t *inversions);
int ca_ec_fixed_comb_mul_profile(const ca_group *g, const ca_fixed_comb_precomp *pre,
                                  ca_elem *out, uint64_t k, uint64_t *doubles,
                                  uint64_t *adds);

/* Per-point width-4 table for repeated scalar multiplications within one rho
 * solve.  It is private to the C implementation and tied to its group. */
typedef struct ca_tau4_digit {
    int8_t a, b, seed, power, sign;
} ca_tau4_digit;

typedef struct ca_tau4_precomp {
    const ca_group *g;
    ca_elem seed[9];
    ca_elem tau_seed[9];
    ca_tau4_digit digit[81];
    uint64_t beta, beta2;
    __int128 v1x, v1y, v2x, v2y, det;
    int identity;
} ca_tau4_precomp;

#define CA_TAU_POS_Q 64
typedef struct ca_tau4_pos_precomp {
    ca_tau4_precomp base;
    ca_elem point[CA_TAU_POS_Q][2][9];
} ca_tau4_pos_precomp;

/* Compact public-scalar positional table. Its order-derived layer count is
 * a heuristic; any scalar needing more layers uses the generic fallback. */
typedef struct ca_tau4_pos_compact_precomp {
    ca_tau4_precomp base;
    ca_elem base_point;
    ca_elem *point; /* [layers][2][9] */
    size_t layers;
} ca_tau4_pos_compact_precomp;
size_t ca_ec_tau4_pos_compact_layers(const ca_group *g);
int ca_ec_tau4_pos_compact_prepare(const ca_group *g, const ca_elem *point,
                                   ca_tau4_pos_compact_precomp *out, uint64_t *triples,
                                   uint64_t *inversions);
int ca_ec_tau4_pos_compact_mul_profile(const ca_group *g,
                                       const ca_tau4_pos_compact_precomp *pre,
                                       ca_elem *out, uint64_t k, uint64_t *adds,
                                       uint64_t *rotations, uint64_t *fallbacks);
void ca_ec_tau4_pos_compact_clear(ca_tau4_pos_compact_precomp *pre);

/* Public-scalar width-3 tau NAF with a complete six-step, unit-orbit point
 * table at each prepared position. An over-capacity scalar uses generic mul. */
typedef struct ca_tau3_fused_precomp {
    ca_tau4_precomp base;
    ca_elem base_point;
    ca_elem *point; /* [blocks][CA_TAU3_FUSED_ORBITS] */
    size_t blocks;
} ca_tau3_fused_precomp;
size_t ca_ec_tau3_fused_blocks(const ca_group *g);
int ca_ec_tau3_fused_verify_map(void);
int ca_ec_tau3_fused_prepare(const ca_group *g, const ca_elem *point, ca_tau3_fused_precomp *out,
                             uint64_t *seed_ops, uint64_t *triples, uint64_t *tau_steps,
                             uint64_t *adds, uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau3_fused_prepare_verify(const ca_tau3_fused_precomp *pre);
int ca_ec_tau3_fused_recode_actions(const ca_tau3_fused_precomp *pre, uint64_t k,
                                    uint16_t actions[16], size_t *count);
int ca_ec_tau3_fused_recode_verify_scalar(const ca_tau3_fused_precomp *pre, uint64_t k);
int ca_ec_tau3_atlas_verify_map(void);
int ca_ec_tau3_atlas_recode_actions(const ca_tau3_fused_precomp *pre, uint64_t k,
                                    uint16_t actions[16], size_t *count);
int ca_ec_tau3_atlas_recode_verify_scalar(const ca_tau3_fused_precomp *pre, uint64_t k);
int ca_ec_tau3_fused_mul_profile(const ca_group *g, const ca_tau3_fused_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *adds, uint64_t *rotations,
                                 uint64_t *fallbacks);
int ca_ec_tau3_atlas_mul_profile(const ca_group *g, const ca_tau3_fused_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *adds, uint64_t *rotations,
                                 uint64_t *fallbacks);
size_t ca_ec_tau3_fused_static_bytes(void);
size_t ca_ec_tau3_atlas_static_bytes(void);
void ca_ec_tau3_fused_clear(ca_tau3_fused_precomp *pre);

/* Public-scalar scattered pair table over the complete six-step orbit table.
 * Each selected cross-block pair has one additional prepared affine point. */
typedef struct ca_tau3_scatter_entry {
    uint8_t i, j, u, v;
} ca_tau3_scatter_entry;
typedef struct ca_tau3_scatter_precomp {
    ca_tau3_fused_precomp full;
    ca_elem *extra;
    const ca_tau3_scatter_entry *entry;
    const uint16_t *offsets; /* [20*i+j] ranges into entry, plus sentinel */
    size_t extra_count;
} ca_tau3_scatter_precomp;
size_t ca_ec_tau3_scatter_point_entries(const ca_group *g);
size_t ca_ec_tau3_scatter_static_bytes(void);
int ca_ec_tau3_scatter_verify_map(void);
int ca_ec_tau3_scatter_prepare(const ca_group *g, const ca_elem *point,
                               ca_tau3_scatter_precomp *out, uint64_t *seed_ops, uint64_t *triples,
                               uint64_t *tau_steps, uint64_t *adds, uint64_t *rotations,
                               uint64_t *inversions);
int ca_ec_tau3_scatter_prepare_verify(const ca_tau3_scatter_precomp *pre);
int ca_ec_tau3_scatter_mul_profile(const ca_group *g, const ca_tau3_scatter_precomp *pre,
                                   ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                   uint64_t *fallbacks, uint64_t *matched_pairs,
                                   size_t *scratch_bytes);
int ca_ec_tau3_scatter_direct_mul_profile(const ca_group *g, const ca_tau3_scatter_precomp *pre,
                                          ca_elem *out, uint64_t k, uint64_t *adds,
                                          uint64_t *rotations, uint64_t *fallbacks,
                                          uint64_t *matched_pairs, size_t *scratch_bytes);
void ca_ec_tau3_scatter_clear(ca_tau3_scatter_precomp *pre);
unsigned ca_ec_tau3_scatter_match_graph(const uint32_t edge[20], unsigned count, int8_t mate[20]);

/* Sparse two-level six-step tau table. Selected hot pair orbits take one
 * mixed addition; every cold pair is composed from two prepared half points.
 * Public scalars only; over-capacity scalars use the generic multiplier. */
typedef struct ca_tau3_sparse_precomp {
    ca_tau4_precomp base;
    ca_elem base_point;
    ca_elem *point; /* per block: 18 half points, then selected hot pairs */
    const uint16_t *hot_offsets, *hot_ids, *hot_slots;
    size_t blocks, point_entries, hot_entries;
} ca_tau3_sparse_precomp;
size_t ca_ec_tau3_sparse_point_entries(const ca_group *g);
size_t ca_ec_tau3_sparse_static_bytes(void);
int ca_ec_tau3_sparse_verify_map(void);
int ca_ec_tau3_sparse_prepare(const ca_group *g, const ca_elem *point, ca_tau3_sparse_precomp *out,
                              uint64_t *seed_ops, uint64_t *triples, uint64_t *tau_steps,
                              uint64_t *adds, uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau3_sparse_prepare_verify(const ca_tau3_sparse_precomp *pre);
int ca_ec_tau3_sparse_verify_actions(const ca_tau3_sparse_precomp *pre);
int ca_ec_tau3_sparse_recode_actions(const ca_tau3_sparse_precomp *pre, uint64_t k,
                                     uint16_t actions[16], size_t *count);
int ca_ec_tau3_sparse_mul_profile(const ca_group *g, const ca_tau3_sparse_precomp *pre,
                                  ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                  uint64_t *cold_pairs, uint64_t *fallbacks);
void ca_ec_tau3_sparse_clear(ca_tau3_sparse_precomp *pre);

/* Exact minimum-addition public-scalar recoder over the same sparse table.
 * Its bounded per-scalar shortest path is charged inside online time. */
size_t ca_ec_tau3_radix27_static_bytes(void);
size_t ca_ec_tau3_radix27_online_scratch_bytes(void);
int ca_ec_tau3_radix27_verify_map(void);
int ca_ec_tau3_radix27_recode_actions(const ca_tau3_sparse_precomp *pre, uint64_t k,
                                      uint16_t actions[16], size_t *count, uint64_t *dp_states,
                                      uint64_t *dp_options);
int ca_ec_tau3_radix27_mul_profile(const ca_group *g, const ca_tau3_sparse_precomp *pre,
                                   ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                   uint64_t *cold_pairs, uint64_t *fallbacks, uint64_t *dp_states,
                                   uint64_t *dp_options);

int ca_ec_tau4_prepare(const ca_group *g, const ca_elem *point, ca_tau4_precomp *out,
                       uint64_t *ops);
int ca_ec_tau4_mul_prepared(const ca_group *g, const ca_tau4_precomp *pre, ca_elem *out, uint64_t k,
                            uint64_t *triples, uint64_t *adds);
/* Public-scalar research variant: score all 25 nearby Eisenstein coset
 * representatives by the prepared tripling/addition/rotation schedule. */
int ca_ec_tau4_mul_prepared_cost(const ca_group *g, const ca_tau4_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *triples, uint64_t *adds);
/* Public-scalar research modes: 0 canonical, 1 cost-aware representative,
 * 2 residue atlas, 3 bounded tail oracle, 4 pre-gated tail oracle,
 * 5 two-digit-pair shortest-path tail, 6 sign-folded 10-bit policy,
 * 7 sign-folded residue-local byte policy. */
int ca_ec_tau4_mul_prepared_profile(const ca_group *g, const ca_tau4_precomp *pre, ca_elem *out,
                                    uint64_t k, int recoder, uint64_t *triples, uint64_t *adds,
                                    uint64_t *rotations);
int ca_ec_tau4_tail_recode_compare_scalar(const ca_tau4_precomp *pre, uint64_t k);
int ca_ec_tau4_double_recode_verify_scalar(const ca_tau4_precomp *pre, uint64_t k);
int ca_ec_tau4_fold_recode_verify_scalar(const ca_tau4_precomp *pre, uint64_t k);
size_t ca_ec_tau4_fold_static_bytes(void);
int ca_ec_tau4_residue_recode_verify_scalar(const ca_tau4_precomp *pre, uint64_t k);
size_t ca_ec_tau4_residue_static_bytes(void);
/* Public-scalar fixed-point experiment: 121 prepared pair-contribution orbits. */
#define CA_TAU_PAIR_FUSED_REP_COUNT 121
typedef struct ca_tau_pair_fused_precomp {
    ca_tau4_precomp base;
    ca_elem orbit[CA_TAU_PAIR_FUSED_REP_COUNT];
} ca_tau_pair_fused_precomp;
int ca_ec_tau_pair_fused_prepare(const ca_group *g, const ca_elem *point,
                                 ca_tau_pair_fused_precomp *out, uint64_t *seed_ops,
                                 uint64_t *pair_adds, uint64_t *pair_rotations,
                                 uint64_t *inversions);
int ca_ec_tau_pair_fused_mul_profile(const ca_group *g, const ca_tau_pair_fused_precomp *pre,
                                     ca_elem *out, uint64_t k, uint64_t *triples, uint64_t *adds,
                                     uint64_t *rotations);
int ca_ec_tau_pair_fused_recode_verify_scalar(const ca_tau_pair_fused_precomp *pre, uint64_t k);
int ca_ec_tau_pair_fused_prepare_verify(const ca_tau_pair_fused_precomp *pre);
size_t ca_ec_tau_pair_fused_static_bytes(void);
/* Expand each pair orbit into all six signed unit images for direct lookup. */
#define CA_TAU_PAIR_COMPLETE_COUNT ((size_t)6 * CA_TAU_PAIR_FUSED_REP_COUNT)
typedef struct ca_tau_pair_complete_precomp {
    ca_tau4_precomp base;
    ca_elem exact[CA_TAU_PAIR_COMPLETE_COUNT];
} ca_tau_pair_complete_precomp;
int ca_ec_tau_pair_complete_prepare(const ca_group *g, const ca_elem *point,
                                    ca_tau_pair_complete_precomp *out, uint64_t *seed_ops,
                                    uint64_t *pair_adds, uint64_t *pair_rotations,
                                    uint64_t *inversions);
int ca_ec_tau_pair_complete_mul_profile(const ca_group *g, const ca_tau_pair_complete_precomp *pre,
                                        ca_elem *out, uint64_t k, uint64_t *triples, uint64_t *adds,
                                        uint64_t *rotations);
int ca_ec_tau_pair_complete_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre,
                                                 uint64_t k);
int ca_ec_tau_pair_complete_prepare_verify(const ca_tau_pair_complete_precomp *pre);
size_t ca_ec_tau_pair_complete_static_bytes(void);
/* Frozen modulus-27 periodic atlas and canonical-plus-oracle reference. */
int ca_ec_tau_pair_periodic_recode_words(const ca_tau_pair_complete_precomp *pre, uint64_t k,
                                         int gated, uint16_t words[128], size_t *count,
                                         uint64_t *lookups, uint64_t *accepted,
                                         uint64_t *fallbacks);
int ca_ec_tau_pair_periodic_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre,
                                                 uint64_t k, int gated);
int ca_ec_tau_pair_periodic_mul_profile(const ca_group *g, const ca_tau_pair_complete_precomp *pre,
                                        ca_elem *out, uint64_t k, int gated, uint64_t *triples,
                                        uint64_t *adds, uint64_t *lookups,
                                        uint64_t *accepted, uint64_t *fallbacks);
size_t ca_ec_tau_pair_periodic_static_bytes(void);
size_t ca_ec_tau_pair_firstword_static_bytes(void);
/* Exact bounded tail with tau^2, tau, or doubling actions. The top two
 * action bits select the radix; the low ten bits are an existing pair word. */
int ca_ec_tau_pair_mixed_recode_actions(const ca_tau_pair_complete_precomp *pre, uint64_t k,
                                         uint16_t actions[128], size_t *count,
                                         uint64_t *lookups, uint64_t *fallbacks);
int ca_ec_tau_pair_mixed_verify_map(void);
int ca_ec_tau_pair_mixed_verify_tau_kernel(const ca_group *g, const ca_elem *point);
int ca_ec_tau_pair_mixed_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre, uint64_t k);
int ca_ec_tau_pair_mixed_mul_profile(const ca_group *g, const ca_tau_pair_complete_precomp *pre,
                                     ca_elem *out, uint64_t k, uint64_t *triples,
                                     uint64_t *tau_steps, uint64_t *doubles, uint64_t *adds,
                                     uint64_t *lookups, uint64_t *fallbacks);
size_t ca_ec_tau_pair_mixed_static_bytes(void);
/* Same radix graph with all 727 prepared words legal after every radix. */
int ca_ec_tau_pair_mixed_full_recode_actions(const ca_tau_pair_complete_precomp *pre, uint64_t k,
                                              uint16_t actions[128], size_t *count,
                                              uint64_t *lookups, uint64_t *fallbacks);
int ca_ec_tau_pair_mixed_full_verify_map(void);
int ca_ec_tau_pair_mixed_full_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre,
                                                    uint64_t k);
int ca_ec_tau_pair_mixed_full_mul_profile(const ca_group *g,
                                          const ca_tau_pair_complete_precomp *pre,
                                          ca_elem *out, uint64_t k, uint64_t *triples,
                                          uint64_t *tau_steps, uint64_t *doubles, uint64_t *adds,
                                          uint64_t *lookups, uint64_t *fallbacks);
size_t ca_ec_tau_pair_mixed_full_static_bytes(void);
/* Private exhaustive/differential test hook for signed tau coordinates. */
int ca_ec_tau4_recode_compare(int64_t x, int64_t y);
int ca_ec_tau4_recode_compare_scalar(const ca_tau4_precomp *pre, uint64_t k);

/* Fixed-base positional table: 3^q times each seed and tau-seed point.
 * precompute_triples excludes the 19 operations in the base preparation. */
int ca_ec_tau4_pos_prepare(const ca_group *g, const ca_elem *point, ca_tau4_pos_precomp *out,
                           uint64_t *precompute_triples);
/* Same affine table, built with one global normalization inversion.
 * Temporary heap scratch is (sizeof(tau_jac) + sizeof(uint64_t)) *
 * CA_TAU_POS_Q * 2 * 9 bytes. */
int ca_ec_tau4_pos_global_prepare(const ca_group *g, const ca_elem *point, ca_tau4_pos_precomp *out,
                                  uint64_t *precompute_triples);
int ca_ec_tau4_pos_mul(const ca_group *g, const ca_tau4_pos_precomp *pre, ca_elem *out, uint64_t k,
                       uint64_t *adds, uint64_t *rotations);
/* Public-scalar batch. Each block shares one affine-output inversion.
 * block_size is in [1,4096]; scratch is block_size * 32 bytes. */
int ca_ec_tau4_pos_mul_batch(const ca_group *g, const ca_tau4_pos_precomp *pre, ca_elem *out,
                             const uint64_t *scalars, size_t count, size_t block_size,
                             uint64_t *adds, uint64_t *rotations, uint64_t *output_inversions);

/* Fixed-base eight-digit fusion. Call clear after every successful prepare.
 * The compact affine table has blocks * 29593 entries on the heap. */
typedef struct ca_tau8_fused_precomp {
    ca_tau4_pos_precomp pos;
    ca_elem *point;
    size_t blocks;
    int orbit; /* 0: full pair table; 1: all unit orbits; 2: hot orbits */
    int selector; /* 0: shortest L1; 1: always two; 2: gated second; 3: carry steering;
                   * 4: gated second after carry steering */
} ca_tau8_fused_precomp;

int ca_ec_tau8_fused_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                             ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                             uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau8_orbit_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                             ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                             uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau8_hot_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                           ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                           uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau8_hot_adapt2_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                  ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                                  uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau8_hot_gated_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                 ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                                 uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau8_hot_steer_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                 ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                                 uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau8_hot_gated2_steer_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                        ca_tau8_fused_precomp *out, uint64_t *triples,
                                        uint64_t *adds, uint64_t *rotations, uint64_t *inversions);
size_t ca_ec_tau8_steer_static_bytes(void);
void ca_ec_tau8_fused_clear(ca_tau8_fused_precomp *pre);
int ca_ec_tau8_fused_mul_batch(const ca_group *g, const ca_tau8_fused_precomp *pre, ca_elem *out,
                               const uint64_t *scalars, size_t count, size_t block_size,
                               uint64_t *adds, uint64_t *rotations, uint64_t *output_inversions,
                               uint64_t *fallbacks);
int ca_ec_tau8_fused_mul_batch_profile(const ca_group *g, const ca_tau8_fused_precomp *pre,
                                       ca_elem *out, const uint64_t *scalars, size_t count,
                                       size_t block_size, uint64_t *adds, uint64_t *rotations,
                                       uint64_t *output_inversions, uint64_t *fallbacks,
                                       uint64_t *second_recodes, uint64_t *steered_blocks);

/* Complete residue-orbit tables with an exact narrow tail. Schedule 0 is
 * (10,10,10,10), schedule 1 is (12,12,12,8,8). Public scalars only. */
typedef struct ca_tau_wide_precomp {
    ca_tau4_pos_precomp pos;
    ca_elem *point;
    size_t point_offset[6];
    uint8_t width[5];
    uint8_t position[5];
    size_t blocks;
    int schedule;
} ca_tau_wide_precomp;

int ca_ec_tau_wide_prepare(const ca_group *g, const ca_elem *point, int schedule,
                           ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                           uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau_wide_prepare_graph(const ca_group *g, const ca_elem *point, int schedule,
                                 ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                                 uint64_t *rotations, uint64_t *inversions);
int ca_ec_tau_wide_prepare_packed(const ca_group *g, const ca_elem *point, int schedule,
                                  ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                                  uint64_t *rotations, uint64_t *inversions,
                                  uint64_t *slot_lookups);
typedef struct ca_tau_wide_wavefront_stats {
    uint64_t slot_lookups, denominators, exceptional_edges, doubling_edges;
} ca_tau_wide_wavefront_stats;
int ca_ec_tau_wide_prepare_wavefront(const ca_group *g, const ca_elem *point, int schedule,
                                     ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                                     uint64_t *rotations, uint64_t *inversions,
                                     ca_tau_wide_wavefront_stats *stats);
void ca_ec_tau_wide_clear(ca_tau_wide_precomp *pre);
size_t ca_ec_tau_wide_entries(int schedule);
size_t ca_ec_tau_wide_static_bytes(int schedule);
size_t ca_ec_tau_wide_graph_recipe_bytes(int schedule);
size_t ca_ec_tau_wide_packed_recipe_bytes(int schedule);
size_t ca_ec_tau_wide_temp_bytes(int schedule);
size_t ca_ec_tau_wide_wavefront_temp_bytes(int schedule);
int ca_ec_tau_wide_mul_batch_profile(const ca_group *g, const ca_tau_wide_precomp *pre,
                                     ca_elem *out, const uint64_t *scalars, size_t count,
                                     size_t block_size, uint64_t *adds, uint64_t *rotations,
                                     uint64_t *output_inversions, uint64_t *fallbacks);

#endif
