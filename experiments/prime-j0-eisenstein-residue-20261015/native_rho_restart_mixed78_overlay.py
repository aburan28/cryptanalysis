#!/usr/bin/env python3
"""Add the opt-in mixed-radix arm to the hash-checked norm-6481 source."""
from pathlib import Path
import shutil
import sys

from native_rho_restart_joint243_overlay import main as add_triple243

HERE = Path(__file__).resolve().parent


def replace_once(source: str, before: str, after: str) -> str:
    assert source.count(before) == 1, before
    return source.replace(before, after, 1)


def main(root: Path) -> None:
    # This overlay checks all three parent source hashes before changing them.
    add_triple243(root)
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    joint = root / 'src/bin/rho_restart_joint.rs'
    extra_windows = root / 'src/bin/eisenstein_fixed/joint_mixed78.rs'
    extra_joint = root / 'src/bin/rho_restart_joint_mixed78.rs'
    assert not extra_windows.exists() and not extra_joint.exists()
    front_source = replace_once(front.read_text(),
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-triple243" {',
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-mixed78" {\n'
        '        let count: usize = args[2].parse().expect("rho restart count");\n'
        '        rho_restart_joint::run_mixed78(&args[1], count);\n'
        '        return;\n'
        '    }\n'
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-triple243" {')
    windows_source = replace_once(windows.read_text(),
        'include!("joint_norm58807.rs");',
        'include!("joint_norm58807.rs");\ninclude!("joint_mixed78.rs");')
    joint_source = joint.read_text()
    assert 'include!("rho_restart_joint243.rs");' in joint_source
    assert 'include!("rho_restart_joint_mixed78.rs");' not in joint_source
    front.write_text(front_source)
    windows.write_text(windows_source)
    joint.write_text(joint_source + '\ninclude!("rho_restart_joint_mixed78.rs");\n')
    shutil.copyfile(HERE / 'joint_mixed78.rs', extra_windows)
    shutil.copyfile(HERE / 'rho_restart_joint_mixed78.rs', extra_joint)


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
