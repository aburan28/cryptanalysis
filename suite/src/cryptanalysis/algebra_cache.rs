//! Separate caches for target-independent preprocessing and exact reductions.
//! Redis is a trusted, private computation cache, not a proof verifier. Checksums
//! detect accidental corruption; they do not authenticate a malicious writer.
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::{cell::RefCell, collections::VecDeque, sync::OnceLock, time::Instant};

#[derive(Clone, Copy)]
pub enum Layer {
    Preprocessing,
    ExactReduction,
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

pub struct AlgebraCache {
    enabled: [bool; 3],
    remote_enabled: [bool; 3],
    namespace: String,
    local: VecDeque<(String, Vec<u8>)>,
    local_bytes: usize,
    local_limit: usize,
    max_value: usize,
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
            include_str!("pq_groebner_f2.rs"),
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
    fn from_env() -> Self {
        let mut c = Self::local(32 * 1024 * 1024);
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
    fn retain(&mut self, key: String, bytes: Vec<u8>) {
        let size = key.len() + bytes.len() + 128;
        if size > self.local_limit {
            return;
        }
        if let Some(pos) = self.local.iter().position(|(k, _)| k == &key) {
            let (k, v) = self.local.remove(pos).unwrap();
            self.local_bytes -= k.len() + v.len() + 128;
        }
        while self.local_bytes + size > self.local_limit {
            let (k, v) = self.local.pop_front().unwrap();
            self.local_bytes -= k.len() + v.len() + 128;
        }
        self.local_bytes += size;
        self.local.push_back((key, bytes));
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
    /// Cache only successful computations; None is never an UNSAT certificate.
    pub fn memoize<T: Serialize + DeserializeOwned>(
        &mut self,
        layer: Layer,
        input: &[u8],
        compute: impl FnOnce() -> Option<T>,
    ) -> Option<T> {
        let start = Instant::now();
        let i = layer.index();
        let key = self.key(layer, input);
        self.stats[i].lookups += 1;
        let mut local_hit = false;
        let bytes = if let Some((_, v)) = self.local.iter().find(|(k, _)| k == &key) {
            local_hit = true;
            Some(v.clone())
        } else {
            #[cfg(feature = "redis-cache")]
            {
                self.remote::<Vec<u8>>(
                    redis::cmd("GETRANGE").arg(&key).arg(0).arg(self.max_value),
                    i,
                )
                .filter(|b| !b.is_empty())
            }
            #[cfg(not(feature = "redis-cache"))]
            {
                None
            }
        };
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
                if local_hit {
                    self.stats[i].local_hits += 1;
                } else {
                    self.stats[i].redis_hits += 1;
                }
                self.stats[i].bytes_read += bytes.len() as u64;
                self.retain(key, bytes);
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
                    self.retain(key, bytes);
                } else {
                    self.stats[i].oversized += 1;
                }
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
pub fn memoize<T: Serialize + DeserializeOwned>(
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
    fn bounded_storage_and_corruption_recompute() {
        let mut c = AlgebraCache::local(4096);
        c.memoize(Layer::Preprocessing, b"x", || Some(2u64));
        c.local.front_mut().unwrap().1[0] = b'!';
        assert_eq!(
            c.memoize(Layer::Preprocessing, b"x", || Some(3u64)),
            Some(3)
        );
        assert_eq!(c.stats[0].invalid, 1);
        for i in 0..100u64 {
            c.memoize(Layer::Preprocessing, &i.to_le_bytes(), || Some(i));
        }
        assert!(c.local_bytes <= 4096);
        let mut c = AlgebraCache::local(0);
        c.memoize(Layer::Preprocessing, b"x", || Some(2u64));
        assert!(c.local.is_empty());
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
