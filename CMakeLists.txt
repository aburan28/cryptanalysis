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
option(CA_SANITIZE "Enable ASan/UBSan" OFF)
option(CA_WERROR "Treat warnings as errors" OFF)

find_package(Threads REQUIRED)

set(CA_SOURCES
  src/modarith.c
  src/util.c
  src/group_common.c
  src/group_zp.c
  src/group_ec.c
  src/bsgs.c
  src/rho.c
  src/kangaroo.c
  src/grumpy.c
  src/pohlig.c
  src/cheon.c
  src/linalg.c
  src/indexcalc.c
  src/ffi.c
)

set(CA_WARNINGS -Wall -Wextra -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes
                -Wmissing-prototypes -Wno-unused-function)
if(CA_WERROR)
  list(APPEND CA_WARNINGS -Werror)
endif()

function(ca_configure_target tgt)
  target_include_directories(${tgt} PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
  target_include_directories(${tgt} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_compile_options(${tgt} PRIVATE ${CA_WARNINGS})
  target_compile_definitions(${tgt} PRIVATE CA_BUILDING _GNU_SOURCE)
  target_link_libraries(${tgt} PUBLIC Threads::Threads m)
  if(CA_NATIVE)
    target_compile_options(${tgt} PRIVATE -march=native)
  endif()
  if(CA_SANITIZE)
    target_compile_options(${tgt} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${tgt} PRIVATE -fsanitize=address,undefined)
  endif()
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
  target_include_directories(ca PRIVATE src)
  target_compile_options(ca PRIVATE ${CA_WARNINGS})
  if(CA_SANITIZE)
    target_compile_options(ca PRIVATE -fsanitize=address,undefined)
    target_link_options(ca PRIVATE -fsanitize=address,undefined)
  endif()
  add_executable(ca_bench tools/ca_bench.c)
  target_link_libraries(ca_bench PRIVATE ${CA_LINK_TARGET})
  target_include_directories(ca_bench PRIVATE src)
  target_compile_options(ca_bench PRIVATE ${CA_WARNINGS})
  if(CA_SANITIZE)
    target_compile_options(ca_bench PRIVATE -fsanitize=address,undefined)
    target_link_options(ca_bench PRIVATE -fsanitize=address,undefined)
  endif()
endif()

if(CA_BUILD_TESTS)
  enable_testing()
  set(CA_TESTS modarith group bsgs rho kangaroo grumpy pohlig cheon linalg indexcalc ffi)
  foreach(t ${CA_TESTS})
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_${t}.c)
      add_executable(test_${t} tests/test_${t}.c)
      target_link_libraries(test_${t} PRIVATE ${CA_LINK_TARGET})
      target_include_directories(test_${t} PRIVATE src tests)
      target_compile_options(test_${t} PRIVATE ${CA_WARNINGS} -Wno-missing-prototypes)
      if(CA_SANITIZE)
        target_compile_options(test_${t} PRIVATE -fsanitize=address,undefined)
        target_link_options(test_${t} PRIVATE -fsanitize=address,undefined)
      endif()
      add_test(NAME ${t} COMMAND test_${t})
    endif()
  endforeach()
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
configure_file(cmake/cryptanalysis.pc.in ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysis.pc @ONLY)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/cryptanalysis.pc
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)
