//! Safe "is this shared library here?" probes.
//!
//! `cudarc`'s `dynamic-loading` backend resolves `libcuda` / `libnvrtc`
//! lazily and **panics** (`panic_no_lib_found`) when none of its candidate
//! names can be loaded.  A panic is the wrong answer for
//! [`device_count()`](crate::device_count) on a machine without a GPU, so
//! every entry point that would touch the driver asks here first.  The names
//! below are a subset of cudarc's own candidate list, so a successful probe
//! implies cudarc will find the library too.

use std::sync::OnceLock;

fn loadable(names: &[&str]) -> bool {
    names.iter().any(|name| {
        // SAFETY: we only load the library and immediately drop it.  Loading
        // libcuda / libnvrtc runs their initialisers, which is exactly what
        // cudarc does a moment later; no symbol is called from here.
        unsafe { libloading::Library::new(name) }.is_ok()
    })
}

/// Whether the CUDA driver library can be loaded on this machine.
pub fn driver_available() -> bool {
    static OK: OnceLock<bool> = OnceLock::new();
    *OK.get_or_init(|| {
        loadable(&[
            "libcuda.so",
            "libcuda.so.1",
            "libcuda.so.12",
            "nvcuda.dll",
            "cuda.dll",
        ])
    })
}

/// Whether the NVRTC runtime-compilation library can be loaded.
pub fn nvrtc_available() -> bool {
    static OK: OnceLock<bool> = OnceLock::new();
    *OK.get_or_init(|| {
        loadable(&[
            "libnvrtc.so",
            "libnvrtc.so.1",
            "libnvrtc.so.11",
            "libnvrtc.so.12",
            "nvrtc64_120_0.dll",
            "nvrtc64_112_0.dll",
        ])
    })
}
