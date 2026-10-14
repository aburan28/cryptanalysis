#!/usr/bin/env python3
"""Build a full-operation, one-scalar benchmark from a frozen table format."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import sys


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "selective-holdout.json"
OVERLAYS = {
    "affine": "native_affine128.py",
    "selective": "native_selective64.py",
    "hybrid": "native_hybrid64.py",
}


def once(body, old, new):
    assert body.count(old) == 1, old[:100]
    return body.replace(old, new, 1)


def main(variant, target):
    if variant not in OVERLAYS:
        raise ValueError("variant must be affine, selective, or hybrid")
    target = target.resolve()
    overlay_path = HERE / OVERLAYS[variant]
    spec = importlib.util.spec_from_file_location("mixed640_bench_overlay", overlay_path)
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    overlay.main(target)

    fixture_bytes = FIXTURE.read_bytes()
    fixture_hash = sha256(fixture_bytes).hexdigest()
    fixture_target = target / "src/bin/mixed640_bench_fixture.json"
    shutil.copyfile(FIXTURE, fixture_target)
    module_path = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = module_path.read_text()
    body = once(body,
        "pub(super) fn multiply_u256_tau_mixed640_pretau_tree(\n",
        "pub(super) fn warm_mixed640_pretau_table() -> usize {\n"
        "    MIXED640_PRETAU_TABLES.retained_bytes\n"
        "}\n\n"
        "pub(super) fn multiply_u256_tau_mixed640_pretau_tree(\n")
    module_path.write_text(body)

    front_path = target / "src/bin/eisenstein_fixed.rs"
    front = front_path.read_text()
    benchmark = (
        "fn benchmark_mixed640_pretau_case(case_index: usize) {\n"
        "    let panel: Value = serde_json::from_str(include_str!(\"mixed640_bench_fixture.json\"))\n"
        "        .expect(\"parse frozen fixture\");\n"
        "    let cases = panel[\"cases\"].as_array().expect(\"fixture cases\");\n"
        "    let case = cases.get(case_index).expect(\"case index\");\n"
        "    let scalar_hex = case[\"scalar_hex\"].as_str().expect(\"scalar\");\n"
        "    let scalar = BigInt::parse_bytes(scalar_hex.as_bytes(), 16).expect(\"scalar hex\");\n"
        "    let words = scalar_words_256(&scalar).expect(\"scalar words\");\n"
        "    let preparation_start = Instant::now();\n"
        "    let retained_bytes = unit_orbit_windows::warm_mixed640_pretau_table();\n"
        "    let preparation_ms = preparation_start.elapsed().as_secs_f64() * 1000.0;\n"
        "    let start = Instant::now();\n"
        "    let answer = std::hint::black_box(\n"
        "        unit_orbit_windows::multiply_u256_tau_mixed640_pretau_tree(\n"
        "            std::hint::black_box(words)));\n"
        "    let online_ms = start.elapsed().as_secs_f64() * 1000.0;\n"
        "    let point = &answer.0;\n"
        "    assert_eq!(point, case[\"point_hex\"].as_str().expect(\"expected point\"));\n"
        f"    println!(\"verified=1 online_ms={{online_ms:.6}} preparation_ms={{preparation_ms:.6}} retained_bytes={{retained_bytes}} case_id={{case_index}} fixture_sha256={fixture_hash} scalar={{scalar_hex}} point={{point}}\");\n"
        "}\n\n"
    )
    front = once(front, "fn main() {\n", benchmark + "fn main() {\n")
    front = once(front,
        "    let args: Vec<String> = std::env::args().skip(1).collect();\n",
        "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
        "    if args.len() == 2 && args[0] == \"--benchmark-mixed640-packet\" {\n"
        "        benchmark_mixed640_pretau_case(args[1].parse().expect(\"case index\"));\n"
        "        return;\n"
        "    }\n")
    front_path.write_text(front)

    receipt = {
        "schema": 1,
        "variant": variant,
        "fixture_sha256": fixture_hash,
        "overlay_sha256": sha256(overlay_path.read_bytes()).hexdigest(),
        "front_door_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(module_path.read_bytes()).hexdigest(),
        "generated_front_sha256": sha256(front_path.read_bytes()).hexdigest(),
    }
    (target / "native-bench-overlay.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: native_bench_cli.py {affine,selective,hybrid} TARGET_DIR")
    main(sys.argv[1], Path(sys.argv[2]))
