cmake_minimum_required(VERSION 3.16)
project(cryptanalysis VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)   # __int128, clock_gettime
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

option(CA_BUILD_SHARED "Build the shared library" ON)
option(CA_BUILD_STATIC "Build the static library" ON)
option(CA_BUILD_TOOLS "Build the ca CLI and benchmark" ON)
option(CA_BUILD_TESTS "Build the C test-suite" ON)
option(CA_NATIVE "Compile with -march=native" OFF)
# OFF, ON (= address,undefined), or an explicit -fsanitize= list such as
# "thread" or "memory".  ON is kept so existing invocations keep working.
set(CA_SANITIZE OFF CACHE STRING "Sanitizers: OFF, ON (address,undefined), or a -fsanitize= list")
option(CA_WERROR "Treat warnings as errors" OFF)
option(CA_CUDA "Build the CUDA backend for the GPU solvers (needs nvcc or clang with CUDA)" OFF)
option(CA_FUZZ "Build the libFuzzer harnesses in fuzz/ (needs clang)" OFF)
set(CA_CUDA_ARCHITECTURES "70;80;89;90" CACHE STRING "CUDA architectures for CA_CUDA")

find_package(Threads REQUIRED)

set(CA_SANITIZE_FLAGS "")
if(CA_SANITIZE)
  if(CA_SANITIZE MATCHES "^(ON|on|ON|TRUE|true|YES|yes|1)$")
    set(CA_SANITIZE_LIST "address,undefined")
  else()
    set(CA_SANITIZE_LIST "${CA_SANITIZE}")
  endif()
  set(CA_SANITIZE_FLAGS -fsanitize=${CA_SANITIZE_LIST} -fno-omit-frame-pointer -g)
  message(STATUS "cryptanalysis: sanitizers ${CA_SANITIZE_LIST}")
endif()

# Apply the selected sanitizers to one target.  Every executable needs them,
# not just the library: linking a sanitized library into an unsanitized binary
# leaves the runtime's own symbols undefined.
function(ca_sanitize tgt)
  if(CA_SANITIZE_FLAGS)
    target_compile_options(${tgt} PRIVATE ${CA_SANITIZE_FLAGS})
    target_link_options(${tgt} PRIVATE ${CA_SANITIZE_FLAGS})
  endif()
endfunction()

set(CA_SOURCES
  src/modarith.c
  src/util.c
  src/group_common.c
  src/group_zp.c
  src/group_ec.c
  src/bsgs.c
  src/rho.c
  src/dist.c
  src/kangaroo.c
  src/grumpy.c
  src/pohlig.c
  src/cheon.c
  src/linalg.c
  src/indexcalc.c
  src/ffi.c
  src/gpu_rho.c
  src/gpu_emulate.c
)

set(CA_WARNINGS -Wall -Wextra -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes
                -Wmissing-prototypes -Wno-unused-function)
if(CA_WERROR)
  list(APPEND CA_WARNINGS -Werror)
endif()

if(CA_CUDA)
  enable_language(CUDA)
  set(CMAKE_CUDA_STANDARD 17)
  set(CMAKE_CUDA_ARCHITECTURES ${CA_CUDA_ARCHITECTURES})
  find_package(CUDAToolkit REQUIRED)
  list(APPEND CA_SOURCES cuda/rho_kernel.cu cuda/gpu_cuda.c)
else()
  list(APPEND CA_SOURCES src/gpu_cuda_stub.c)
endif()

function(ca_configure_target tgt)
  target_include_directories(${tgt} PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
  target_include_directories(${tgt} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src ${CMAKE_CURRENT_SOURCE_DIR}/cuda)
  if(CA_CUDA)
    target_compile_definitions(${tgt} PRIVATE CA_HAVE_CUDA=1)
    target_link_libraries(${tgt} PUBLIC CUDA::cudart)
    set_target_properties(${tgt} PROPERTIES CUDA_SEPARABLE_COMPILATION OFF)
  endif()
  target_compile_options(${tgt} PRIVATE $<$<COMPILE_LANGUAGE:C>:${CA_WARNINGS}>)
  target_compile_definitions(${tgt} PRIVATE CA_BUILDING _GNU_SOURCE)
  target_link_libraries(${tgt} PUBLIC Threads::Threads m)
  if(CA_NATIVE)
    target_compile_options(${tgt} PRIVATE -march=native)
  endif()
  ca_sanitize(${tgt})
  set_target_properties(${tgt} PROPERTIES C_VISIBILITY_PRESET hidden
                                          OUTPUT_NAME cryptanalysis)
endfunction()

set(CA_PRIMARY_TARGET "")
if(CA_BUILD_SHARED)
  add_library(cryptanalysis SHARED ${CA_SOURCES})
  ca_configure_target(cryptanalysis)
  target_compile_definitions(cryptanalysis PUBLIC CA_SHARED)
  set_target_properties(cryptanalysis PROPERTIES VERSION ${PROJECT_VERSION}
                                                 SOVERSION ${PROJECT_VERSION_MAJOR})
  set(CA_PRIMARY_TARGET cryptanalysis)
endif()
if(CA_BUILD_STATIC)
  add_library(cryptanalysis_static STATIC ${CA_SOURCES})
  ca_configure_target(cryptanalysis_static)
  set_target_properties(cryptanalysis_static PROPERTIES POSITION_INDEPENDENT_CODE ON)
  if(NOT CA_PRIMARY_TARGET)
    set(CA_PRIMARY_TARGET cryptanalysis_static)
  endif()
endif()
if(NOT CA_PRIMARY_TARGET)
  message(FATAL_ERROR "Enable at least one of CA_BUILD_SHARED / CA_BUILD_STATIC")
endif()

# Tools and tests link the static library when available (simpler rpath story).
if(CA_BUILD_STATIC)
  set(CA_LINK_TARGET cryptanalysis_static)
else()
  set(CA_LINK_TARGET cryptanalysis)
endif()

if(CA_BUILD_TOOLS)
  add_executable(ca tools/ca_cli.c)
  target_link_libraries(ca PRIVATE ${CA_LINK_TARGET})
  target_include_directories(ca PRIVATE src cuda)
  target_compile_options(ca PRIVATE ${CA_WARNINGS})
  ca_sanitize(ca)
  add_executable(ca_bench tools/ca_bench.c)
  target_link_libraries(ca_bench PRIVATE ${CA_LINK_TARGET})
  target_include_directories(ca_bench PRIVATE src cuda)
  target_compile_options(ca_bench PRIVATE ${CA_WARNINGS})
  ca_sanitize(ca_bench)
endif()

if(CA_BUILD_TESTS)
  enable_testing()
  set(CA_TESTS modarith group bsgs rho dist kangaroo grumpy pohlig cheon linalg indexcalc ffi gpu)
  foreach(t ${CA_TESTS})
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_${t}.c)
      add_executable(test_${t} tests/test_${t}.c)
      target_link_libraries(test_${t} PRIVATE ${CA_LINK_TARGET})
      target_include_directories(test_${t} PRIVATE src tests cuda)
      target_compile_options(test_${t} PRIVATE ${CA_WARNINGS} -Wno-missing-prototypes)
      ca_sanitize(test_${t})
      add_test(NAME ${t} COMMAND test_${t})
    endif()
  endforeach()
