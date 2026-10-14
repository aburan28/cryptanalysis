// ---------------------------------------------------------------------------
// Bernstein–Lange arm for the library walk (`StrongRhoG<F, S>`).
//
// Appended by `restore_sources.py` to a copy of crypto 770f6a69's
// `src/cryptanalysis/koblitz_strong_rho.rs` (tests removed, `crate::` paths
// made `crypto_lib::`). Everything above this banner is the library's code,
// unchanged. Two items are added:
//
// * `solve_with_table` is generated mechanically from the library's `solve`
//   by four textual substitutions (restore_sources.py, `SG_SOLVE_SUBS`): the
//   distinguished-point table is passed in instead of created empty, and the
//   successful collision reports whether its stored partner had `b = 0`
//   (a precomputed entry). With an empty table it is `solve`, step for step.
// * `bl_precompute` walks from `c·G` (no target) with the same jumps,
//   partition, canonicalization, distinguished-point rule, lane schedule and
//   batched step as `solve`; the step block below is `solve`'s, with its
//   counters renamed. Every new distinguished point is stored with its
//   logarithm `a` and `b = 0`.
// ---------------------------------------------------------------------------

/// Counts of one precomputation.
#[derive(Clone, Copy, Debug, Default)]
pub struct BlPrecomputeStats {
    /// Lane rounds started (the stop rule is evaluated before each round).
    pub rounds: u64,
    /// Walk steps (group additions of the walk proper).
    pub steps: u64,
    /// Walks started.
    pub walks: u64,
    /// Walks abandoned in a fruitless cycle.
    pub fruitless: u64,
    /// Fruitless cycles escaped (`escape_fruitless` only).
    pub escapes: u64,
    /// Walks abandoned at the length cap.
    pub capped: u64,
    /// Walks that ended on a distinguished point not yet stored.
    pub new_points: u64,
    /// Walks that ended on a distinguished point already stored (merged trails).
    pub duplicate_points: u64,
    /// Points on the trails of walks that stored a new point (length + 1 each).
    pub covered_points: u64,
    /// Steps of walks that ended on an already stored point.
    pub duplicate_walk_steps: u64,
    /// Steps of abandoned walks.
    pub abandoned_walk_steps: u64,
    /// Group additions, walk starts included.
    pub group_additions: u64,
    /// Scalar multiplications (the start stride and cursor).
    pub scalar_multiplications: u64,
    /// Distinguished points that were the point at infinity (never stored).
    pub infinity_points: u64,
}

impl<F: RhoField, S: RhoScalar> StrongRhoG<F, S> {
    // @@SOLVE_WITH_TABLE@@

    /// Whether `point` is distinguished under `dp_bits` (the walk's own rule).
    pub fn bl_is_distinguished(&self, point: RawPointG<F::E>, dp_bits: u32) -> bool {
        dp_hash(point) & ((1u64 << dp_bits) - 1) == 0
    }

    /// Whether `point` is its own signed-Frobenius representative.
    pub fn bl_is_canonical(&self, point: RawPointG<F::E>) -> bool {
        self.canonicalize(WalkStateG {
            point,
            a: S::one(),
            b: S::zero(),
        })
        .point
            == point
    }

