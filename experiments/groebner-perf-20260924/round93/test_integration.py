"""Exercise all existing Macaulay integration controls with the new schedule."""
import importlib.util
from query import HERE,Query
spec=importlib.util.spec_from_file_location('old_matrix_controls',HERE.parent/'round92/test_macaulay.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

class ScheduledMatrixTests(old.MatrixTests):
    @classmethod
    def setUpClass(cls):
        cls.queries=[Query(checker_order='completion-first'),Query(sanitizer=True,checker_order='completion-first')]
