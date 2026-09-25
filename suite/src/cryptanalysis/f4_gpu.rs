//! # Batched Boolean Macaulay decisions on a GPU.
//!
//! The device kernel is `suite/cuda/f4_gf2_device.cuh`: one thread block
//! decides one system — builds its Macaulay matrix over the occurring
//! variables with a rank bitmap and prefix counts, applies the size caps in
//! the reference builder's units, eliminates the high-degree columns by
//! leading-column pivoting, and reduces the linear block — exactly the
//! algorithm of [`f4_gf2::decide`].  The matrices of the splitting search
//! are small (a few hundred rows), so a launch pays only when it carries
//! thousands of them; [`super::f4_batch::solve_lockstep`] supplies them by
//! running a batch of searches in lockstep.
//!
//! Three [`BatchDecider`]s answer the same batches:
//!
//! - [`super::f4_batch::CpuDecider`], the host kernel;
//! - `EmulatorDecider` (feature `gpu-emulator`), the **device source**
//!   compiled as C and run on the host one emulated block at a time — how
//!   the kernel is tested on machines without a GPU;
//! - [`CudaDecider`], the kernel on an NVIDIA device through the CUDA driver
//!   API.  `libcuda` and NVRTC are opened at run time, so the crate builds
//!   and links everywhere and nothing here runs unless it is asked for.
//!   The source is compiled by NVRTC for the device found (or loaded as PTX
//!   from `CA_F4_PTX`).
//!
//! A system the kernel cannot hold — degree above 7, more than 256
//! equations, or more scratch than a block was given — comes back as
//! `F4_STATUS_FALLBACK` and is decided on the host, so every backend
//! answers every request.

use super::f4_batch::{BatchDecider, CpuDecider, DecisionRequest};
use super::f4_gf2::{self, Decision, KernelCounters, MacaulayCaps};

/// Result of one system; mirrors `F4Result` in `cuda/f4_gf2_device.cuh`.
#[repr(C)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct F4Result {
    /// One of the `STATUS_*` codes.
    pub status: u32,
    /// The ideal contains `1`.
    pub refuted: u32,
    /// Variables pinned by a row `v` or `v + 1`.
    pub forced_mask: u64,
    /// Their values: bit set for `v + 1`, i.e. `v = 1`.
    pub forced_vals: u64,
    /// Rows in reference units.
    pub ref_rows: u64,
    /// Columns in reference units.
    pub ref_cols: u64,
    /// 64-bit word XORs the kernel performed.
    pub word_ops: u64,
    /// Rows eliminated.
    pub rows: u32,
    /// Columns eliminated.
    pub cols: u32,
}

/// Decided; the decision is in the result.
pub const STATUS_DECIDED: u32 = 0;
/// Over the caps, in reference units.
pub const STATUS_OVERSIZE: u32 = 1;
/// A matrix with no nonempty row.
pub const STATUS_EMPTY: u32 = 2;
/// No equations: nothing built.
pub const STATUS_NO_POLYS: u32 = 3;
/// Beyond the kernel's limits: decide on the host.
pub const STATUS_FALLBACK: u32 = 4;

/// Highest Macaulay degree the kernel handles (`F4_DMAX`).
pub const KERNEL_MAX_DEGREE: u32 = 7;
/// Most equations per system the kernel handles (`F4_MAX_POLYS`).
pub const KERNEL_MAX_POLYS: usize = 256;

/// The kernel as NVRTC compiles it: the device header, then the entry
/// point.
pub fn kernel_source() -> String {
    format!(
        "{}\n{}",
        include_str!("../../cuda/f4_gf2_device.cuh"),
        include_str!("../../cuda/f4_gf2_kernel.cu")
    )
}

/// A batch in the kernel's input layout.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct PackedBatch {
    /// Every term of every equation, as a monomial mask.
    pub terms: Vec<u64>,
    /// Start of each equation in `terms`, plus one end offset.
    pub poly_start: Vec<u32>,
    /// Start of each system in the equation list, plus one end offset.
    pub sys_poly_start: Vec<u32>,
    /// `n_vars | degree << 8` per system.
    pub sys_meta: Vec<u32>,
    /// Scratch words the most demanding system needs (an upper bound).
    pub scratch_words: u64,
}

