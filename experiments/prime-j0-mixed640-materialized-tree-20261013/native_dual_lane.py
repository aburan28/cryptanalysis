#!/usr/bin/env python3
"""Generate a selective pre-tau evaluator with two streaming sum lanes."""

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
    source = source[:start] + """#[derive(Clone, Copy)]
enum Mixed640Lane {
    Empty,
    Affine(U256Affine),
    Projective(U256XYZZ),
}

fn mixed640_lane_push(lane: &mut Mixed640Lane, point: U256Affine) {
    *lane = match *lane {
        Mixed640Lane::Empty => Mixed640Lane::Affine(point),
        Mixed640Lane::Affine(first) =>
            Mixed640Lane::Projective(mixed640_add_affine_pair(first, point)),
        Mixed640Lane::Projective(sum) =>
            Mixed640Lane::Projective(sum.add_mixed(point)),
    };
}

fn mixed640_lane_node(lane: Mixed640Lane) -> Option<Mixed640TreeNode> {
    match lane {
        Mixed640Lane::Empty => None,
        Mixed640Lane::Affine(point) => Some(Mixed640TreeNode::Affine(point)),
        Mixed640Lane::Projective(point) => Some(Mixed640TreeNode::Projective(point)),
    }
}

fn mixed640_dual_lane_sum(lanes: [Mixed640Lane; 2]) -> U256XYZZ {
    let node = match (mixed640_lane_node(lanes[0]), mixed640_lane_node(lanes[1])) {
        (None, None) => return U256XYZZ::identity(),
        (Some(node), None) | (None, Some(node)) => node,
        (Some(left), Some(right)) => mixed640_tree_join(left, right),
    };
    match node {
        Mixed640TreeNode::Affine(point) => U256XYZZ::from_affine(point),
        Mixed640TreeNode::Projective(point) => point,
    }
}

""" + source[end:]
    source = replace_once(
        source,
        "    let mut selected = Vec::with_capacity(RADIX640_SCHEDULE.len());\n",
        "    let mut lanes = [Mixed640Lane::Empty; 2];\n"
        "    let mut selected_len = 0usize;\n",
    )
    source = replace_once(
        source,
        "            selected.push(Mixed640TreeNode::Affine(\n"
        "                tables.windows[index].select(seed_id, exponent, unit_code)));\n",
        "            let point = tables.windows[index].select(seed_id, exponent, unit_code);\n"
        "            mixed640_lane_push(&mut lanes[selected_len & 1], point);\n"
        "            selected_len += 1;\n",
    )
    source = replace_once(
        source,
        "    let additions = selected.len().saturating_sub(1);\n"
        "    let point = mixed640_single_tree(selected).affine_hex_binary_inverse();\n",
        "    let additions = selected_len.saturating_sub(1);\n"
        "    let point = mixed640_dual_lane_sum(lanes).affine_hex_binary_inverse();\n",
    )
    path.write_text(source)
    receipt_path = target / "native-bench-overlay.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        "variant": "selective_dual_lane",
        "dual_lane_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(path.read_bytes()).hexdigest(),
    })
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_dual_lane.py TARGET_DIR")
    main(Path(sys.argv[1]))
