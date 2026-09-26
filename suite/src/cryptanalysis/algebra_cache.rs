//! Separate caches for target-independent preprocessing and exact reductions.
//! Redis is a trusted, private computation cache, not a proof verifier. Checksums
//! detect accidental corruption; they do not authenticate a malicious writer.
//!
//! The two layers store different things on purpose. Redis holds the encoded
//! envelope, because bytes are what cross a wire and what a checksum can speak
//! about. The in-process layer holds the DECODED value: it never left the
//! process, so there is nothing to parse and nothing a checksum could tell us.
//! Storing bytes there made every local hit re-run `serde_json` over the whole
//! artifact -- measured at up to 5.6 ms against a 9.1 ms build, so the cache
//! was returning most of what it saved (`examples/preprocessing_cost.rs`).
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::{any::Any, cell::RefCell, collections::VecDeque, sync::OnceLock, time::Instant};

#[derive(Clone, Copy)]
pub enum Layer {
    Preprocessing,
    ExactReduction,
    /// Has no producer.  It held `polynomial_reuse::parameter_basis_cached`,
    /// removed once measured never to pay for itself (the note at that
    /// function's former place gives the figures).  The slot is kept, not
    /// deleted, because `ic` reports cache statistics as the fixed array
    /// `[preprocessing, exact-reduction, parameterized]` and the 2026-09-14
    /// polynomial-reuse record reads that shape; its counters now stay zero.
    Parameterized,
}
impl Layer {
    fn index(self) -> usize {
        match self {
            Self::Preprocessing => 0,
            Self::ExactReduction => 1,
            Self::Parameterized => 2,
        }
    }
    fn name(self) -> &'static str {
        ["preprocessing", "exact-reduction", "parameterized"][self.index()]
    }
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct CacheStats {
    pub lookups: u64,
    pub local_hits: u64,
    pub redis_hits: u64,
    pub misses: u64,
    pub errors: u64,
    pub invalid: u64,
    pub oversized: u64,
    pub bytes_read: u64,
    pub bytes_written: u64,
    pub overhead_ns: u64,
}
#[derive(Serialize, Deserialize)]
struct Envelope {
    key: String,
    payload: String,
    checksum: String,
}

/// One in-process entry: the decoded value, plus the encoded size it was
/// admitted on.
///
/// `size` is the ENCODED length, not the decoded footprint, which cannot be
/// measured from here. It stays the basis for `local_limit` so the bound keeps
/// the meaning it had before; for these artifacts JSON is the larger form, so
/// the limit errs conservative rather than over-committing memory.
struct LocalEntry {
    size: usize,
    value: Box<dyn Any + Send>,
}

