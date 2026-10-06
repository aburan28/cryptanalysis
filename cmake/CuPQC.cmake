# cuPQC is an optional, separately installed SDK. No configure-time downloads.
if(CMAKE_VERSION VERSION_LESS 3.24)
  message(FATAL_ERROR "CA_CUPQC requires CMake 3.24 or newer for CUDA device LTO")
endif()
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "CA_CUPQC requires a Linux CUDA build host; disable CA_CUPQC on this host")
endif()

set(CA_CUPQC_ROOT "" CACHE PATH "Extracted NVIDIA cuPQC SDK directory")
set(CA_CUPQC_MLKEM_SOURCE "" CACHE FILEPATH "NVIDIA example_ml_kem.cu from the SDK or cuPQC examples checkout")
set(CA_CUPQC_ARCHITECTURES "80" CACHE STRING "CUDA architectures for the cuPQC example (match the GPU and SDK)")
if(NOT CA_CUPQC_MLKEM_SOURCE AND EXISTS "${CA_CUPQC_ROOT}/examples/public_key/example_ml_kem.cu")
  set(CA_CUPQC_MLKEM_SOURCE "${CA_CUPQC_ROOT}/examples/public_key/example_ml_kem.cu")
endif()
if(NOT EXISTS "${CA_CUPQC_MLKEM_SOURCE}" OR IS_DIRECTORY "${CA_CUPQC_MLKEM_SOURCE}")
  message(FATAL_ERROR "Set CA_CUPQC_MLKEM_SOURCE to NVIDIA's example_ml_kem.cu; see docs/CUPQC.md")
endif()

enable_language(CUDA)
if(NOT CMAKE_CUDA_COMPILER_ID STREQUAL "NVIDIA")
  message(FATAL_ERROR "CA_CUPQC requires NVIDIA nvcc for device LTO")
endif()
find_package(CUDAToolkit REQUIRED)
find_package(cupqc CONFIG REQUIRED HINTS "${CA_CUPQC_ROOT}/cmake")
if(NOT TARGET cupqc-pk_static)
  message(FATAL_ERROR "The cuPQC package must export cupqc-pk_static; see docs/CUPQC.md")
endif()

add_executable(ca_cupqc_mlkem "${CA_CUPQC_MLKEM_SOURCE}")
target_link_libraries(ca_cupqc_mlkem PRIVATE cupqc-pk_static CUDA::cudart)
set_target_properties(ca_cupqc_mlkem PROPERTIES
  CUDA_STANDARD 17 CUDA_STANDARD_REQUIRED ON
  CUDA_ARCHITECTURES "${CA_CUPQC_ARCHITECTURES}"
  CUDA_SEPARABLE_COMPILATION ON
  INTERPROCEDURAL_OPTIMIZATION TRUE)
# This is NVIDIA's demonstration program, not a registered correctness test.
