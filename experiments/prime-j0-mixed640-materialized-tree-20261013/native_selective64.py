#!/usr/bin/env python3
"""Build selected 96-byte orbit columns beside 64-byte affine columns."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def once(body, old, new):
    assert body.count(old) == 1, old[:100]
    return body.replace(old, new, 1)


def main(target):
    spec = importlib.util.spec_from_file_location("mixed640_affine_overlay", HERE / "native_affine128.py")
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    overlay.main(target)
    policy_path = HERE / "selective-policy.json"
    policy = json.loads(policy_path.read_bytes())
    assert policy["status"] == "training_only_exact_knapsack_policy"
    selected = policy["compressed_channels"]
    assert len(selected) == 14 and all(len(row) == 2 for row in selected)
    source = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = source.read_text()
    marker = "// Inserted into the pinned mixed-radix 640 module by native_overlay.py."
    before, variant = body.split(marker, 1)
    flags = ",\n    ".join(
        "[" + ", ".join("true" if flag else "false" for flag in row) + "]"
        for row in selected)
    old = (
        "#[derive(Clone, Copy)]\n"
        "struct Mixed640AffinePair {\n"
        "    plain: U256Affine,\n"
        "    tau: U256Affine,\n"
        "}\n\n"
        "impl Mixed640AffinePair {\n"
        "    fn select(self, exponent: usize, unit_code: usize) -> U256Affine {\n"
        "        assert!(exponent < 2);\n"
        "        let point = if exponent == 0 { self.plain } else { self.tau };\n"
        "        point.unit_solinas(unit_code)\n"
        "    }\n"
        "}\n"
    )
    replacement = (
        f"const MIXED640_COMPRESSED: [[bool; 2]; 14] = [\n    {flags}\n];\n\n"
        "enum Mixed640Column {\n"
        "    Affine(Box<[U256Affine]>),\n"
        "    Orbit(Box<[U256TwoXAffine]>),\n"
        "}\n\n"
        "impl Mixed640Column {\n"
        "    fn len(&self) -> usize {\n"
        "        match self { Self::Affine(v) => v.len(), Self::Orbit(v) => v.len() }\n"
        "    }\n"
        "    fn payload_bytes(&self) -> usize {\n"
        "        match self {\n"
        "            Self::Affine(v) => v.len() * size_of::<U256Affine>(),\n"
        "            Self::Orbit(v) => v.len() * size_of::<U256TwoXAffine>(),\n"
        "        }\n"
        "    }\n"
        "    fn select(&self, seed_id: usize, unit_code: usize) -> U256Affine {\n"
        "        match self {\n"
        "            Self::Affine(v) => v[seed_id].unit_solinas(unit_code),\n"
        "            Self::Orbit(v) => v[seed_id].unit(unit_code),\n"
        "        }\n"
        "    }\n"
        "}\n\n"
        "struct Mixed640SelectiveRow {\n"
        "    plain: Mixed640Column,\n"
        "    tau: Mixed640Column,\n"
        "}\n\n"
        "impl Mixed640SelectiveRow {\n"
        "    fn len(&self) -> usize {\n"
        "        assert_eq!(self.plain.len(), self.tau.len());\n"
        "        self.plain.len()\n"
        "    }\n"
        "    fn payload_bytes(&self) -> usize {\n"
        "        self.plain.payload_bytes() + self.tau.payload_bytes()\n"
        "    }\n"
        "    fn select(&self, seed_id: usize, exponent: usize, unit_code: usize) -> U256Affine {\n"
        "        assert!(exponent < 2);\n"
        "        if exponent == 0 { self.plain.select(seed_id, unit_code) }\n"
        "        else { self.tau.select(seed_id, unit_code) }\n"
        "    }\n"
        "}\n"
    )
    variant = once(variant, old, replacement)
    variant = once(variant,
        "windows: Vec<Box<[Mixed640AffinePair]>>",
        "windows: Vec<Mixed640SelectiveRow>")
    variant = once(variant,
        "            windows.push(plain.iter().copied().zip(tau.iter().copied())\n"
        "                .map(|(plain, tau)| Mixed640AffinePair {\n"
        "                    plain,\n"
        "                    tau,\n"
        "                }).collect::<Vec<_>>().into_boxed_slice());",
        "            let make_column = |points: Box<[U256Affine]>, compressed: bool| {\n"
        "                if compressed {\n"
        "                    Mixed640Column::Orbit(points.iter().copied()\n"
        "                        .map(U256TwoXAffine::from_affine)\n"
        "                        .collect::<Vec<_>>().into_boxed_slice())\n"
        "                } else { Mixed640Column::Affine(points) }\n"
        "            };\n"
        "            windows.push(Mixed640SelectiveRow {\n"
        "                plain: make_column(plain, MIXED640_COMPRESSED[index][0]),\n"
        "                tau: make_column(tau, MIXED640_COMPRESSED[index][1]),\n"
        "            });")
    variant = once(variant,
        "assert_eq!(size_of::<Mixed640AffinePair>(), 128);",
        "assert_eq!(size_of::<U256Affine>(), 64);\n"
        "        assert_eq!(size_of::<U256TwoXAffine>(), 96);")
    variant = once(variant,
        "let retained_bytes = entries * size_of::<Mixed640AffinePair>()",
        "let retained_bytes = windows.iter().map(|row| row.payload_bytes()).sum::<usize>()")
    variant = once(variant,
        "windows.capacity() * size_of::<Box<[Mixed640AffinePair]>>();",
        "windows.capacity() * size_of::<Mixed640SelectiveRow>();\n"
        "        assert!(retained_bytes <= 64 * 1024 * 1024);")
    variant = once(variant,
        "tables.windows[index][seed_id].select(exponent, unit_code)",
        "tables.windows[index].select(seed_id, exponent, unit_code)")
    variant = variant.replace("mixed640_affine128_retained_bytes",
                              "mixed640_selective64_retained_bytes")
    source.write_text(before + marker + variant)
    receipt = {
        "schema": 1,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy_sha256": sha256(policy_path.read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(source.read_bytes()).hexdigest(),
        "predicted_point_and_atlas_bytes": policy["point_and_atlas_bytes"],
        "retained_table_cap_bytes": policy["retained_table_cap_bytes"],
    }
    (target / "native-selective64-overlay.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]).resolve())
