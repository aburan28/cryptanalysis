"""Minimal-output back substitution over the unchanged sparse Macaulay input."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('generator105_for106', P/'round105/generate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
source, sparse_source, dense_source, reuse_source, normal_source = (
    previous.source, previous.sparse_source, previous.dense_source,
    previous.reuse_source, previous.normal_source)


def minimal_source():
    text = sparse_source()
    start = text.index('        for (size_t i = pivot_columns.size(); i-- > 0;) {')
    end = text.index('        finish();', start)
    text = text[:start]+(HERE/'minimal_backsub.inc').read_text()+text[end:]
    start = text.index('        Masks minimal;', text.index('auto result ='))
    end = text.index('            const auto &row = pivots[slots[c]];', start)
    text = text[:start]+'''        // Preserve the reference output order and extraction.
        for (size_t c = l.columns.size(); c-- > 0;) {
            if (!selected[c]) continue;
'''+text[end:]
    return text


if __name__ == '__main__':
    print(minimal_source())
