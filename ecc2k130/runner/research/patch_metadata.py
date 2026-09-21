"""Apply compact-metadata experiment to the disposable source copy only."""
from pathlib import Path
import re


def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def patch(content):
    content = dict(content)
    path = 'include/packedkernels.cuh'
    s = content[path]
    s = replace_once(s, '#include "packed131.h"', '#include "packed131.h"\n#include "compact_metadata.cuh"')
    s = re.sub(r'p\.dead\[([^\]]+)\] = ([01]);', r'goal22WriteDead(p.dead, \1, \2);', s)
    s = re.sub(r'p\.dead\[([^\]]+)\]', r'goal22ReadDead(p.dead, \1)', s)
    s = re.sub(r'p\.hist\[([^\]]+)\] = ([^;]+);', r'goal22WriteHist(p.hist, \1, size_t(p.threads)*ECC_BATCH, \2);', s)
    s = re.sub(r'p\.hist\[([^\]]+)\]', r'goal22ReadHist(p.hist, \1, size_t(p.threads)*ECC_BATCH)', s)
    old = 'const unsigned tag = twSelect(x, yp, hw, p.hist + id, twSel);'
    assert s.count(old) == 2
    s = s.replace(old, '''unsigned long long compactHist = goal22ReadHist(p.hist, id, size_t(p.threads)*ECC_BATCH);
    const unsigned tag = twSelectHist(x, yp, hw, &compactHist, twSel);
    goal22WriteHist(p.hist, id, size_t(p.threads)*ECC_BATCH, compactHist);''')
    assert 'p.dead[' not in s and 'p.hist[' not in s and 'p.hist + id' not in s
    content[path] = s
    path = 'include/packedengine.cuh'
    s = replace_once(content[path], '    size_t fieldCount() const override',
                     '#include "metadata_checkpoint.inc"\n    size_t fieldCount() const override')
    s = replace_once(s, 'CUDA_CHECK(cudaMalloc(&P.dead, slotCount() * sizeof(unsigned)));',
        '''CUDA_CHECK(cudaMalloc(&P.dead, eccPacked131::goal22DeadBytes(slotCount())));
        CUDA_CHECK(cudaMemset(P.dead, 0, eccPacked131::goal22DeadBytes(slotCount())));''')
    s = replace_once(s, 'CUDA_CHECK(cudaMalloc(&P.hist, laneCount() * sizeof(u64)));',
        'CUDA_CHECK(cudaMalloc(&P.hist, eccPacked131::goal22HistoryBytes(laneCount())));')
    content[path] = s
    path = 'src/main.cu'
    s = content[path]
    pairs = [
        ('CUDA_CHECK(cudaMemcpy(sbuf.data(), P.dead, sbuf.size() * sizeof(W), cudaMemcpyDeviceToHost));',
         'readCheckpointDead(sbuf);'),
        ('CUDA_CHECK(cudaMemcpy(P.dead, sbuf.data(), sbuf.size() * sizeof(W), cudaMemcpyHostToDevice));',
         'writeCheckpointDead(sbuf);'),
        ('CUDA_CHECK(cudaMemcpy(lbuf.data(), laneArray(i), lbuf.size() * sizeof(u64), cudaMemcpyDeviceToHost));',
         'readCheckpointLane(i, lbuf);'),
        ('CUDA_CHECK(cudaMemcpy(laneArray(i), lbuf.data(), lbuf.size() * sizeof(u64), cudaMemcpyHostToDevice));',
         'writeCheckpointLane(i, lbuf);'),
    ]
    for old, new in pairs:
        s = replace_once(s, old, new)
    marker = '    virtual u64 *laneArray(int i) const { return i ? P.startIter : P.seed; }'
    s = replace_once(s, marker, marker + '''
    virtual void readCheckpointDead(std::vector<W> &v) const {
        CUDA_CHECK(cudaMemcpy(v.data(), P.dead, v.size()*sizeof(W), cudaMemcpyDeviceToHost));
    }
    virtual void writeCheckpointDead(const std::vector<W> &v) {
        CUDA_CHECK(cudaMemcpy(P.dead, v.data(), v.size()*sizeof(W), cudaMemcpyHostToDevice));
    }
    virtual void readCheckpointLane(int i, std::vector<u64> &v) const {
        CUDA_CHECK(cudaMemcpy(v.data(), laneArray(i), v.size()*sizeof(u64), cudaMemcpyDeviceToHost));
    }
    virtual void writeCheckpointLane(int i, const std::vector<u64> &v) {
        CUDA_CHECK(cudaMemcpy(laneArray(i), v.data(), v.size()*sizeof(u64), cudaMemcpyHostToDevice));
    }
''')
    content[path] = s
    return content
