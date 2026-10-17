#!/usr/bin/env python3
"""Replace independent projective digit synthesis with an adaptive addition graph."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = 'a0d9cdccc7586f3fbb898730f28d3ca49a542244923dd45c2e188e93c41a34c4'
WINDOWS_SHA256 = '7ae1e78e9751466b4ad87e92d56cba8bb0d0a6333049fadad12fe3dafd0de774'

OLD = '''        let mut a_powers = [U256Jacobian::identity();7];
        let mut b_powers = [U256Jacobian::identity();7];
        a_powers[0] = native_generator;
        b_powers[0] = native_tau;
        for bit in 1..7 {
            a_powers[bit] = a_powers[bit-1].double();
            b_powers[bit] = b_powers[bit-1].double();
        }
        let points = selected.iter().map(|&(da,db)| {
            let mut point = U256Jacobian::identity();
            for (value,powers) in [(da,&a_powers),(db,&b_powers)] {
                let magnitude = value.unsigned_abs() as usize;
                assert!(magnitude < 128);
                for bit in 0..7 {
                    if magnitude & (1usize << bit) != 0 {
                        let mut term = powers[bit];
                        if value < 0 {
                            term.y = u256_sub(super::U256::ZERO,term.y);
                        }
                        point = point.add_projective(term);
                    }
                }
            }
            assert_eq!(point.is_identity(),(da,db)==(0,0));
            point
        }).collect::<Vec<_>>();'''

NEW = '''        // Prim's algorithm on the selected digit lattice. An edge from
        // (a,b) to (c,d) synthesizes ((c-a)G+(d-b)τG) and adds its parent.
        // The root edge from (0,0) always remains available.
        let mut a_powers = [U256Jacobian::identity();8];
        let mut b_powers = [U256Jacobian::identity();8];
        a_powers[0] = native_generator;
        b_powers[0] = native_tau;
        for bit in 1..8 {
            a_powers[bit] = a_powers[bit-1].double();
            b_powers[bit] = b_powers[bit-1].double();
        }
        let edge_cost = |source: (i16,i16), target: (i16,i16), root: bool| {
            let da = i32::from(target.0)-i32::from(source.0);
            let db = i32::from(target.1)-i32::from(source.1);
            let bits = da.unsigned_abs().count_ones()+db.unsigned_abs().count_ones();
            if root { bits.saturating_sub(1) } else { bits }
        };
        let mut points = vec![U256Jacobian::identity();selected.len()];
        let mut built = vec![false;selected.len()];
        let mut best_parent = vec![0usize;selected.len()];
        let mut best_cost = vec![u32::MAX;selected.len()];
        built[0] = true;
        for target in 1..selected.len() {
            best_cost[target] = edge_cost((0,0),selected[target],true);
        }
        for _ in 1..selected.len() {
            let target = (1..selected.len()).filter(|&index| !built[index])
                .min_by_key(|&index| (best_cost[index],index)).unwrap();
            let parent = best_parent[target];
            let delta = (i32::from(selected[target].0)-i32::from(selected[parent].0),
                         i32::from(selected[target].1)-i32::from(selected[parent].1));
            let mut step = U256Jacobian::identity();
            for (value,powers) in [(delta.0,&a_powers),(delta.1,&b_powers)] {
                let magnitude = value.unsigned_abs() as usize;
                assert!(magnitude < 256);
                for bit in 0..8 {
                    if magnitude & (1usize << bit) != 0 {
                        let mut term = powers[bit];
                        if value < 0 {
                            term.y = u256_sub(super::U256::ZERO,term.y);
                        }
                        step = step.add_projective(term);
                    }
                }
            }
            points[target] = if parent == 0 { step }
                             else { points[parent].add_projective(step) };
            assert!(!points[target].is_identity());
            built[target] = true;
            for next in 1..selected.len() {
                if !built[next] {
                    let cost = edge_cost(selected[target],selected[next],false);
                    if cost < best_cost[next] {
                        best_cost[next] = cost;
                        best_parent[next] = target;
                    }
                }
            }
        }'''


def main(root: Path):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    front_text = front.read_text()
    windows_text = windows.read_text()
    assert front_text.count('--pilot-alt-projective-digits') == 1
    front_text = front_text.replace('--pilot-alt-projective-digits', '--pilot-alt-digit-graph', 1)
    before = 'unit_orbit_windows::multiply_u256_tau_alt_projective_digits_batch(&words)'
    after = 'unit_orbit_windows::multiply_u256_tau_alt_digit_graph_batch(&words)'
    assert front_text.count(before) == 1
    front_text = front_text.replace(before, after, 1)
    assert windows_text.count(OLD) == 1
    windows_text = windows_text.replace(OLD, NEW, 1)
    before = 'pub(super) fn multiply_u256_tau_alt_projective_digits_batch('
    after = 'pub(super) fn multiply_u256_tau_alt_digit_graph_batch('
    assert windows_text.count(before) == 1
    windows_text = windows_text.replace(before, after, 1)
    front.write_text(front_text)
    windows.write_text(windows_text)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
