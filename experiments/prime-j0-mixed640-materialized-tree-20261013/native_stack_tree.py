#!/usr/bin/env python3
"""Generate the selective evaluator with a fixed-capacity reduction tree."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE = HERE / "native_bench_cli.py"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"expected one source anchor, found {source.count(old)}: {old[:80]}")
    return source.replace(old, new, 1)


def main(target: Path) -> None:
    spec = importlib.util.spec_from_file_location("mixed640_bench_cli", BASE)
    bench = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(bench)
    bench.main("selective", target)
    target = target.resolve()
    path = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    source = path.read_text()
    start = source.index("fn mixed640_single_tree(mut selected: Vec<Mixed640TreeNode>)")
    end = source.index("pub(super) fn warm_mixed640_pretau_table()", start)
    source = source[:start] + """fn mixed640_single_tree(
    selected: &mut [Option<Mixed640TreeNode>; 14],
    mut len: usize,
) -> U256XYZZ {
    if len == 0 { return U256XYZZ::identity(); }
    while len > 1 {
        let pairs = len / 2;
        for i in 0..pairs {
            let a = selected[2 * i].take().expect("left tree node");
            let b = selected[2 * i + 1].take().expect("right tree node");
            selected[i] = Some(mixed640_tree_join(a, b));
        }
        if len % 2 != 0 { selected[pairs] = selected[len - 1].take(); }
        len = pairs + len % 2;
    }
    match selected[0].take().expect("root tree node") {
        Mixed640TreeNode::Affine(p) => U256XYZZ::from_affine(p),
        Mixed640TreeNode::Projective(p) => p,
    }
}

""" + source[end:]
    source = replace_once(
        source,
        "    let mut selected = Vec::with_capacity(RADIX640_SCHEDULE.len());\n",
        "    let mut selected: [Option<Mixed640TreeNode>; 14] = [None; 14];\n"
        "    let mut selected_len = 0usize;\n",
    )
    source = replace_once(
        source,
        "            selected.push(Mixed640TreeNode::Affine(\n"
        "                tables.windows[index].select(seed_id, exponent, unit_code)));\n",
        "            selected[selected_len] = Some(Mixed640TreeNode::Affine(\n"
        "                tables.windows[index].select(seed_id, exponent, unit_code)));\n"
        "            selected_len += 1;\n",
    )
    source = replace_once(
        source,
        "    let additions = selected.len().saturating_sub(1);\n"
        "    let point = mixed640_single_tree(selected).affine_hex_binary_inverse();\n",
        "    let additions = selected_len.saturating_sub(1);\n"
        "    let point = mixed640_single_tree(&mut selected, selected_len).affine_hex_binary_inverse();\n",
    )
    path.write_text(source)
    receipt_path = target / "native-bench-overlay.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        "variant": "selective_stack_tree",
        "stack_tree_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(path.read_bytes()).hexdigest(),
    })
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_stack_tree.py TARGET_DIR")
    main(Path(sys.argv[1]))
