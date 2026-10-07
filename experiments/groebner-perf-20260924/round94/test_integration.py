import importlib.util
from query import HERE,Query
spec=importlib.util.spec_from_file_location('matrix92_for94_controls',HERE.parent/'round92/test_macaulay.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

class LiveMatrixTests(old.MatrixTests):
    @classmethod
    def setUpClass(cls):
        cls.queries=[Query(sanitizer=s,checker_order='completion-first',retention=p)
            for s in (False,True) for p in ('release-cumulative','release-live')]
