#!/usr/bin/env python3
"""Add the opt-in norm-58807 arm to an exact norm-6481 source snapshot."""
from hashlib import sha256
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
FRONT_SHA256 = 'a1142e716da32b511f1367bcb49f90e6f5543271b9249941db5aa0a3f8824483'
WINDOWS_SHA256 = 'c436e4cb9f1ef371ceff817d47a58bcdb6cc307a8fa2a31b1899af8f2e44d275'
JOINT_SHA256 = '72048617300d0e1acb3cc98693b8b0a4c3e4f5ba141e7445cf4775f2d8b4a933'


def replace_once(source, before, after):
    assert source.count(before) == 1, before
    return source.replace(before, after, 1)


def main(root):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    joint = root / 'src/bin/rho_restart_joint.rs'
    for path, expected in ((front, FRONT_SHA256), (windows, WINDOWS_SHA256),
                           (joint, JOINT_SHA256)):
        assert sha256(path.read_bytes()).hexdigest() == expected, path
    extra_windows = root / 'src/bin/eisenstein_fixed/joint_norm58807.rs'
    extra_joint = root / 'src/bin/rho_restart_joint243.rs'
    assert not extra_windows.exists() and not extra_joint.exists()
    front_source = replace_once(front.read_text(),
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-triple81" {',
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-triple243" {\n'
        '        let count: usize = args[2].parse().expect("rho restart count");\n'
        '        rho_restart_joint::run_triple243(&args[1], count);\n'
        '        return;\n'
        '    }\n'
        '    if args.len() == 3 && args[0] == "--pilot-rho-restart-joint-triple81" {')
    windows_source = replace_once(windows.read_text(),
        'include!("joint_norm4033.rs");',
        'include!("joint_norm4033.rs");\ninclude!("joint_norm58807.rs");')
    joint_source = joint.read_text()
    assert 'include!("rho_restart_joint243.rs");' not in joint_source
    front.write_text(front_source)
    windows.write_text(windows_source)
    joint.write_text(joint_source + '\ninclude!("rho_restart_joint243.rs");\n')
    shutil.copyfile(HERE / 'joint_norm58807.rs', extra_windows)
    shutil.copyfile(HERE / 'rho_restart_joint243.rs', extra_joint)


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