pub struct AlgebraCache {
    enabled: [bool; 3],
    remote_enabled: [bool; 3],
    namespace: String,
    local: VecDeque<(String, LocalEntry)>,
    local_bytes: usize,
    local_limit: usize,
    /// Largest envelope Redis will be asked to hold. A WIRE limit: `GETRANGE`
    /// bounds what a read can pull back, so a value past it could not be read
    /// whole even if it were written. It says nothing about what this process
    /// can hold.
    max_value: usize,
    /// Warn once per layer rather than once per artifact, so a relation search
    /// that keeps building oversized templates says so without flooding.
    warned_oversize: [bool; 3],
    strict_oversize: bool,
    pub stats: [CacheStats; 3],
    #[cfg(feature = "redis-cache")]
    client: Option<redis::Client>,
    #[cfg(feature = "redis-cache")]
    connection: Option<redis::Connection>,
    #[cfg(feature = "redis-cache")]
    retry_after: Option<Instant>,
}
fn fingerprint() -> &'static str {
    static HASH: OnceLock<String> = OnceLock::new();
    HASH.get_or_init(|| {
        let mut h = blake3::Hasher::new();
        for source in [
            include_str!("algebra_cache.rs"),
            include_str!("polynomial_reuse.rs"),
            include_str!("koblitz_groebner.rs"),
            include_str!("f4_gf2.rs"),
            include_str!("pq_groebner_f2.rs"),
            // Produces the cached symbolic summation polynomials. Without it a
            // change to the generator would leave every key untouched and the
            // old bytes would be served as current.
            include_str!("semaev_leading_form.rs"),
        ] {
            h.update(source.as_bytes());
        }
        h.finalize().to_hex().to_string()
    })
}
impl AlgebraCache {
    pub fn local(bytes: usize) -> Self {
        Self {
            enabled: [true; 3],
            remote_enabled: [false; 3],
            namespace: "index-calculus".into(),
            local: VecDeque::new(),
            local_bytes: 0,
            local_limit: bytes,
            max_value: 4 * 1024 * 1024,
            warned_oversize: [false; 3],
            strict_oversize: true,
            stats: Default::default(),
            #[cfg(feature = "redis-cache")]
            client: None,
            #[cfg(feature = "redis-cache")]
            connection: None,
            #[cfg(feature = "redis-cache")]
            retry_after: None,
        }
    }
    /// Errors omit URLs because they can contain credentials.
    #[cfg(feature = "redis-cache")]
    pub fn with_redis(mut self, url: &str) -> Result<Self, &'static str> {
        self.remote_enabled = [true; 3];
        self.client = Some(redis::Client::open(url).map_err(|_| "invalid Redis URL")?);
        Ok(self)
    }
    /// Whether an artifact that cannot be shared is fatal. ON by default.
    ///
    /// The cost of this default is real and worth stating: a run that produces
    /// an artifact past the wire cap now stops, even though its computation was
    /// correct and would have completed. That is the trade asked for -- silence
    /// there is a performance cliff nobody sees, and a stopped run is at least
    /// a run you can ask about.
    ///
    /// Turn it off for a job that would rather finish degraded than stop:
    /// `strict_oversize(false)`, or `IC_CACHE_STRICT_OVERSIZE=0`.
    pub fn strict_oversize(mut self, on: bool) -> Self {
        self.strict_oversize = on;
        self
    }
    fn from_env() -> Self {
        let mut c = Self::local(32 * 1024 * 1024);
        // Opt-OUT: anything explicitly falsey disables it, everything else
        // (including unset) leaves it on.
        c.strict_oversize = !matches!(
            std::env::var("IC_CACHE_STRICT_OVERSIZE").as_deref(),
            Ok("0") | Ok("false") | Ok("no")
        );
        c.enabled = [
            "IC_PREPROCESS_CACHE",
            "IC_REDUCTION_CACHE",
            "IC_PARAMETER_CACHE",
        ]
        .map(|key| matches!(std::env::var(key).as_deref(), Ok("local") | Ok("redis")));
        c.remote_enabled = [
            "IC_PREPROCESS_CACHE",
            "IC_REDUCTION_CACHE",
            "IC_PARAMETER_CACHE",
        ]
        .map(|key| std::env::var(key).as_deref() == Ok("redis"));
        if let Ok(bytes) = std::env::var("IC_CACHE_LOCAL_BYTES") {
            if let Ok(bytes) = bytes.parse::<usize>() {
                c.local_limit = bytes.min(1024 * 1024 * 1024);
            }
        }
        // The connection is common; a local layer never accesses Redis.
        #[cfg(feature = "redis-cache")]
        if [
            "IC_PREPROCESS_CACHE",
            "IC_REDUCTION_CACHE",
            "IC_PARAMETER_CACHE",
        ]
        .iter()
        .any(|k| std::env::var(k).as_deref() == Ok("redis"))
        {
            c.client = std::env::var("IC_REDIS_URL")
                .ok()
                .and_then(|u| redis::Client::open(u).ok());
            if c.client.is_none() {
                eprintln!("Redis cache configuration unavailable; using local fallback");
            }
        }
        #[cfg(not(feature = "redis-cache"))]
        if [
            "IC_PREPROCESS_CACHE",
            "IC_REDUCTION_CACHE",
            "IC_PARAMETER_CACHE",
        ]
        .iter()
        .any(|k| std::env::var(k).as_deref() == Ok("redis"))
        {
            eprintln!("Redis feature is not compiled; using local fallback");
        }
        if let Ok(ns) = std::env::var("IC_REDIS_NAMESPACE") {
            if !ns.is_empty()
                && ns.len() <= 64
                && ns
                    .bytes()
                    .all(|x| x.is_ascii_alphanumeric() || x == b'-' || x == b'_')
            {
                c.namespace = ns;
            }
        }
        c
    }
    fn key(&self, layer: Layer, input: &[u8]) -> String {
        format!(
            "ic:v3:{}:{}:{}:{}",
            self.namespace,
            layer.name(),
            fingerprint(),
            blake3::hash(input).to_hex()
        )
    }
    fn retain(&mut self, key: String, encoded_len: usize, value: Box<dyn Any + Send>) {
        let size = key.len() + encoded_len + 128;
        if size > self.local_limit {
            return;
        }
        if let Some(pos) = self.local.iter().position(|(k, _)| k == &key) {
            let (_, e) = self.local.remove(pos).unwrap();
            self.local_bytes -= e.size;
        }
        while self.local_bytes + size > self.local_limit {
            let (_, e) = self.local.pop_front().unwrap();
            self.local_bytes -= e.size;
        }
        self.local_bytes += size;
        self.local.push_back((key, LocalEntry { size, value }));
    }
    #[cfg(feature = "redis-cache")]
    fn remote<T: redis::FromRedisValue>(&mut self, cmd: &redis::Cmd, i: usize) -> Option<T> {
        use std::time::Duration;
        if !self.remote_enabled[i] {
            return None;
        }
        let client = self.client.as_ref()?;
        if self.retry_after.is_some_and(|t| Instant::now() < t) {
            return None;
        }
        let result = (|| {
            if self.connection.is_none() {
                let c = client.get_connection_with_timeout(Duration::from_millis(100))?;
                c.set_read_timeout(Some(Duration::from_millis(100)))?;
                c.set_write_timeout(Some(Duration::from_millis(100)))?;
                self.connection = Some(c);
            }
            cmd.query(self.connection.as_mut().unwrap())
        })();
        match result {
            Ok(v) => Some(v),
            Err(_) => {
                self.stats[i].errors += 1;
                self.connection = None;
                self.retry_after = Some(Instant::now() + Duration::from_secs(5));
                None
            }
        }
    }
    /// An artifact past the wire cap is a performance cliff, and it used to be
    /// an invisible one: the value silently stopped being shared and the only
    /// trace was a counter nobody reads. Say it once per layer, or fail hard
    /// under `strict_oversize`.
    fn report_oversize(&mut self, i: usize, layer: Layer, len: usize) {
        if self.strict_oversize {
            panic!(
                "algebra cache: {} artifact is {len} bytes, past the {} byte Redis \
                 value cap, so it cannot be shared between processes. Reduce the \
                 parameters or raise the cap; set IC_CACHE_STRICT_OVERSIZE=0 to \
                 carry on with a warning instead of stopping.",
                layer.name(),
                self.max_value,
            );
        }
        if !self.warned_oversize[i] {
            self.warned_oversize[i] = true;
            eprintln!(
                "algebra cache: {} artifact is {len} bytes, past the {} byte Redis \
                 value cap; holding it in this process only, not sharing it. \
                 Later occurrences on this layer are counted in stats().oversized.",
                layer.name(),
                self.max_value,
            );
        }
    }
    /// Cache only successful computations; None is never an UNSAT certificate.
    ///
    /// `T: Clone + Send + 'static` is what the in-process layer costs: it holds
    /// decoded values behind `dyn Any`, so a hit clones rather than re-parses.
    pub fn memoize<T: Serialize + DeserializeOwned + Clone + Send + 'static>(
        &mut self,
        layer: Layer,
        input: &[u8],
        compute: impl FnOnce() -> Option<T>,
    ) -> Option<T> {
        let start = Instant::now();
        let i = layer.index();
        let key = self.key(layer, input);
        self.stats[i].lookups += 1;

        // In-process hit: clone the decoded value and move it to the back of
        // the LRU. No envelope, no checksum -- the value never left the
        // process, so neither has anything to say about it.
        if let Some(pos) = self.local.iter().position(|(k, _)| k == &key) {
            let cloned = self.local[pos].1.value.downcast_ref::<T>().cloned();
            match cloned {
                Some(value) => {
                    let entry = self.local.remove(pos).unwrap();
                    self.local.push_back(entry);
                    self.stats[i].local_hits += 1;
                    self.stats[i].overhead_ns += start.elapsed().as_nanos() as u64;
                    return Some(value);
                }
                None => {
                    // One key holding a different type. Type erasure makes this
                    // expressible where storing bytes did not, so it is handled
                    // rather than assumed away: drop the entry and recompute,
                    // never hand back something of the wrong type.
                    let (_, e) = self.local.remove(pos).unwrap();
                    self.local_bytes -= e.size;
                    self.stats[i].invalid += 1;
                }
            }
        }

        // Redis: this came off a wire, so the envelope and its checksum apply.
        #[cfg(feature = "redis-cache")]
        let bytes = self
            .remote::<Vec<u8>>(
                redis::cmd("GETRANGE").arg(&key).arg(0).arg(self.max_value),
                i,
            )
            .filter(|b| !b.is_empty());
        #[cfg(not(feature = "redis-cache"))]
        let bytes: Option<Vec<u8>> = None;

        if let Some(bytes) = bytes {
            let decode = || -> Option<T> {
                if bytes.len() > self.max_value {
                    return None;
                }
                let e: Envelope = serde_json::from_slice(&bytes).ok()?;
                if e.key != key
                    || e.checksum != blake3::hash(e.payload.as_bytes()).to_hex().to_string()
                {
                    return None;
                }
                serde_json::from_str(&e.payload).ok()
            };
            if let Some(value) = decode() {
                self.stats[i].redis_hits += 1;
                self.stats[i].bytes_read += bytes.len() as u64;
                self.retain(key, bytes.len(), Box::new(value.clone()));
                self.stats[i].overhead_ns += start.elapsed().as_nanos() as u64;
                return Some(value);
            }
            self.stats[i].invalid += 1;
        }
        self.stats[i].misses += 1;
        self.stats[i].overhead_ns += start.elapsed().as_nanos() as u64;
        let value = compute()?;
        let start = Instant::now();
        if let Ok(payload) = serde_json::to_string(&value) {
            let checksum = blake3::hash(payload.as_bytes()).to_hex().to_string();
            if let Ok(bytes) = serde_json::to_vec(&Envelope {
                key: key.clone(),
                payload,
                checksum,
            }) {
                if bytes.len() <= self.max_value {
                    #[cfg(feature = "redis-cache")]
                    {
                        let _: Option<()> = self.remote(
                            redis::cmd("SET").arg(&key).arg(&bytes).arg("EX").arg(86400),
                            i,
                        );
                    }
                    self.stats[i].bytes_written += bytes.len() as u64;
                } else {
                    // Too big for the WIRE, which is all `max_value` governs.
                    // This used to gate the in-process layer too, so crossing
                    // the cap dropped both tiers at once -- and it drops them
                    // for exactly the artifacts that cost the most to rebuild,
                    // since size and build cost move together. The local layer
                    // has its own bound in `local_limit` and holds a decoded
                    // value rather than an envelope, so it takes this one.
                    self.stats[i].oversized += 1;
                    self.report_oversize(i, layer, bytes.len());
                }
                self.retain(key, bytes.len(), Box::new(value.clone()));
            }
        }
        self.stats[i].overhead_ns += start.elapsed().as_nanos() as u64;
        Some(value)
    }
}
thread_local! { static CACHE: RefCell<AlgebraCache> = RefCell::new(AlgebraCache::from_env()); }
pub fn enabled(layer: Layer) -> bool {
    CACHE.with(|c| c.borrow().enabled[layer.index()])
}
pub fn memoize<T: Serialize + DeserializeOwned + Clone + Send + 'static>(
    layer: Layer,
    input: &[u8],
    compute: impl FnOnce() -> Option<T>,
) -> Option<T> {
    CACHE.with(|c| c.borrow_mut().memoize(layer, input, compute))
}
/// Statistics for the calling thread. Parallel collectors must aggregate workers.
pub fn stats() -> [CacheStats; 3] {
    CACHE.with(|c| c.borrow().stats.clone())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cached_reductions_preserve_answers_and_node_budgets() {
        use crate::cryptanalysis::koblitz_groebner::{
            solve_boolean_system, SolveOptions, SolverEngine,
        };
        use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
        let equations = vec![F2BoolPoly::from_monos(
            vec![F2BoolMono::from_mask(3), F2BoolMono::from_mask(4)],
            3,
        )];
        for engine in [
            SolverEngine::Buchberger,
            SolverEngine::MatrixF4 { max_degree: 3 },
        ] {
            for budget in [1, 3, 100] {
                let options = SolveOptions {
                    engine,
                    node_budget: budget,
                    max_solutions: usize::MAX,
                    ..Default::default()
                };
                CACHE.with(|c| {
                    let mut c = c.borrow_mut();
                    c.enabled = [false; 3];
                });
                let baseline = solve_boolean_system(&equations, 3, &options);
                CACHE.with(|c| *c.borrow_mut() = AlgebraCache::local(1024 * 1024));
                for _ in 0..2 {
                    let candidate = solve_boolean_system(&equations, 3, &options);
                    assert_eq!(baseline.0, candidate.0);
                    assert_eq!(baseline.1.reductions, candidate.1.reductions);
                    assert_eq!(baseline.1.exhausted, candidate.1.exhausted);
                    assert_eq!(baseline.1.oversize, candidate.1.oversize);
                }
                assert!(stats()[1].local_hits > 0);
            }
        }
    }
    #[test]
    fn layers_are_disjoint_and_none_is_not_cached() {
        let mut c = AlgebraCache::local(4096);
        for (layer, value) in [
            (Layer::Preprocessing, 1u64),
            (Layer::ExactReduction, 2),
            (Layer::Parameterized, 3),
        ] {
            assert_eq!(c.memoize(layer, b"same", || Some(value)), Some(value));
            assert_eq!(
                c.memoize(layer, b"same", || panic!("must hit")),
                Some(value)
            );
            let x: Option<u64> = c.memoize(layer, b"incomplete", || None);
            assert!(x.is_none());
            assert_eq!(c.memoize(layer, b"incomplete", || Some(4u64)), Some(4));
        }
    }
    #[test]
    fn bounded_storage() {
        let mut c = AlgebraCache::local(4096);
        for i in 0..100u64 {
            c.memoize(Layer::Preprocessing, &i.to_le_bytes(), || Some(i));
        }
        assert!(c.local_bytes <= 4096);
        assert_eq!(
            c.local_bytes,
            c.local.iter().map(|(_, e)| e.size).sum::<usize>(),
            "the running total must equal what is actually held"
        );
        let mut c = AlgebraCache::local(0);
        c.memoize(Layer::Preprocessing, b"x", || Some(2u64));
        assert!(c.local.is_empty());
    }

    /// The local layer holds decoded values, so there are no local bytes left
    /// to corrupt -- that property now belongs to Redis alone, where
    /// `redis_cross_client_reuse_and_corruption` covers it. What type erasure
    /// introduces instead is one key reached at two types, which is what this
    /// pins: recompute at the new type, never hand back the old one.
    #[test]
    fn one_key_at_two_types_recomputes() {
        let mut c = AlgebraCache::local(1 << 20);
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"x", || Some(2u64)),
            Some(2)
        );
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"x", || Some("two".to_string())),
            Some("two".to_string())
        );
        assert_eq!(c.stats[0].invalid, 1);
        // The displaced entry is gone from the accounting, not just the queue.
        assert_eq!(
            c.local_bytes,
            c.local.iter().map(|(_, e)| e.size).sum::<usize>()
        );
        // And the surviving entry is the one just written.
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"x", || panic!("must hit")),
            Some("two".to_string())
        );
    }

    /// A local hit must not touch `serde_json`: it returns a value whose type
    /// does not round-trip through the encoder at all.
    #[test]
    fn a_local_hit_does_not_re_parse() {
        #[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
        struct Asymmetric {
            n: u64,
            /// Skipped on the wire, so a decode can never restore it. If a
            /// local hit re-parsed, this would come back empty.
            #[serde(skip)]
            only_in_memory: String,
        }
        let mut c = AlgebraCache::local(1 << 20);
        let made = Asymmetric {
            n: 7,
            only_in_memory: "not on the wire".into(),
        };
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"k", || Some(made.clone())),
            Some(made.clone())
        );
        let hit = c
            .memoize::<Asymmetric>(Layer::Preprocessing, b"k", || panic!("must hit"))
            .unwrap();
        assert_eq!(c.stats[0].local_hits, 1);
        assert_eq!(hit, made, "a local hit re-parsed instead of cloning");
    }
    /// A value too big for the wire is still worth holding in process. It used
    /// to be dropped by both tiers at once, which lost exactly the artifacts
    /// that cost the most to rebuild.
    #[test]
    fn an_oversized_artifact_is_still_served_locally() {
        let mut c = AlgebraCache::local(64 * 1024 * 1024).strict_oversize(false);
        c.max_value = 512;
        let big = "x".repeat(4096);
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"big", || Some(big.clone())),
            Some(big.clone())
        );
        assert_eq!(c.stats[0].oversized, 1, "it must be counted as oversized");
        assert_eq!(
            c.stats[0].bytes_written, 0,
            "and must not be claimed as written to the wire"
        );
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"big", || panic!("must hit locally")),
            Some(big)
        );
        assert_eq!(c.stats[0].local_hits, 1);
    }

    /// The warning is once per layer, not once per artifact: a relation search
    /// that keeps building oversized templates should say so without flooding.
    #[test]
    fn the_oversize_warning_is_once_per_layer() {
        let mut c = AlgebraCache::local(64 * 1024 * 1024).strict_oversize(false);
        c.max_value = 512;
        let big = "x".repeat(4096);
        for n in 0..5u8 {
            c.memoize(Layer::Preprocessing, &[n], || Some(big.clone()));
        }
        assert!(c.warned_oversize[0]);
        assert!(!c.warned_oversize[1], "another layer warns on its own");
        assert_eq!(c.stats[0].oversized, 5, "every one is still counted");
    }

    /// Fatal by default: losing the ability to share an artifact is a cliff,
    /// and stopping is preferred to sliding down it quietly.
    #[test]
    #[should_panic(expected = "cannot be shared between processes")]
    fn oversize_is_fatal_by_default() {
        let mut c = AlgebraCache::local(64 * 1024 * 1024);
        c.max_value = 512;
        c.memoize(Layer::Preprocessing, b"big", || Some("x".repeat(4096)));
    }

    /// The way out has to work, or the default is a trap rather than a choice.
    #[test]
    fn oversize_can_be_downgraded_to_a_warning() {
        let mut c = AlgebraCache::local(64 * 1024 * 1024).strict_oversize(false);
        c.max_value = 512;
        let big = "x".repeat(4096);
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"big", || Some(big.clone())),
            Some(big)
        );
        assert_eq!(c.stats[0].oversized, 1);
    }

    /// `IC_CACHE_STRICT_OVERSIZE` is an opt-OUT now, so only an explicitly
    /// falsey value disables it; unset must leave it on.
    #[test]
    fn the_env_opt_out_reads_only_falsey_values() {
        fn strict_for(value: Option<&str>) -> bool {
            !matches!(value, Some("0") | Some("false") | Some("no"))
        }
        assert!(strict_for(None), "unset must stay strict");
        assert!(strict_for(Some("1")));
        assert!(strict_for(Some("yes")));
        assert!(!strict_for(Some("0")));
        assert!(!strict_for(Some("false")));
        assert!(!strict_for(Some("no")));
    }

    #[test]
    #[cfg(feature = "redis-cache")]
    #[ignore = "needs IC_TEST_REDIS_URL pointing to a dedicated test Redis"]
    fn redis_cross_client_reuse_and_corruption() {
        let url = std::env::var("IC_TEST_REDIS_URL").unwrap();
        let key = format!("test-{}-{:?}", std::process::id(), Instant::now());
        let mut a = AlgebraCache::local(0).with_redis(&url).unwrap();
        let mut b = AlgebraCache::local(0).with_redis(&url).unwrap();
        assert_eq!(
            a.memoize(Layer::Preprocessing, key.as_bytes(), || Some(17u64)),
            Some(17)
        );
        assert_eq!(
            b.memoize(Layer::Preprocessing, key.as_bytes(), || panic!(
                "remote miss"
            )),
            Some(17u64)
        );
        assert_eq!(b.stats[0].redis_hits, 1);
        let redis_key = a.key(Layer::Preprocessing, key.as_bytes());
        let _: Option<()> = a.remote(redis::cmd("SET").arg(&redis_key).arg("bad"), 0);
        assert_eq!(
            b.memoize(Layer::Preprocessing, key.as_bytes(), || Some(18u64)),
            Some(18)
        );
        assert_eq!(b.stats[0].invalid, 1);
        let _: Option<()> = a.remote(redis::cmd("DEL").arg(&redis_key), 0);
    }
}