impl PackedBatch {
    /// Pack `requests`, dropping zero equations (they build no rows).
    pub fn pack(requests: &[DecisionRequest<'_>]) -> Self {
        let mut b = PackedBatch::default();
        b.sys_poly_start.push(0);
        b.poly_start.push(0);
        for r in requests {
            for p in r.polys.iter().filter(|p| !p.is_zero()) {
                b.terms.extend(p.terms.iter().map(|t| t.mask));
                b.poly_start.push(b.terms.len() as u32);
            }
            b.sys_poly_start.push((b.poly_start.len() - 1) as u32);
            b.sys_meta
                .push((r.n_vars.min(255) as u32) | (r.degree.min(255) << 8));
            b.scratch_words = b.scratch_words.max(scratch_bound(r));
        }
        b
    }

    /// Systems in the batch.
    pub fn len(&self) -> usize {
        self.sys_meta.len()
    }

    /// Whether the batch holds no system.
    pub fn is_empty(&self) -> bool {
        self.sys_meta.is_empty()
    }
}

/// Scratch words the kernel's layout needs for `r`, from the shape of its
/// rank space and candidate rows — an upper bound, since cancellation only
/// removes columns.
pub fn scratch_bound(r: &DecisionRequest<'_>) -> u64 {
    let d = r.degree;
    let mut occ = 0u64;
    let mut ks = Vec::new();
    let mut max_terms = 0u64;
    for p in r.polys.iter().filter(|p| !p.is_zero()) {
        let pdeg = p
            .terms
            .iter()
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap_or(0);
        if pdeg > d {
            continue;
        }
        occ |= p.terms.iter().fold(0, |a, t| a | t.mask);
        ks.push((d - pdeg) as usize);
        max_terms = max_terms.max(p.terms.len() as u64);
    }
    let v = occ.count_ones() as u64;
    let binom = |n: u64, k: u64| -> u64 {
        if k > n {
            return 0;
        }
        (1..=k).fold(1u64, |c, i| c.saturating_mul(n - k + i) / i)
    };
    let upto = |k: u64| (0..=k.min(v)).fold(0u64, |a, j| a.saturating_add(binom(v, j)));
    let rank_space = upto(u64::from(d));
    let n_cand = ks
        .iter()
        .fold(0u64, |a, &k| a.saturating_add(upto(k as u64)));
    let cols = rank_space.min(n_cand.saturating_mul(max_terms)).max(1);
    let stride = cols.div_ceil(64);
    let bitmap = rank_space.div_ceil(64);
    let half = n_cand.div_ceil(2);
    bitmap
        .saturating_add(bitmap.div_ceil(2))
        .saturating_add(n_cand.saturating_mul(stride))
        .saturating_add(3 * half)
        .saturating_add((u64::from(d) + 1).saturating_mul(stride))
        .saturating_add(2 * n_cand)
        .saturating_add(8)
}

/// Turn a kernel result into the host kernel's answer, deciding on the
/// host when the kernel declined.
pub fn unpack(
    result: &F4Result,
    request: &DecisionRequest<'_>,
    caps: MacaulayCaps,
) -> (Option<Decision>, KernelCounters) {
    let mut k = KernelCounters::default();
    match result.status {
        STATUS_DECIDED => {
            let mut forced = Vec::with_capacity(result.forced_mask.count_ones() as usize);
            let mut m = result.forced_mask;
            while m != 0 {
                let v = m.trailing_zeros();
                forced.push((v, result.forced_vals >> v & 1 == 1));
                m &= m - 1;
            }
            k.built = true;
            k.rows = result.ref_rows;
            k.cols = result.ref_cols;
            k.eliminated_rows = u64::from(result.rows);
            k.eliminated_cols = u64::from(result.cols);
            k.word_ops = result.word_ops;
            (
                Some(Decision {
                    refuted: result.refuted != 0,
                    forced,
                }),
                k,
            )
        }
        STATUS_OVERSIZE => {
            k.oversize = true;
            (None, k)
        }
        STATUS_EMPTY => {
            k.built = true;
            (Some(Decision::default()), k)
        }
        STATUS_NO_POLYS => (Some(Decision::default()), k),
        _ => f4_gf2::decide(request.polys, request.n_vars, request.degree, caps),
    }
}

/// Clamp a cap to the kernel's 32-bit field.
fn cap32(x: usize) -> u32 {
    u32::try_from(x).unwrap_or(u32::MAX)
}

/// Spread a batch's wall time over its built results, so the profile's
/// phase split stays a sum of the whole stage.
fn charge_time(answers: &mut [(Option<Decision>, KernelCounters)], ns: u128) {
    let built = answers.iter().filter(|(_, k)| k.built).count().max(1) as u128;
    for (_, k) in answers.iter_mut().filter(|(_, k)| k.built) {
        k.reduce_ns = ns / built;
    }
}

#[cfg(feature = "gpu-emulator")]
mod emulator_ffi {
    use super::F4Result;
    extern "C" {
        pub fn f4_gf2_emulate_batch(
            terms: *const u64,
            poly_start: *const u32,
            sys_poly_start: *const u32,
            sys_meta: *const u32,
            n_systems: u32,
            max_rows: u32,
            max_cols: u32,
            threads: u32,
            scratch_words: u64,
            results: *mut F4Result,
        ) -> i32;
        pub fn f4_gf2_result_size() -> u64;
        pub fn f4_gf2_shared_size() -> u64;
    }
}

/// The device kernel's source run on the host: each system decided by one
/// emulated block of `threads` threads, chunks of the batch in parallel.
#[cfg(feature = "gpu-emulator")]
#[derive(Clone, Copy, Debug)]
pub struct EmulatorDecider {
    /// Threads per emulated block (1..=1024).
    pub threads: u32,
}

#[cfg(feature = "gpu-emulator")]
impl Default for EmulatorDecider {
    fn default() -> Self {
        EmulatorDecider { threads: 256 }
    }
}

#[cfg(feature = "gpu-emulator")]
impl EmulatorDecider {
    /// `sizeof(F4Result)` and `sizeof(F4Shared)` as the C compiler laid
    /// them out.
    pub fn c_layout() -> (u64, u64) {
        // SAFETY: pure functions of the compiled layout.
        unsafe {
            (
                emulator_ffi::f4_gf2_result_size(),
                emulator_ffi::f4_gf2_shared_size(),
            )
        }
    }

    /// Run the emulated kernel on a packed batch.
    pub fn run(&self, batch: &PackedBatch, caps: MacaulayCaps) -> Vec<F4Result> {
        let mut results = vec![F4Result::default(); batch.len()];
        if batch.is_empty() {
            return results;
        }
        // SAFETY: every pointer spans the length the batch layout declares,
        // and `results` holds one F4Result per system.
        let rc = unsafe {
            emulator_ffi::f4_gf2_emulate_batch(
                batch.terms.as_ptr(),
                batch.poly_start.as_ptr(),
                batch.sys_poly_start.as_ptr(),
                batch.sys_meta.as_ptr(),
                batch.len() as u32,
                cap32(caps.max_rows),
                cap32(caps.max_cols),
                self.threads,
                batch.scratch_words.max(1),
                results.as_mut_ptr(),
            )
        };
        assert_eq!(rc, 0, "f4_gf2_emulate_batch failed ({rc})");
        results
    }
}

#[cfg(feature = "gpu-emulator")]
impl BatchDecider for EmulatorDecider {
    fn name(&self) -> String {
        format!("emulate:{}", self.threads)
    }

