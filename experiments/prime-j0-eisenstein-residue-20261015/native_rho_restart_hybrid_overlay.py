#!/usr/bin/env python3
"""Add the exact-output rho restart pilot to the archived norm-4033 source."""
from hashlib import sha256
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
FRONT_SHA256 = '4f216696cc6d512563b375d306b6d55c2f4715d963e4f7b8782786fa797a252a'
WINDOWS_SHA256 = '1cefa4288120140cc6e74303e6905bace389f50a9de2c725f89f473d4d57ab85'


def replace_once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after, 1)


def main(root):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    source = front.read_text()
    source = replace_once(source, 'mod unit_orbit_windows;',
                          'mod unit_orbit_windows;\nmod rho_restart_hybrid;')
    source = replace_once(source,
        '    let args: Vec<String> = std::env::args().skip(1).collect();\n',
        '    let args: Vec<String> = std::env::args().skip(1).collect();\n'
        '    if args.len() == 4 && args[0] == "--pilot-rho-restart" {\n'
        '        let count: usize = args[3].parse().expect("rho restart count");\n'
        '        rho_restart_hybrid::run(&args[1], &args[2], count);\n'
        '        return;\n'
        '    }\n')
    front.write_text(source)
    shutil.copyfile(HERE / 'rho_restart_hybrid.rs',
                    root / 'src/bin/rho_restart_hybrid.rs')


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
