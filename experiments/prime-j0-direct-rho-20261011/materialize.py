#!/usr/bin/env python3
"""Materialize priority-cover native source with a direct XYZZ rho variant."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-dual-orbit-20261011"
WINDOW = "src/bin/eisenstein_fixed/unit_orbit_windows.rs"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, (old[:100], source.count(old))
    return source.replace(old, new)


RHO_METHOD = '''    // Direct degree-seven endomorphism rho=1+tau in XYZZ coordinates.
    // The Jacobian polynomial is homogeneous in X,Y; the Z factor E
    // updates ZZ=Z^2 and ZZZ=Z^3 without constructing Z itself.
    fn rho_direct(self) -> Self {
        if self.is_identity() { return self; }
        let x3 = u256_mul(u256_square(self.x), self.x);
        let y2 = u256_square(self.y);
        let a = u256_add(u256_add(x3, x3), x3);
        let b = u256_add(u256_add(y2, y2), u256_add(y2, y2));
        let aa = u256_square(a);
        let bb = u256_square(b);
        let c = u256_mul_const_solinas(a, U256_BETA_CANONICAL[1]);
        let d = u256_mul_const_solinas(b, U256_BETA_CANONICAL[1]);
        let three_aa = u256_add(u256_add(aa, aa), aa);
        let three_d = u256_add(u256_add(d, d), d);
        let x_factor = u256_sub(
            u256_sub(super::U256::ZERO, three_aa),
            u256_mul(u256_add(b, three_d), u256_add(u256_sub(u256_add(a, a), b), c)));
        let two_c = u256_add(c, c);
        let four_c = u256_add(two_c, two_c);
        let nine_c = u256_add(u256_add(four_c, four_c), c);
        let two_d = u256_add(d, d);
        let four_d = u256_add(two_d, two_d);
        let seven_d = u256_sub(u256_add(four_d, four_d), d);
        let y_left = u256_mul(three_aa, u256_add(u256_sub(a, four_c), seven_d));
        let y_right = u256_mul(bb, u256_sub(u256_sub(b, a),
                                                 u256_add(u256_add(a, a), nine_c)));
        let e = u256_sub(u256_add(u256_sub(u256_add(a, a), b), c), d);
        let e2 = u256_square(e);
        let e3 = u256_mul(e, e2);
        Self { x: u256_mul(self.x, x_factor),
               y: u256_mul(self.y, u256_add(y_left, y_right)),
               zz: u256_mul(self.zz, e2),
               zzz: u256_mul(self.zzz, e3) }
    }

'''


def main() -> None:
    assert len(sys.argv) in (2, 3), "usage: materialize.py OUTPUT_DIRECTORY [PANEL_JSON]"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    subprocess.run([sys.executable, str(PARENT / "materialize_priority_native.py"),
                    str(output)], check=True, capture_output=True)
    parent_raw = (output / "materialization.json").read_bytes()
    parent = json.loads(parent_raw)
    if len(sys.argv) == 3:
        panel = Path(sys.argv[2]).resolve()
        target = output / "dual-rho0-fresh-inputs.json"
        target.write_bytes(panel.read_bytes())
        parent["assets_sha256"][target.name] = digest(target)
    path = output / WINDOW
    source = path.read_text()
    xyzz = source.index("impl U256XYZZ {")
    before_double = source.index("    fn double(self) -> Self {", xyzz)
    source = source[:before_double] + RHO_METHOD + source[before_double:]

    begin = source.index("pub(super) fn multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(")
    end = source.index("fn multiply_u256_sector_with<", begin)
    evaluator = source[begin:end]
    evaluator = replace_once(
        evaluator,
        "pub(super) fn multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(\n    scalar_words: [u64; 4],\n)",
        "fn multiply_u256_tau_dual_rho0_with(\n    scalar_words: [u64; 4], direct_rho: bool,\n)")
    evaluator = replace_once(evaluator,
        "    let rho = buckets[3];\n"
        "    let zero = buckets[0].add_xyzz(rho);\n"
        "    let one = buckets[1].add_xyzz(rho);\n"
        "    let point = zero.add_xyzz(\n"
        "        one.add_xyzz(buckets[2].tau()).tau()\n"
        "    ).affine_hex_binary_inverse();",
        "    let point = if direct_rho {\n"
        "        buckets[0].add_xyzz(\n"
        "            buckets[1].add_xyzz(buckets[2].tau()).tau()\n"
        "        ).add_xyzz(buckets[3].rho_direct()).affine_hex_binary_inverse()\n"
        "    } else {\n"
        "        let rho = buckets[3];\n"
        "        let zero = buckets[0].add_xyzz(rho);\n"
        "        let one = buckets[1].add_xyzz(rho);\n"
        "        zero.add_xyzz(one.add_xyzz(buckets[2].tau()).tau())\n"
        "            .affine_hex_binary_inverse()\n"
        "    };")
    evaluator += '''pub(super) fn multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    multiply_u256_tau_dual_rho0_with(scalar_words, false)
}

fn multiply_u256_tau_dual_rho0_direct_gauge_xyzz_tau(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    multiply_u256_tau_dual_rho0_with(scalar_words, true)
}

'''
    source = source[:begin] + evaluator + source[end:]

    test_begin = source.index("    fn dual_rho0_folded_matches_fresh_panel_and_controls() {")
    test_end = source.index("    #[test]\n    fn fused_orbit_matches", test_begin)
    test = source[test_begin:test_end]
    test = replace_once(test,
        "            let candidate = multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(words);",
        "            let candidate = multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(words);\n"
        "            let direct_rho = multiply_u256_tau_dual_rho0_direct_gauge_xyzz_tau(words);")
    test = replace_once(test,
        '            assert_eq!(candidate.0, direct.0, "direct point {index}");',
        '            assert_eq!(candidate.0, direct.0, "direct point {index}");\n'
        '            assert_eq!(candidate.0, direct_rho.0, "rho point {index}");\n'
        '            assert_eq!(candidate.1, direct_rho.1, "rho representative {index}");\n'
        '            assert_eq!((candidate.2, candidate.3, candidate.4, candidate.5, candidate.6),\n'
        '                       (direct_rho.2, direct_rho.3, direct_rho.4, direct_rho.5, direct_rho.6),\n'
        '                       "rho metadata {index}");')
    source = source[:test_begin] + test + source[test_end:]

    marker = "    #[test]\n    fn dual_rho0_folded_matches_fresh_panel_and_controls() {"
    direct_test = '''    #[test]
    fn xyzz_rho_direct_matches_group_sum_across_projective_gauges() {
        let first = FRONTIER19_TABLES.windows[0][1];
        let second = FRONTIER19_TABLES.windows[1][1];
        let p = U256XYZZ::from_affine(first);
        let q = U256XYZZ::from_affine(second);
        for point in [U256XYZZ::identity(), p, q, p.double(),
                      p.add_xyzz(q), p.add_xyzz(q).double(), p.tau()] {
            let direct = point.rho_direct();
            let group = point.add_xyzz(point.tau());
            assert_eq!(direct.affine_hex_binary_inverse(),
                       group.affine_hex_binary_inverse());
            assert_eq!(u256_mul(u256_square(direct.zz), direct.zz).0,
                       u256_square(direct.zzz).0);
        }
    }

'''
    source = replace_once(source, marker, direct_test + marker)
    path.write_text(source)
    receipt = {"schema": 1, "status": "materialized",
               "materializer_sha256": digest(Path(__file__)),
               "parent_materialization_sha256": sha256(parent_raw).hexdigest(),
               "generated_sha256": {name: digest(output / name)
                                    for name in parent["generated_sha256"]},
               "assets_sha256": parent["assets_sha256"]}
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