    fn decide(
        &mut self,
        requests: &[DecisionRequest<'_>],
        caps: MacaulayCaps,
    ) -> Vec<(Option<Decision>, KernelCounters)> {
        use rayon::prelude::*;
        let t0 = std::time::Instant::now();
        let chunk = requests.len().div_ceil(rayon::current_num_threads()).max(1);
        let mut answers: Vec<(Option<Decision>, KernelCounters)> = requests
            .par_chunks(chunk)
            .flat_map_iter(|part| {
                let batch = PackedBatch::pack(part);
                let results = self.run(&batch, caps);
                part.iter()
                    .zip(results)
                    .map(|(r, res)| unpack(&res, r, caps))
                    .collect::<Vec<_>>()
            })
            .collect();
        charge_time(&mut answers, t0.elapsed().as_nanos());
        answers
    }
}

#[cfg(unix)]
pub use cuda::CudaDecider;

#[cfg(unix)]
mod cuda {
    //! The CUDA driver API and NVRTC, opened with `dlopen` on first use.
    use super::{
        cap32, charge_time, kernel_source, unpack, BatchDecider, Decision, DecisionRequest,
        F4Result, KernelCounters, MacaulayCaps, PackedBatch,
    };
    use std::ffi::{c_char, c_int, c_uint, c_void, CStr, CString};

    type CuResult = c_int;
    type Handle = *mut c_void;

    /// A `dlopen` handle, closed on drop.
    struct Library(Handle);

    impl Library {
        fn open(names: &[String]) -> Result<Self, String> {
            for name in names {
                let c = CString::new(name.as_str()).map_err(|e| e.to_string())?;
                // SAFETY: a NUL-terminated path; dlopen has no other contract.
                let h = unsafe { libc::dlopen(c.as_ptr(), libc::RTLD_NOW | libc::RTLD_LOCAL) };
                if !h.is_null() {
                    return Ok(Library(h));
                }
            }
            Err(format!("none of {names:?} could be opened"))
        }

        /// # Safety
        /// `T` must be the function-pointer type of the symbol.
        unsafe fn symbol<T: Copy>(&self, name: &str) -> Result<T, String> {
            assert_eq!(std::mem::size_of::<T>(), std::mem::size_of::<Handle>());
            let c = CString::new(name).map_err(|e| e.to_string())?;
            let p = libc::dlsym(self.0, c.as_ptr());
            if p.is_null() {
                Err(format!("symbol {name} not found"))
            } else {
                Ok(std::mem::transmute_copy(&p))
            }
        }
    }

    impl Drop for Library {
        fn drop(&mut self) {
            // SAFETY: the handle came from dlopen and is closed once.
            unsafe {
                libc::dlclose(self.0);
            }
        }
    }

    struct Driver {
        _lib: Library,
        init: unsafe extern "C" fn(c_uint) -> CuResult,
        device_get_count: unsafe extern "C" fn(*mut c_int) -> CuResult,
        device_get: unsafe extern "C" fn(*mut c_int, c_int) -> CuResult,
        device_get_attribute: unsafe extern "C" fn(*mut c_int, c_int, c_int) -> CuResult,
        device_get_name: unsafe extern "C" fn(*mut c_char, c_int, c_int) -> CuResult,
        primary_ctx_retain: unsafe extern "C" fn(*mut Handle, c_int) -> CuResult,
        primary_ctx_release: unsafe extern "C" fn(c_int) -> CuResult,
        ctx_set_current: unsafe extern "C" fn(Handle) -> CuResult,
        module_load_data: unsafe extern "C" fn(*mut Handle, *const c_void) -> CuResult,
        module_unload: unsafe extern "C" fn(Handle) -> CuResult,
        module_get_function: unsafe extern "C" fn(*mut Handle, Handle, *const c_char) -> CuResult,
        mem_alloc: unsafe extern "C" fn(*mut u64, usize) -> CuResult,
        mem_free: unsafe extern "C" fn(u64) -> CuResult,
        memcpy_htod: unsafe extern "C" fn(u64, *const c_void, usize) -> CuResult,
        memcpy_dtoh: unsafe extern "C" fn(*mut c_void, u64, usize) -> CuResult,
        #[allow(clippy::type_complexity)]
        launch_kernel: unsafe extern "C" fn(
            Handle,
            c_uint,
            c_uint,
            c_uint,
            c_uint,
            c_uint,
            c_uint,
            c_uint,
            Handle,
            *mut *mut c_void,
            *mut *mut c_void,
        ) -> CuResult,
        ctx_synchronize: unsafe extern "C" fn() -> CuResult,
        get_error_string: unsafe extern "C" fn(CuResult, *mut *const c_char) -> CuResult,
    }

    impl Driver {
        fn load() -> Result<Self, String> {
            let mut names = Vec::new();
            if let Ok(path) = std::env::var("CA_CUDA_LIB") {
                names.push(path);
            }
            names.extend(["libcuda.so.1".to_string(), "libcuda.so".to_string()]);
            let lib = Library::open(&names)?;
            // SAFETY: each type is the documented driver API prototype.
            unsafe {
                let first = |a: &str, b: &str| -> String {
                    if lib.symbol::<Handle>(a).is_ok() {
                        a.to_string()
                    } else {
                        b.to_string()
                    }
                };
                let release = first("cuDevicePrimaryCtxRelease_v2", "cuDevicePrimaryCtxRelease");
                Ok(Driver {
                    init: lib.symbol("cuInit")?,
                    device_get_count: lib.symbol("cuDeviceGetCount")?,
                    device_get: lib.symbol("cuDeviceGet")?,
                    device_get_attribute: lib.symbol("cuDeviceGetAttribute")?,
                    device_get_name: lib.symbol("cuDeviceGetName")?,
                    primary_ctx_retain: lib.symbol("cuDevicePrimaryCtxRetain")?,
                    primary_ctx_release: lib.symbol(&release)?,
                    ctx_set_current: lib.symbol("cuCtxSetCurrent")?,
                    module_load_data: lib.symbol("cuModuleLoadData")?,
                    module_unload: lib.symbol("cuModuleUnload")?,
                    module_get_function: lib.symbol("cuModuleGetFunction")?,
                    mem_alloc: lib.symbol("cuMemAlloc_v2")?,
                    mem_free: lib.symbol("cuMemFree_v2")?,
                    memcpy_htod: lib.symbol("cuMemcpyHtoD_v2")?,
                    memcpy_dtoh: lib.symbol("cuMemcpyDtoH_v2")?,
                    launch_kernel: lib.symbol("cuLaunchKernel")?,
                    ctx_synchronize: lib.symbol("cuCtxSynchronize")?,
                    get_error_string: lib.symbol("cuGetErrorString")?,
                    _lib: lib,
                })
            }
        }