    /// Bernstein–Lange precomputation into `table` (see the banner).
    /// `stop(stats, entries)` is called before every lane round; the walk is
    /// a function of `jumps`, `start_rng` and `params` only, so stopping at
    /// the same round count reproduces the same table.
    pub fn bl_precompute(
        &self,
        jumps: &[JumpG<F::E, S>],
        start_rng: &mut StdRng,
        params: &StrongRhoParams,
        table: &mut HashMap<(u8, F::E, F::E), (S, S)>,
        stop: &mut dyn FnMut(&BlPrecomputeStats, usize) -> bool,
    ) -> BlPrecomputeStats {
        assert_eq!(jumps.len(), JUMPS, "jump table must have JUMPS entries");
        assert!(params.dp_bits < 32, "dp_bits must be below 32");
        let modulus = self.modulus;
        let mut st = BlPrecomputeStats::default();
        let stride_a = start_rng.gen_range(S::one()..modulus);
        let stride = self.scalar_mul(self.generator, stride_a);
        let mut cursor_a = start_rng.gen_range(S::zero()..modulus);
        let mut cursor = self.scalar_mul(self.generator, cursor_a);
        st.scalar_multiplications += 2;

        let dp_mask = (1u64 << params.dp_bits) - 1;
        let walk_cap = 8u64 << params.dp_bits;
        let lanes_n = params.lanes.max(1);
        let mut lanes = vec![
            Lane {
                state: WalkStateG {
                    point: RawPointG::Infinity,
                    a: S::zero(),
                    b: S::zero(),
                },
                previous: [RawPointG::Infinity; 4],
                length: 0,
                live: false,
            };
            lanes_n
        ];
        let zero = F::E::default();
        let mut denominators = vec![zero; lanes_n];
        let mut jump_index = vec![0usize; lanes_n];
        let mut active: Vec<usize> = Vec::with_capacity(lanes_n);
        let mut scratch: Vec<F::E> = Vec::new();

        while !stop(&st, table.len()) {
            st.rounds += 1;
            // Start a walk in every idle lane: c·G, b = 0.
            for lane in lanes.iter_mut().filter(|lane| !lane.live) {
                loop {
                    st.walks += 1;
                    let start = cursor;
                    let start_a = cursor_a;
                    cursor = self.add(cursor, stride);
                    cursor_a = S::add_mod(cursor_a, stride_a, modulus);
                    st.group_additions += 1;
                    if start == RawPointG::Infinity {
                        continue;
                    }
                    lane.state = self.canonicalize(WalkStateG {
                        point: start,
                        a: start_a,
                        b: S::zero(),
                    });
                    lane.previous = [RawPointG::Infinity; 4];
                    lane.length = 0;
                    lane.live = true;
                    break;
                }
            }
            // Lanes standing on a distinguished point: store it if new.
            for lane in lanes.iter_mut() {
                if !(lane.live && dp_hash(lane.state.point) & dp_mask == 0) {
                    continue;
                }
                lane.live = false;
                if lane.state.point == RawPointG::Infinity {
                    st.infinity_points += 1;
                    continue;
                }
                let key = lane.state.point.key();
                if table.contains_key(&key) {
                    st.duplicate_points += 1;
                    st.duplicate_walk_steps += lane.length;
                } else {
                    table.insert(key, (lane.state.a, S::zero()));
                    st.new_points += 1;
                    st.covered_points += lane.length + 1;
                }
            }
            // One step for every live lane, denominators inverted together
            // (the step block of `solve`).
            active.clear();
            for (li, lane) in lanes.iter().enumerate() {
                if !lane.live {
                    continue;
                }
                let ji = partition(lane.state.point);
                let j = active.len();
                jump_index[j] = ji;
                denominators[j] = match (lane.state.point, jumps[ji].point) {
                    (RawPointG::Affine { x: x1, .. }, RawPointG::Affine { x: x2, .. }) => x1 ^ x2,
                    _ => zero,
                };
                active.push(li);
            }
            self.gf
                .batch_inv(&mut denominators[..active.len()], &mut scratch);
            for (j, &li) in active.iter().enumerate() {
                let lane = &mut lanes[li];
                let jump = &jumps[jump_index[j]];
                let sum = match (lane.state.point, jump.point) {
                    (RawPointG::Affine { x: x1, y: y1 }, RawPointG::Affine { x: x2, y: y2 })
                        if denominators[j] != zero =>
                    {
                        let slope = self.mul(y1 ^ y2, denominators[j]);
                        self.add_with_slope(x1, y1, x2, slope)
                    }
                    _ => self.add(lane.state.point, jump.point),
                };
                st.group_additions += 1;
                let next = self.canonicalize(WalkStateG {
                    point: sum,
                    a: S::add_mod(lane.state.a, jump.a, modulus),
                    b: lane.state.b,
                });
                st.steps += 1;
                lane.length += 1;
                if next.point == lane.state.point || lane.previous.contains(&next.point) {
                    if !params.escape_fruitless {
                        st.fruitless += 1;
                        st.abandoned_walk_steps += lane.length;
                        lane.live = false;
                        continue;
                    }
                    st.escapes += 1;
                    st.group_additions += 1;
                    lane.state = self.canonicalize(WalkStateG {
                        point: self.add(next.point, next.point),
                        a: S::add_mod(next.a, next.a, modulus),
                        b: S::add_mod(next.b, next.b, modulus),
                    });
                    lane.previous = [RawPointG::Infinity; 4];
                    continue;
                }
                if lane.length > walk_cap {
                    st.capped += 1;
                    st.abandoned_walk_steps += lane.length;
                    lane.live = false;
                    continue;
                }
                lane.previous = [
                    lane.state.point,
                    lane.previous[0],
                    lane.previous[1],
                    lane.previous[2],
                ];
                lane.state = next;
            }
        }
        st
    }
}
