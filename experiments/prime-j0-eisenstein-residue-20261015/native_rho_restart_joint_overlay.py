#!/usr/bin/env python3
"""Add the joint norm-4033 rho restart path to the frozen hybrid source."""
from hashlib import sha256
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
FRONT_SHA256 = '3fb9a699e0261849eee9bea04b215724f1df18a12ec9df97b6d779028c1a1d55'
WINDOWS_SHA256 = '1cefa4288120140cc6e74303e6905bace389f50a9de2c725f89f473d4d57ab85'
HYBRID_SHA256 = 'db6c2f69d38aac0a3109adfcd8bbe88381ff82b52c087d57bb95d24fa9b947cf'


def replace_once(source, before, after):
    assert source.count(before) == 1, before
    return source.replace(before, after, 1)


def main(root):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    hybrid = root / 'src/bin/rho_restart_hybrid.rs'
    for path, expected in ((front, FRONT_SHA256), (windows, WINDOWS_SHA256),
                           (hybrid, HYBRID_SHA256)):
        assert sha256(path.read_bytes()).hexdigest() == expected, path
    front_source = replace_once(front.read_text(),
        'mod rho_restart_hybrid;', 'mod rho_restart_hybrid;\nmod rho_restart_joint;')
    front_source = replace_once(front_source,
        '    let args: Vec<String> = std::env::args().skip(1).collect();\n',
        '    let args: Vec<String> = std::env::args().skip(1).collect();\n'
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-fused" {\n'
        '        let count: usize = args[2].parse().expect("rho restart count");\n'
        '        rho_restart_joint::run_fused(&args[1], count);\n'
        '        return;\n'
        '    }\n'
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-profile" {\n'
        '        let count: usize = args[2].parse().expect("rho restart count");\n'
        '        rho_restart_joint::run_profile(&args[1], count);\n'
        '        return;\n'
        '    }\n'
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-demand" {\n'
        '        let count: usize = args[2].parse().expect("rho restart count");\n'
        '        rho_restart_joint::run_demand(&args[1], count);\n'
        '        return;\n'
        '    }\n'
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint" {\n'
        '        let count: usize = args[2].parse().expect("rho restart count");\n'
        '        rho_restart_joint::run(&args[1], count);\n'
        '        return;\n'
        '    }\n')
    windows_source = replace_once(windows.read_text(),
        '\n#[cfg(test)]\nmod split_prime_tests {',
        '\ninclude!("joint_norm4033.rs");\n\n#[cfg(test)]\nmod split_prime_tests {')
    hybrid_source = replace_once(hybrid.read_text(),
        '    assert!(mode == "openssl" || mode == "hybrid");',
        '    assert!(mode == "openssl" || mode == "openssl_nowarm" || mode == "hybrid");')
    hybrid_source = replace_once(hybrid_source,
        '    let warm_start = Instant::now();\n'
        '    let warm = unsafe { crypto.baseline(cases[0].a_bn, cases[0].b_bn) };\n'
        '    assert_eq!(warm, cases[0].expected);\n'
        '    let openssl_warmup_ms = warm_start.elapsed().as_secs_f64() * 1000.0;',
        '    let openssl_warmup_ms = if mode == "openssl_nowarm" { 0.0 } else {\n'
        '        let warm_start = Instant::now();\n'
        '        let warm = unsafe { crypto.baseline(cases[0].a_bn, cases[0].b_bn) };\n'
        '        assert_eq!(warm, cases[0].expected);\n'
        '        warm_start.elapsed().as_secs_f64() * 1000.0\n'
        '    };')
    front.write_text(front_source)
    windows.write_text(windows_source)
    hybrid.write_text(hybrid_source)
    shutil.copyfile(HERE / 'rho_restart_joint.rs', root / 'src/bin/rho_restart_joint.rs')
    shutil.copyfile(HERE / 'joint_norm4033.rs',
                    root / 'src/bin/eisenstein_fixed/joint_norm4033.rs')


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