        fn check(&self, rc: CuResult, what: &str) -> Result<(), String> {
            if rc == 0 {
                return Ok(());
            }
            let mut msg: *const c_char = std::ptr::null();
            // SAFETY: cuGetErrorString writes a static string pointer.
            unsafe { (self.get_error_string)(rc, &mut msg) };
            let text = if msg.is_null() {
                "unknown error".to_string()
            } else {
                // SAFETY: a static NUL-terminated string from the driver.
                unsafe { CStr::from_ptr(msg) }
                    .to_string_lossy()
                    .into_owned()
            };
            Err(format!("{what}: CUDA error {rc} ({text})"))
        }
    }

    struct Nvrtc {
        _lib: Library,
        create: unsafe extern "C" fn(
            *mut Handle,
            *const c_char,
            *const c_char,
            c_int,
            *const *const c_char,
            *const *const c_char,
        ) -> c_int,
        compile: unsafe extern "C" fn(Handle, c_int, *const *const c_char) -> c_int,
        log_size: unsafe extern "C" fn(Handle, *mut usize) -> c_int,
        log: unsafe extern "C" fn(Handle, *mut c_char) -> c_int,
        ptx_size: unsafe extern "C" fn(Handle, *mut usize) -> c_int,
        ptx: unsafe extern "C" fn(Handle, *mut c_char) -> c_int,
        destroy: unsafe extern "C" fn(*mut Handle) -> c_int,
    }

    impl Nvrtc {
        fn load() -> Result<Self, String> {
            let mut names = Vec::new();
            if let Ok(path) = std::env::var("CA_NVRTC_LIB") {
                names.push(path);
            }
            for v in ["13", "12", "11.2"] {
                names.push(format!("libnvrtc.so.{v}"));
            }
            names.push("libnvrtc.so".into());
            let lib = Library::open(&names)?;
            // SAFETY: each type is the documented NVRTC prototype.
            unsafe {
                Ok(Nvrtc {
                    create: lib.symbol("nvrtcCreateProgram")?,
                    compile: lib.symbol("nvrtcCompileProgram")?,
                    log_size: lib.symbol("nvrtcGetProgramLogSize")?,
                    log: lib.symbol("nvrtcGetProgramLog")?,
                    ptx_size: lib.symbol("nvrtcGetPTXSize")?,
                    ptx: lib.symbol("nvrtcGetPTX")?,
                    destroy: lib.symbol("nvrtcDestroyProgram")?,
                    _lib: lib,
                })
            }
        }

        /// Compile `source` to PTX for `compute_{arch}`.
        fn compile_ptx(&self, source: &str, arch: u32) -> Result<Vec<u8>, String> {
            let src = CString::new(source).map_err(|e| e.to_string())?;
            let name = CString::new("f4_gf2_kernel.cu").unwrap();
            let mut prog: Handle = std::ptr::null_mut();
            // SAFETY: valid NUL-terminated strings; no headers.
            let rc = unsafe {
                (self.create)(
                    &mut prog,
                    src.as_ptr(),
                    name.as_ptr(),
                    0,
                    std::ptr::null(),
                    std::ptr::null(),
                )
            };
            if rc != 0 {
                return Err(format!("nvrtcCreateProgram failed ({rc})"));
            }
            let opt = CString::new(format!("--gpu-architecture=compute_{arch}")).unwrap();
            let opts = [opt.as_ptr()];
            // SAFETY: `prog` is live; one option string.
            let rc = unsafe { (self.compile)(prog, 1, opts.as_ptr()) };
            let result = if rc != 0 {
                let mut n = 0usize;
                // SAFETY: querying the log of a live program.
                unsafe { (self.log_size)(prog, &mut n) };
                let mut buf = vec![0u8; n.max(1)];
                // SAFETY: `buf` holds the reported log size.
                unsafe { (self.log)(prog, buf.as_mut_ptr() as *mut c_char) };
                Err(format!(
                    "NVRTC compile for compute_{arch} failed: {}",
                    String::from_utf8_lossy(&buf).trim_end_matches('\0')
                ))
            } else {
                let mut n = 0usize;
                // SAFETY: querying the PTX of a compiled program.
                unsafe { (self.ptx_size)(prog, &mut n) };
                let mut buf = vec![0u8; n];
                // SAFETY: `buf` holds the reported PTX size, NUL included.
                unsafe { (self.ptx)(prog, buf.as_mut_ptr() as *mut c_char) };
                Ok(buf)
            };
            // SAFETY: destroying the program once.
            unsafe { (self.destroy)(&mut prog) };
            result
        }
    }

    /// A device allocation that grows as batches do.
    #[derive(Default)]
    struct Buffer {
        ptr: u64,
        bytes: usize,
    }

    /// The kernel on an NVIDIA device.
    pub struct CudaDecider {
        driver: Driver,
        device: c_int,
        context: Handle,
        module: Handle,
        function: Handle,
        name: String,
        compute: (i32, i32),
        sm_count: u32,
        /// Threads per block.
        pub threads: u32,
        /// Resident blocks per multiprocessor to launch for.
        pub blocks_per_sm: u32,
        /// Device scratch budget over all blocks, in bytes.
        pub scratch_budget: usize,
        buffers: [Buffer; 6],
    }

