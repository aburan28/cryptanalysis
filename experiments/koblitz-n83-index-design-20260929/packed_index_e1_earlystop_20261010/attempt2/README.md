# Second local panel interruption

Rows 1–3 completed under the frozen protocol. During row 4, the native
binary printed a completion line, but the runner raised `OSError: [Errno 28]
No space left on device` when writing the stdout receipt to the macOS
filesystem. No row-4 JSON result or run record was retained. The native
stdout is preserved here. The isolated checkout was moved to SSD scratch,
and rows 4–6 were replayed there using the same binary, source digest,
protocol, workload, and arm order. The final six-row summary records the
successful rows 1–3 and the completed SSD replay rows 4–6. These local
timings remain exploratory.
