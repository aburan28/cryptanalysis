//! Interruption: a session that is stopped must still put the host back.
//!
//! A session moves other threads off its CPUs and runs a measured child
//! in its own process group, where the terminal's Ctrl-C does not reach
//! it.  Killed outright by SIGINT, SIGTERM (a CI cancel, `timeout`) or
//! SIGHUP (a dropped SSH session), the runner would leave every evicted
//! thread with a narrowed mask and the child solving on a core the lock
//! no longer protects.
//!
//! So the runner blocks those signals in every thread and takes them in
//! one thread with `sigwait`.  That thread only records the signal and
//! kills the child's process group; the main thread sees the flag at its
//! next step, writes the session as interrupted, restores the evicted
//! threads (the eviction handle restores on drop as well, for a panic)
//! and exits with `128 + signal`.  The child unblocks the signals again
//! between fork and exec, and on Linux asks to be killed if the runner
//! dies (`PR_SET_PDEATHSIG`), which covers SIGKILL too.

use std::sync::atomic::{AtomicI32, Ordering};

/// The signal that interrupted the session, or 0.
static INTERRUPTED: AtomicI32 = AtomicI32::new(0);
/// The running child's pid (and process group), or 0.
static CHILD: AtomicI32 = AtomicI32::new(0);

#[cfg(unix)]
const SIGNALS: [libc::c_int; 4] = [libc::SIGINT, libc::SIGTERM, libc::SIGHUP, libc::SIGQUIT];

#[cfg(unix)]
fn signal_set() -> libc::sigset_t {
    // SAFETY: a zeroed set initialised by sigemptyset before use.
    unsafe {
        let mut set: libc::sigset_t = std::mem::zeroed();
        libc::sigemptyset(&mut set);
        for s in SIGNALS {
            libc::sigaddset(&mut set, s);
        }
        set
    }
}

/// Block the interrupting signals in this thread (and so in every thread
/// started after it) and start the thread that takes them.  Call before
/// starting any other thread.  Idempotent.
pub fn install() {
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| {
        #[cfg(unix)]
        {
            let set = signal_set();
            // SAFETY: blocking a valid set in the calling thread.
            unsafe {
                libc::pthread_sigmask(libc::SIG_BLOCK, &set, std::ptr::null_mut());
            }
            std::thread::spawn(move || loop {
                let mut sig: libc::c_int = 0;
                // SAFETY: the set is blocked in every thread, as sigwait requires.
                if unsafe { libc::sigwait(&set, &mut sig) } == 0 {
                    INTERRUPTED.store(sig, Ordering::SeqCst);
                    kill_child();
                }
            });
        }
    });
}

/// The signal that interrupted the session, if one did.
pub fn interrupted() -> Option<i32> {
    match INTERRUPTED.load(Ordering::SeqCst) {
        0 => None,
        s => Some(s),
    }
}

/// Record the running child, and kill it at once if an interruption
/// arrived before it was recorded.
pub fn set_child(pid: i32) {
    CHILD.store(pid, Ordering::SeqCst);
    if interrupted().is_some() {
        kill_child();
    }
}

pub fn clear_child() {
    CHILD.store(0, Ordering::SeqCst);
}

fn kill_child() {
    let pid = CHILD.load(Ordering::SeqCst);
    if pid > 0 {
        #[cfg(unix)]
        // SAFETY: signalling the child's own process group.
        unsafe {
            libc::kill(-pid, libc::SIGKILL);
        }
    }
}

/// In the child, between fork and exec: unblock the signals the runner
/// blocked, and on Linux die with the runner.  `parent` is the runner's
/// pid, to close the race where it died before the request took effect.
///
/// # Safety
/// Async-signal-safe system calls only.
#[cfg(unix)]
pub unsafe fn prepare_child(parent: u32) -> std::io::Result<()> {
    let set = signal_set();
    if libc::sigprocmask(libc::SIG_UNBLOCK, &set, std::ptr::null_mut()) != 0 {
        return Err(std::io::Error::last_os_error());
    }
    #[cfg(target_os = "linux")]
    {
        if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL as libc::c_ulong) != 0 {
            return Err(std::io::Error::last_os_error());
        }
        if libc::getppid() as u32 != parent {
            return Err(std::io::Error::from_raw_os_error(libc::ESRCH));
        }
    }
    #[cfg(not(target_os = "linux"))]
    let _ = parent;
    Ok(())
}
