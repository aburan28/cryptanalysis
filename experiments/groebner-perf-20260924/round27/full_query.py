"""Complete two-block query with unchanged descent and signed curve replay."""
from pathlib import Path
import sys
import time

from conditional import Basis

HERE = Path(__file__).resolve().parent
_path = sys.path[:]
try:
    sys.path.insert(0,str(HERE.parent/'round23'))
    from sparse_checker import SparseQuery, TruthQuery
    from packed_checker import PublicInstance
finally:
    sys.path[:] = _path


class ConditionalQuery(TruthQuery):
    def __init__(self,n,mod,b,m,ell,*,sanitizer=False):
        if m!=2:
            raise ValueError('conditional query requires exactly two coordinate blocks')
        super().__init__(n,mod,b,m,ell,arm='combined',sanitizer=sanitizer)
        try:
            self.basis.close()
            self.checker.close()
            self.basis = Basis(ell,ell,n,sanitizer=sanitizer)
            self.checker = self.basis.checker
        except Exception:
            self.close()
            raise

    def solve(self,target):
        return complete_query(self,target,'conditional-linear')


class BaselineQuery(SparseQuery):
    def solve(self,target):
        return complete_query(self,target,'sparse')


def complete_query(query,target,arm):
    """Same complete boundary in both arms; retain basis terms for offline audit."""
    with query._lock:
        if query._closed:
            raise RuntimeError('query is closed')
        start=time.perf_counter_ns()
        query.replay.validate_target(target)
        if target.inf:
            raise ValueError('finite target required')
        validated=time.perf_counter_ns()
        anf=query.descent.descend_packed(target.x)
        descended=time.perf_counter_ns()
        instance=PublicInstance(*query.shape,target,anf)
        answer=query.basis.compute(anf)
        certified=time.perf_counter_ns()
        checked,witness=0,None
        if answer['status']=='gb':
            answer['status']='gb-no-verified-solution'
            for assignment in answer['basis_certificate']['solutions']:
                checked+=1
                if query.checker.evaluate(anf,assignment):
                    raise RuntimeError('certified root fails original equations')
                trial=query.replay.match(instance.x_from_assignment(assignment),target)
                if trial['verified']:
                    if query.checker.evaluate(anf,assignment):
                        raise RuntimeError('witness fails original equations')
                    witness=trial
                    answer.update(status='solved',verified=True,assignment=assignment)
                    break
        finished=time.perf_counter_ns()
        answer.update(assignments_checked=checked,curve_witness=witness,
            public_target=vars(target),query_arm=arm,complete_query_ns=finished-start,
            replay_backend=query.replay.backend,replay_binary_sha256=query.replay.binary_sha256,
            equation_backend='independent-native-direct-packed',
            equation_binary_sha256=query.checker.binary_sha256,
            descent_binary_sha256=query.descent.binary_sha256,
            phases_ns={'target_validation':validated-start,'descent':descended-validated,
                       'basis_and_certificate':certified-descended,
                       'equation_and_curve_replay':finished-certified})
        return answer
