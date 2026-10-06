class KernelTransformStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('logical_xors', 'encoded_dispatches', 'submitted_dispatches',
        'completed_dispatches', 'dispatched_threads', 'input_bytes', 'output_bytes', 'scratch_bytes')]
    _fields_ += [(name, ct.c_double) for name in ('copy_in', 'encode', 'wait', 'copy_out', 'device', 'wall')]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class ProducerTransformStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('requested_mode', 'executed_mode', 'generation',
        'projection_reused_bytes', 'projection_uploaded_bytes', 'additional_table_bytes')]
    _fields_ += [('kernel', KernelTransformStats)]

    def record(self):
        return {name: getattr(self, name).record() if name == 'kernel' else getattr(self, name)
                for name, _ in self._fields_}
