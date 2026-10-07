"""Compact packed input for the hash-bound round92 Macaulay producer."""
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent


def source():
    spec = importlib.util.spec_from_file_location('live94_for101', P/'round94/generate.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    return old.source()


def sparse_source():
    path = P/'round92/macaulay.cpp'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == '0465dac78c5ecaf0b834da0e13a11be0aa3b6cff34814ac63d3d26a2e66595b1'
    text = path.read_text()
    replacements = {
        'in.terms != (l.equations ? support : 0)':
            'in.terms > (l.equations ? support : 0)',
        '        std::vector<std::vector<uint32_t>> inputs(in.equations);\n        charge(in.equations);':
            '''        // Both vectors are query-local. No coefficients or pivot choices survive.
        charge(in.equations);
        std::vector<std::vector<uint32_t>> inputs(in.equations);
        charge(support);
        std::vector<uint8_t> seen(support, 0);''',
        '            if (in.masks[i] != l.support[i]) throw Invalid("support order mismatch");':
            '''            const uint64_t mask = in.masks[i];
            size_t lo = 0, hi = support;
            while (lo < hi) {
                charge(); // One immutable-support comparison.
                const size_t middle = lo + (hi - lo) / 2;
                if (l.support[middle] < mask)
                    lo = middle + 1;
                else
                    hi = middle;
            }
            charge(); // Membership and duplicate validation.
            if (lo == support || l.support[lo] != mask)
                throw Invalid("mask outside support envelope");
            if (seen[lo]) throw Invalid("duplicate packed mask");
            seen[lo] = 1;''',
        'inputs[k * 64 + __builtin_ctzll(bits)].push_back(uint32_t(i));':
            'inputs[k * 64 + __builtin_ctzll(bits)].push_back(uint32_t(lo));',
    }
    for old, new in replacements.items():
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text
