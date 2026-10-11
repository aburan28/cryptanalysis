"""GPU integration: report replay, restart, exact resume, backend rejection, guard.

Run with a CUDA binary: python3 codegen/testpackedclient.py ./ecc2k130
"""
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

from benchreport import reportsVerified

HEADER = struct.Struct('<8s6IQ')


def run(binary, args, expected=0):
    result = subprocess.run([str(binary)] + args, capture_output=True, text=True, timeout=240)
    if result.returncode != expected or 'MISMATCH' in result.stdout:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout + result.stderr


def main():
    binary = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        cp, corpus = root/'reports.ck', root/'reports.bin'
        args = ['--packed','--curve','131','--threads','128','--steps','32','--launches','2',
                '--dp-weight','50','--verify','4096','--checkpoint',str(cp),'--dp-file',str(corpus)]
        for _ in range(2):
            output = run(binary,args)
            assert reportsVerified(0,output), output
        records = corpus.read_bytes()
        assert len(records)%32 == 0
        assert any(struct.unpack_from('<Q',records,i)[0]&0xffff for i in range(0,len(records),32)), 'no restarted seeds reported'
        print('PASS: DP replay across launch boundaries, restart and checkpoint resume',flush=True)

        a,b = root/'split.ck',root/'whole.ck'
        common=['--packed','--curve','131','--bench','--threads','8','--steps','16','--verify','0']
        run(binary,common+['--launches','2','--checkpoint',str(a)])
        resumed=run(binary,common+['--launches','2','--checkpoint',str(a)])
        run(binary,common+['--launches','4','--checkpoint',str(b)])
        assert a.read_bytes()==b.read_bytes(), 'resumed state differs from uninterrupted execution'
        head=HEADER.unpack_from(a.read_bytes())
        assert head[1]==2 and head[5]==1
        expected=8*head[4]*32
        assert int(re.search(r'M it/s\s+(\d+) iterations',resumed).group(1))==expected
        before=hashlib.sha256(a.read_bytes()).digest()
        run(binary,[x for x in common if x!='--packed']+['--launches','1','--checkpoint',str(a)],expected=6)
        assert hashlib.sha256(a.read_bytes()).digest()==before
        print('PASS: byte-identical resume, scalar iteration count, incompatible checkpoint preserved',flush=True)

        guard=root/'guard.ck'
        run(binary,['--packed','--curve','131','--threads','1','--steps','4096','--launches','2',
                    '--dp-weight','0','--max-iters','1','--verify','16','--checkpoint',str(guard)])
        data=guard.read_bytes();head=HEADER.unpack_from(data);n=head[3]*head[4]
        seedOffset=HEADER.size+n*44
        seeds=struct.unpack_from('<'+'Q'*n,data,seedOffset)
        starts=struct.unpack_from('<'+'Q'*n,data,seedOffset+8*n)
        assert all(seed&0xffff==1 for seed in seeds),seeds
        assert all(start==8192 for start in starts),starts
        print('PASS: overdue walks restart without false distinguished-point reports',flush=True)


if __name__=='__main__':
    main()