    // SAFETY: the handles are process-wide driver objects; every call makes
    // the context current on the calling thread first.
    unsafe impl Send for CudaDecider {}

    impl CudaDecider {
        /// Open device `ordinal`, compile the kernel for it (NVRTC, or the
        /// PTX file named by `CA_F4_PTX`) and load it.
        pub fn new(ordinal: usize) -> Result<Self, String> {
            let driver = Driver::load()?;
            // SAFETY: plain driver API calls with valid out-pointers.
            unsafe {
                driver.check((driver.init)(0), "cuInit")?;
                let mut count = 0;
                driver.check((driver.device_get_count)(&mut count), "cuDeviceGetCount")?;
                if ordinal >= count as usize {
                    return Err(format!("no CUDA device {ordinal} ({count} present)"));
                }
                let mut device = 0;
                driver.check(
                    (driver.device_get)(&mut device, ordinal as c_int),
                    "cuDeviceGet",
                )?;
                let attr = |a: c_int| -> Result<i32, String> {
                    let mut v = 0;
                    driver.check(
                        (driver.device_get_attribute)(&mut v, a, device),
                        "cuDeviceGetAttribute",
                    )?;
                    Ok(v)
                };
                let sm_count = attr(16)? as u32;
                let compute = (attr(75)?, attr(76)?);
                let mut raw = [0 as c_char; 256];
                driver.check(
                    (driver.device_get_name)(raw.as_mut_ptr(), 256, device),
                    "cuDeviceGetName",
                )?;
                let name = CStr::from_ptr(raw.as_ptr()).to_string_lossy().into_owned();
                let mut context: Handle = std::ptr::null_mut();
                driver.check(
                    (driver.primary_ctx_retain)(&mut context, device),
                    "cuDevicePrimaryCtxRetain",
                )?;
                driver.check((driver.ctx_set_current)(context), "cuCtxSetCurrent")?;
                let ptx = match std::env::var("CA_F4_PTX") {
                    Ok(path) => {
                        let mut bytes = std::fs::read(&path).map_err(|e| format!("{path}: {e}"))?;
                        bytes.push(0);
                        bytes
                    }
                    Err(_) => {
                        let nvrtc = Nvrtc::load()?;
                        let arch = (compute.0 * 10 + compute.1) as u32;
                        let source = kernel_source();
                        nvrtc
                            .compile_ptx(&source, arch)
                            .or_else(|_| nvrtc.compile_ptx(&source, 75))?
                    }
                };
                let mut module: Handle = std::ptr::null_mut();
                driver.check(
                    (driver.module_load_data)(&mut module, ptx.as_ptr() as *const c_void),
                    "cuModuleLoadData",
                )?;
                let fname = CString::new("f4_gf2_decide_batch").unwrap();
                let mut function: Handle = std::ptr::null_mut();
                driver.check(
                    (driver.module_get_function)(&mut function, module, fname.as_ptr()),
                    "cuModuleGetFunction",
                )?;
                let threads = std::env::var("CA_F4_THREADS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(256u32)
                    .clamp(32, 1024);
                let scratch_budget = std::env::var("CA_F4_SCRATCH_MB")
                    .ok()
                    .and_then(|v| v.parse::<usize>().ok())
                    .unwrap_or(1024)
                    << 20;
                Ok(CudaDecider {
                    driver,
                    device,
                    context,
                    module,
                    function,
                    name,
                    compute,
                    sm_count,
                    threads,
                    blocks_per_sm: 4,
                    scratch_budget,
                    buffers: Default::default(),
                })
            }
        }

        /// Device name, compute capability and multiprocessor count.
        pub fn device_info(&self) -> (String, (i32, i32), u32) {
            (self.name.clone(), self.compute, self.sm_count)
        }

        fn ensure(&mut self, slot: usize, bytes: usize) -> Result<u64, String> {
            let bytes = bytes.max(8);
            if self.buffers[slot].bytes < bytes {
                let old = std::mem::take(&mut self.buffers[slot]);
                // SAFETY: freeing our own allocation, then allocating anew.
                unsafe {
                    if old.ptr != 0 {
                        self.driver
                            .check((self.driver.mem_free)(old.ptr), "cuMemFree")?;
                    }
                    let mut ptr = 0u64;
                    self.driver
                        .check((self.driver.mem_alloc)(&mut ptr, bytes), "cuMemAlloc")?;
                    self.buffers[slot] = Buffer { ptr, bytes };
                }
            }
            Ok(self.buffers[slot].ptr)
        }

        fn upload<T: Copy>(&mut self, slot: usize, data: &[T]) -> Result<u64, String> {
            let bytes = std::mem::size_of_val(data);
            let ptr = self.ensure(slot, bytes)?;
            if bytes > 0 {
                // SAFETY: `ptr` spans at least `bytes`; `data` is host memory.
                unsafe {
                    self.driver.check(
                        (self.driver.memcpy_htod)(ptr, data.as_ptr() as *const c_void, bytes),
                        "cuMemcpyHtoD",
                    )?;
                }
            }
            Ok(ptr)
        }

        /// Run the kernel on a packed batch.
        pub fn run(
            &mut self,
            batch: &PackedBatch,
            caps: MacaulayCaps,
        ) -> Result<Vec<F4Result>, String> {
            let n = batch.len();
            let mut results = vec![F4Result::default(); n];
            if n == 0 {
                return Ok(results);
            }
            // SAFETY: making our retained primary context current.
            unsafe {
                self.driver.check(
                    (self.driver.ctx_set_current)(self.context),
                    "cuCtxSetCurrent",
                )?;
            }
            let grid = (self.sm_count * self.blocks_per_sm).max(1).min(n as u32);
            let per_block = (self.scratch_budget / 8 / grid as usize) as u64;
            let scratch_words = batch.scratch_words.clamp(1, per_block.max(1));
            let mut terms = self.upload(0, &batch.terms)?;
            let mut poly_start = self.upload(1, &batch.poly_start)?;
            let mut sys_poly_start = self.upload(2, &batch.sys_poly_start)?;
            let mut sys_meta = self.upload(3, &batch.sys_meta)?;
            let mut scratch = self.ensure(4, (scratch_words as usize) * 8 * grid as usize)?;
            let mut out = self.ensure(5, n * std::mem::size_of::<F4Result>())?;
            let mut n_systems = n as u32;
            let mut max_rows = cap32(caps.max_rows);
            let mut max_cols = cap32(caps.max_cols);
            let mut words = scratch_words;
            let mut params: [*mut c_void; 10] = [
                &mut terms as *mut u64 as *mut c_void,
                &mut poly_start as *mut u64 as *mut c_void,
                &mut sys_poly_start as *mut u64 as *mut c_void,
                &mut sys_meta as *mut u64 as *mut c_void,
                &mut n_systems as *mut u32 as *mut c_void,
                &mut max_rows as *mut u32 as *mut c_void,
                &mut max_cols as *mut u32 as *mut c_void,
                &mut scratch as *mut u64 as *mut c_void,
                &mut words as *mut u64 as *mut c_void,
                &mut out as *mut u64 as *mut c_void,
            ];
            // SAFETY: `params` points at one value per kernel argument, in
            // the order and with the types of `f4_gf2_decide_batch`.
            unsafe {
                self.driver.check(
                    (self.driver.launch_kernel)(
                        self.function,
                        grid,
                        1,
                        1,
                        self.threads,
                        1,
                        1,
                        0,
                        std::ptr::null_mut(),
                        params.as_mut_ptr(),
                        std::ptr::null_mut(),
                    ),
                    "cuLaunchKernel",
                )?;
                self.driver
                    .check((self.driver.ctx_synchronize)(), "cuCtxSynchronize")?;
                self.driver.check(
                    (self.driver.memcpy_dtoh)(
                        results.as_mut_ptr() as *mut c_void,
                        out,
                        n * std::mem::size_of::<F4Result>(),
                    ),
                    "cuMemcpyDtoH",
                )?;
            }
            Ok(results)
        }
    }

