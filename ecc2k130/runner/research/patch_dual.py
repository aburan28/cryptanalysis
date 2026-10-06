"""Substitute two interleaved 16-point chains in the disposable runner."""
from patch_metadata import replace_once


def patch(content):
    content=dict(content)
    path='include/packedkernels.cuh'
    s=replace_once(content[path], '#include "packed131.h"', '#include "packed131.h"\n#include "paired_inverse.h"')
    start=s.index('#if ECC_TABLE_FUSED\n// The forward-pass work')
    marker='#endif  // ECC_TABLE_FUSED'
    end=s.index(marker,start)+len(marker)
    content[path]=s[:start]+'#include "dual_walk.cuh"\n'+s[end:]
    path='include/packedengine.cuh'
    # Reserve 60 KiB to guarantee a single block, while retaining the same
    # 64 KiB carveout used by the baseline (including driver reservation).
    content[path]=replace_once(content[path],
        'static size_t dynamicSharedBytes() { return eccPacked131::TW_SHARED_BYTES; }',
        'static size_t dynamicSharedBytes() { return 60 * 1024; }')
    return content