endif()

# ---- fuzzing ---------------------------------------------------------------
# One libFuzzer binary per fuzz/*.c, so a new harness needs no CMake edit.
if(CA_FUZZ)
  if(NOT CMAKE_C_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR "CA_FUZZ needs clang (libFuzzer); set CC=clang")
  endif()
  file(GLOB CA_FUZZ_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/fuzz/*.c)
  foreach(fz ${CA_FUZZ_SOURCES})
    get_filename_component(fz_name ${fz} NAME_WE)
    add_executable(${fz_name} ${fz})
    target_link_libraries(${fz_name} PRIVATE ${CA_LINK_TARGET})
    target_include_directories(${fz_name} PRIVATE src cuda)
    target_compile_options(${fz_name} PRIVATE ${CA_WARNINGS}
                           -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer)
    target_link_options(${fz_name} PRIVATE -fsanitize=fuzzer,address,undefined)
  endforeach()
  list(LENGTH CA_FUZZ_SOURCES CA_FUZZ_COUNT)
  message(STATUS "cryptanalysis: ${CA_FUZZ_COUNT} fuzz harness(es)")
endif()

# ---- install ---------------------------------------------------------------
include(GNUInstallDirs)
install(DIRECTORY include/cryptanalysis DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
if(CA_BUILD_SHARED)
  install(TARGETS cryptanalysis EXPORT cryptanalysisTargets
          LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
          ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
          RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()
if(CA_BUILD_STATIC)
  install(TARGETS cryptanalysis_static EXPORT cryptanalysisTargets
          ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
endif()
if(CA_BUILD_TOOLS)
  install(TARGETS ca RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()
# The .pc file locates the install tree relative to itself, so that
# `cmake --install --prefix DIR` is correct even when DIR differs from the
# prefix used at configure time.  That only works when the directories are
# relative to the prefix, which is the GNUInstallDirs default; an absolute
# libdir or includedir is emitted as the absolute path it is.
if(IS_ABSOLUTE "${CMAKE_INSTALL_LIBDIR}")
  set(CA_PC_PREFIX "${CMAKE_INSTALL_PREFIX}")
  set(CA_PC_LIBDIR "${CMAKE_INSTALL_LIBDIR}")
else()
  file(RELATIVE_PATH CA_PC_REL_PREFIX
       "${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR}/pkgconfig" "${CMAKE_INSTALL_PREFIX}")
  string(REGEX REPLACE "/+$" "" CA_PC_REL_PREFIX "${CA_PC_REL_PREFIX}")
  set(CA_PC_PREFIX "\${pcfiledir}/${CA_PC_REL_PREFIX}")
  set(CA_PC_LIBDIR "\${prefix}/${CMAKE_INSTALL_LIBDIR}")
endif()
if(IS_ABSOLUTE "${CMAKE_INSTALL_INCLUDEDIR}")
  set(CA_PC_INCLUDEDIR "${CMAKE_INSTALL_INCLUDEDIR}")
else()
  set(CA_PC_INCLUDEDIR "\${prefix}/${CMAKE_INSTALL_INCLUDEDIR}")
endif()
configure_file(cmake/cryptanalysis.pc.in ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysis.pc @ONLY)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysis.pc
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)

# The CMake package, so that consumers can find_package(cryptanalysis).  The
# targets above join the export set; without installing it they would be
# exported nowhere and only pkg-config would work.
include(CMakePackageConfigHelpers)
write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysisConfigVersion.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion)
configure_package_config_file(
  cmake/cryptanalysisConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysisConfig.cmake
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/cryptanalysis)
install(EXPORT cryptanalysisTargets
        FILE cryptanalysisTargets.cmake
        NAMESPACE cryptanalysis::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/cryptanalysis)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysisConfig.cmake
              ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysisConfigVersion.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/cryptanalysis)