    impl Drop for CudaDecider {
        fn drop(&mut self) {
            // SAFETY: releasing what `new` and `ensure` acquired, once.
            unsafe {
                (self.driver.ctx_set_current)(self.context);
                for b in &self.buffers {
                    if b.ptr != 0 {
                        (self.driver.mem_free)(b.ptr);
                    }
                }
                (self.driver.module_unload)(self.module);
                (self.driver.primary_ctx_release)(self.device);
            }
        }
    }

    impl BatchDecider for CudaDecider {
        fn name(&self) -> String {
            format!(
                "cuda:{} sm_{}{} x{}",
                self.name, self.compute.0, self.compute.1, self.sm_count
            )
        }

        fn decide(
            &mut self,
            requests: &[DecisionRequest<'_>],
            caps: MacaulayCaps,
        ) -> Vec<(Option<Decision>, KernelCounters)> {
            let t0 = std::time::Instant::now();
            let batch = PackedBatch::pack(requests);
            let results = self
                .run(&batch, caps)
                .unwrap_or_else(|e| panic!("CUDA F4 batch failed: {e}"));
            let mut answers: Vec<_> = requests
                .iter()
                .zip(&results)
                .map(|(r, res)| unpack(res, r, caps))
                .collect();
            charge_time(&mut answers, t0.elapsed().as_nanos());
            answers
        }
    }
}

/// The decider named by `IC_F4_BACKEND`: `cuda[:N]` (device `N`),
/// `emulate[:threads]` (feature `gpu-emulator`), or `cpu` — the default,
/// also when the variable is unset.
pub fn decider_from_env() -> Result<Box<dyn BatchDecider>, String> {
    let spec = std::env::var("IC_F4_BACKEND").unwrap_or_else(|_| "cpu".into());
    decider_from_spec(&spec)
}

/// The decider named by `spec` (see [`decider_from_env`]).
pub fn decider_from_spec(spec: &str) -> Result<Box<dyn BatchDecider>, String> {
    let (kind, arg) = spec.split_once(':').unwrap_or((spec, ""));
    match kind {
        "cpu" | "" => Ok(Box::new(CpuDecider)),
        "cuda" => {
            #[cfg(unix)]
            {
                let ordinal = if arg.is_empty() {
                    0
                } else {
                    arg.parse()
                        .map_err(|_| format!("bad device ordinal {arg:?}"))?
                };
                Ok(Box::new(CudaDecider::new(ordinal)?))
            }
            #[cfg(not(unix))]
            {
                let _ = arg;
                Err("the CUDA backend needs a Unix dlopen".into())
            }
        }
        "emulate" => {
            #[cfg(feature = "gpu-emulator")]
            {
                let threads = if arg.is_empty() {
                    256
                } else {
                    arg.parse()
                        .map_err(|_| format!("bad thread count {arg:?}"))?
                };
                Ok(Box::new(EmulatorDecider { threads }))
            }
            #[cfg(not(feature = "gpu-emulator"))]
            {
                let _ = arg;
                Err("the emulator needs the `gpu-emulator` feature".into())
            }
        }
        other => Err(format!(
            "unknown F4 backend {other:?} (expected cpu, cuda[:N] or emulate[:threads])"
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_groebner::{build_decomposition_system, FieldStructure};
    use crate::cryptanalysis::koblitz_index_calculus::{build_frobenius_factor_base, KoblitzCurve};
    use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
    use rand::{rngs::StdRng, Rng, SeedableRng};

    const CAPS: MacaulayCaps = MacaulayCaps {
        max_rows: 20_000,
        max_cols: 40_000,
    };

    /// Real decomposition systems at their base and next degree, plus the
    /// substituted systems the search produces, plus random ones.
    pub(super) fn corpus() -> Vec<(Vec<F2BoolPoly>, usize, u32)> {
        let mut out = Vec::new();
        for (a, n, m) in [
            (0u8, 9u32, 2usize),
            (0, 9, 3),
            (1, 11, 2),
            (0, 13, 2),
            (1, 17, 2),
        ] {
            let Some(kc) = KoblitzCurve::new(a, n) else {
                continue;
            };
            let Some(fb) = build_frobenius_factor_base(&kc, 0) else {
                continue;
            };
            let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
            let mut rng = StdRng::seed_from_u64(u64::from(n) ^ 0xF4);
            for _ in 0..3 {
                let raw = 1 + rng.gen::<u64>() % ((1u64 << n) - 1);
                let x_r =
                    crate::binary_ecc::F2mElement::from_biguint(&num_bigint::BigUint::from(raw), n);
                let Some(sys) =
                    build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
                else {
                    continue;
                };
                let mut eqs = sys.equations.clone();
                for step in 0..3u32 {
                    let base = eqs
                        .iter()
                        .flat_map(|p| p.terms.iter())
                        .map(|t| t.mask.count_ones())
                        .max()
                        .unwrap_or(0)
                        .max(2);
                    for d in base..=base + 1 {
                        out.push((eqs.clone(), sys.n_vars, d));
                    }
                    let var = (step * 5 + 2) % sys.n_vars as u32;
                    eqs = eqs
                        .iter()
                        .map(|p| {
                            crate::cryptanalysis::koblitz_groebner::substitute(
                                p,
                                var,
                                step % 2 == 0,
                            )
                        })
                        .filter(|p| !p.is_zero())
                        .collect();
                }
            }
        }
        let mut rng = StdRng::seed_from_u64(0x6_F4);
        for case in 0..120usize {
            let n_vars = 3 + case % 12;
            let n_eqs = 1 + rng.gen::<usize>() % 8;
            let polys: Vec<F2BoolPoly> = (0..n_eqs)
                .map(|_| {
                    let monos: Vec<F2BoolMono> = (0..1 + rng.gen::<usize>() % 6)
                        .map(|_| {
                            let mut mask = 0u64;
                            for _ in 0..rng.gen::<u32>() % 4 {
                                mask |= 1u64 << (rng.gen::<u32>() % n_vars as u32);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n_vars)
                })
                .collect();
            out.push((polys, n_vars, 2 + (case as u32 % 3)));
        }
        out.push((Vec::new(), 5, 3));
        out
    }

    #[test]
    fn packing_round_trips_the_systems() {
        let corpus = corpus();
        let requests: Vec<DecisionRequest<'_>> = corpus
            .iter()
            .map(|(p, n, d)| DecisionRequest {
                polys: p,
                n_vars: *n,
                degree: *d,
            })
            .collect();
        let b = PackedBatch::pack(&requests);
        assert_eq!(b.len(), requests.len());
        for (i, r) in requests.iter().enumerate() {
            let (lo, hi) = (
                b.sys_poly_start[i] as usize,
                b.sys_poly_start[i + 1] as usize,
            );
            let nonzero: Vec<&F2BoolPoly> = r.polys.iter().filter(|p| !p.is_zero()).collect();
            assert_eq!(hi - lo, nonzero.len());
            for (k, p) in nonzero.iter().enumerate() {
                let (a, z) = (
                    b.poly_start[lo + k] as usize,
                    b.poly_start[lo + k + 1] as usize,
                );
                let masks: Vec<u64> = p.terms.iter().map(|t| t.mask).collect();
                assert_eq!(&b.terms[a..z], masks.as_slice());
            }
            assert_eq!(b.sys_meta[i] & 0xff, r.n_vars as u32);
            assert_eq!(b.sys_meta[i] >> 8, r.degree);
        }
    }

    #[test]
    fn unpack_decodes_every_status() {
        let p = F2BoolPoly::from_monos(vec![F2BoolMono::var(1), F2BoolMono::one()], 4);
        let polys = [p];
        let r = DecisionRequest {
            polys: &polys,
            n_vars: 4,
            degree: 2,
        };
        let decided = F4Result {
            status: STATUS_DECIDED,
            forced_mask: 0b1010,
            forced_vals: 0b0010,
            ref_rows: 7,
            ref_cols: 9,
            ..F4Result::default()
        };
        let (d, k) = unpack(&decided, &r, CAPS);
        assert_eq!(d.unwrap().forced, vec![(1, true), (3, false)]);
        assert!(k.built && k.rows == 7 && k.cols == 9);
        let (d, k) = unpack(
            &F4Result {
                status: STATUS_OVERSIZE,
                ..F4Result::default()
            },
            &r,
            CAPS,
        );
        assert!(d.is_none() && k.oversize);
        // A declined system is decided on the host.
        let (d, _) = unpack(
            &F4Result {
                status: STATUS_FALLBACK,
                ..F4Result::default()
            },
            &r,
            CAPS,
        );
        assert_eq!(d.unwrap().forced, vec![(1, true)]);
    }

    #[test]
    fn the_kernel_source_is_self_contained() {
        let src = kernel_source();
        assert!(src.contains("f4_gf2_decide_batch"));
        // NVRTC resolves no include path: the only #include is guarded out
        // by the header that precedes it.
        let includes: Vec<&str> = src
            .lines()
            .filter(|l| l.trim_start().starts_with("#include"))
            .collect();
        assert_eq!(includes, vec!["#include \"f4_gf2_device.cuh\""]);
        assert!(src.find("#define F4_GF2_DEVICE_CUH").unwrap() < src.find("#include").unwrap());
    }

    #[test]
    fn result_layout_matches_the_kernel() {
        // f4_u32 status, refuted; f4_u64 x5; f4_u32 rows, cols.
        assert_eq!(std::mem::size_of::<F4Result>(), 56);
        assert_eq!(std::mem::align_of::<F4Result>(), 8);
    }

    #[test]
    fn backend_specs_parse() {
        assert_eq!(decider_from_spec("cpu").unwrap().name(), "cpu");
        assert!(decider_from_spec("warp-drive").is_err());
        assert!(decider_from_spec("cuda:x").is_err());
    }

    #[cfg(feature = "gpu-emulator")]
    #[test]
    fn the_emulated_kernel_decides_like_the_host_kernel() {
        let (result_size, _) = EmulatorDecider::c_layout();
        assert_eq!(result_size as usize, std::mem::size_of::<F4Result>());
        let corpus = corpus();
        let requests: Vec<DecisionRequest<'_>> = corpus
            .iter()
            .map(|(p, n, d)| DecisionRequest {
                polys: p,
                n_vars: *n,
                degree: *d,
            })
            .collect();
        let host: Vec<_> = requests
            .iter()
            .map(|r| f4_gf2::decide(r.polys, r.n_vars, r.degree, CAPS))
            .collect();
        for threads in [1u32, 7, 32, 256] {
            let emu = EmulatorDecider { threads };
            let batch = PackedBatch::pack(&requests);
            let raw = emu.run(&batch, CAPS);
            let mut decided = 0;
            for (i, ((r, res), (want, wk))) in requests.iter().zip(&raw).zip(&host).enumerate() {
                assert_ne!(res.status, STATUS_FALLBACK, "system {i} fell back");
                let (got, gk) = unpack(res, r, CAPS);
                assert_eq!(&got, want, "system {i}, {threads} threads");
                assert_eq!(
                    (gk.built, gk.oversize),
                    (wk.built, wk.oversize),
                    "system {i}"
                );
                assert_eq!((gk.rows, gk.cols), (wk.rows, wk.cols), "system {i} shape");
                assert_eq!(
                    (gk.eliminated_rows, gk.eliminated_cols),
                    (wk.eliminated_rows, wk.eliminated_cols),
                    "system {i} eliminated shape"
                );
                decided += usize::from(res.status == STATUS_DECIDED);
            }
            assert!(decided > 100, "only {decided} decided");
        }
    }

    #[cfg(feature = "gpu-emulator")]
    #[test]
    fn the_emulated_kernel_applies_the_caps_like_the_host_kernel() {
        let corpus = corpus();
        let emu = EmulatorDecider { threads: 64 };
        let mut refused = 0;
        for (polys, n_vars, degree) in corpus.iter().take(60) {
            let r = DecisionRequest {
                polys,
                n_vars: *n_vars,
                degree: *degree,
            };
            let (_, k) = f4_gf2::decide(polys, *n_vars, *degree, CAPS);
            if !k.built || k.rows == 0 {
                continue;
            }
            for (dr, dc) in [(0u64, 0u64), (1, 0), (0, 1)] {
                let caps = MacaulayCaps {
                    max_rows: (k.rows - dr.min(k.rows)) as usize,
                    max_cols: (k.cols - dc.min(k.cols)) as usize,
                };
                let want = f4_gf2::decide(polys, *n_vars, *degree, caps);
                let res = emu.run(&PackedBatch::pack(&[r]), caps);
                let got = unpack(&res[0], &r, caps);
                assert_eq!(got.0, want.0);
                assert_eq!(got.1.oversize, want.1.oversize);
                refused += usize::from(want.1.oversize);
            }
        }
        assert!(refused > 20, "only {refused} refusals exercised");
    }

    /// The whole path the pipeline takes: searches in lockstep, every
    /// round decided by the emulated device kernel.
    #[cfg(feature = "gpu-emulator")]
    #[test]
    fn lockstep_on_the_emulated_kernel_matches_the_recursive_solver() {
        use crate::cryptanalysis::f4_batch::solve_lockstep;
        use crate::cryptanalysis::koblitz_groebner::{
            solve_boolean_system_filtered, SolveOptions, SolverEngine,
        };
        let systems: Vec<(Vec<F2BoolPoly>, usize)> = corpus()
            .into_iter()
            .filter(|(p, _, _)| !p.is_empty())
            .step_by(4)
            .map(|(p, n, _)| (p, n))
            .collect();
        let opts = SolveOptions {
            engine: SolverEngine::MatrixF4 { max_degree: 3 },
            max_solutions: usize::MAX,
            node_budget: 256,
            ..SolveOptions::default()
        };
        let accept = |i: usize, root: u64| root % 5 == (i % 5) as u64;
        let (got, _) = solve_lockstep(
            &systems,
            &opts,
            &mut EmulatorDecider { threads: 64 },
            &accept,
        );
        for (i, ((eqs, n_vars), outcome)) in systems.iter().zip(&got).enumerate() {
            let (sols, stats) =
                solve_boolean_system_filtered(eqs, *n_vars, &opts, |root| accept(i, root));
            assert_eq!(outcome.solutions, sols, "system {i}");
            assert_eq!(outcome.stats.reductions, stats.reductions, "system {i}");
            assert_eq!(outcome.stats.splits, stats.splits, "system {i}");
            assert_eq!(outcome.stats.propagations, stats.propagations, "system {i}");
            assert_eq!(outcome.stats.oversize, stats.oversize, "system {i}");
            assert_eq!(outcome.stats.exhausted, stats.exhausted, "system {i}");
        }
    }

    #[cfg(feature = "gpu-emulator")]
    #[test]
    fn a_small_scratch_falls_back_to_the_host() {
        let corpus = corpus();
        let requests: Vec<DecisionRequest<'_>> = corpus
            .iter()
            .take(10)
            .map(|(p, n, d)| DecisionRequest {
                polys: p,
                n_vars: *n,
                degree: *d,
            })
            .collect();
        let mut batch = PackedBatch::pack(&requests);
        batch.scratch_words = 16;
        let raw = EmulatorDecider { threads: 32 }.run(&batch, CAPS);
        assert!(raw.iter().any(|r| r.status == STATUS_FALLBACK));
        for (r, res) in requests.iter().zip(&raw) {
            let want = f4_gf2::decide(r.polys, r.n_vars, r.degree, CAPS).0;
            assert_eq!(unpack(res, r, CAPS).0, want);
        }
    }
}
