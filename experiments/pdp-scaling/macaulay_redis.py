"""Optional Redis transport using the existing IC ElastiCache configuration.

Only immutable algebra artifacts are stored. Credentials and client exception
messages are never included in telemetry or warnings.
"""

from __future__ import annotations

import math
import os
import re
import time
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
import warnings


DEFAULT_NAMESPACE = "crypto:ic:groebner:v1"
DEFAULT_TTL_SECS = 7 * 24 * 60 * 60
DEFAULT_MAX_BYTES = 16 * 1024 * 1024


class RedisArtifactStore:
    """Bounded binary GETRANGE / atomic SET EX, with fail-open backoff."""

    def __init__(self, client, *, namespace=DEFAULT_NAMESPACE,
                 ttl_secs=DEFAULT_TTL_SECS, max_bytes=DEFAULT_MAX_BYTES):
        if not isinstance(namespace, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", namespace):
            raise ValueError("invalid Macaulay Redis namespace")
        if type(ttl_secs) is not int or ttl_secs <= 0:
            raise ValueError("Redis TTL must be a positive integer")
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("Redis entry limit must be a positive integer")
        self.client = client
        self.namespace = namespace
        self.ttl_secs = ttl_secs
        self.max_bytes = max_bytes
        self._retry_after = 0.0
        self.stats = dict.fromkeys((
            "read_attempts", "write_attempts", "hits", "misses", "writes",
            "read_errors", "write_errors", "config_errors", "invalid_entries",
            "oversize_skips", "backoff_skips", "bytes_read", "bytes_written",
        ), 0)
        self.stats.update({"enabled": client is not None,
                           "read_seconds": 0.0, "write_seconds": 0.0})

    @classmethod
    def from_environment(cls, environ=None):
        env = os.environ if environ is None else environ
        if env.get("IC_MACAULAY_CACHE", "auto").lower() == "off":
            return None
        if not any(env.get(name, "").strip() for name in (
                "IC_MACAULAY_CACHE_URL", "IC_MACAULAY_CACHE_HOST", "IC_GROEBNER_CACHE_URL")):
            return None

        def setting(suffix, default):
            return env.get("IC_MACAULAY_CACHE_" + suffix,
                           env.get("IC_GROEBNER_CACHE_" + suffix, default))

        try:
            url = cls._url_from_environment(env)
            namespace = setting("NAMESPACE", DEFAULT_NAMESPACE)
            ttl = int(setting("TTL_SECS", DEFAULT_TTL_SECS))
            max_bytes = int(setting("MAX_BYTES", DEFAULT_MAX_BYTES))
            timeout = float(env.get("IC_MACAULAY_CACHE_TIMEOUT_SECS", "0.25"))
            if not math.isfinite(timeout) or not 0 < timeout <= 5:
                raise ValueError("invalid Redis timeout")
            store = cls(None, namespace=namespace, ttl_secs=ttl, max_bytes=max_bytes)
            store.client = cls._client_from_url(url, timeout)
            store.stats["enabled"] = True
            return store
        except Exception:
            # Includes a missing optional redis-py dependency or bad URL. Do
            # not print exceptions: client errors can embed authentication URLs.
            store = cls(None)
            store.stats["config_errors"] = 1
            warnings.warn("Macaulay Redis cache configuration unavailable; "
                          "using local cache/computation", RuntimeWarning, stacklevel=2)
            return store

    @staticmethod
    def _url_from_environment(env):
        # Helm can inject a password directly from secretKeyRef, without
        # copying it into chart values or relying on unsafe URI substitution.
        url = env.get("IC_MACAULAY_CACHE_URL")
        host = env.get("IC_MACAULAY_CACHE_HOST")
        if not url and host:
            if any(c in host for c in "/?#@ \t\r\n"):
                raise ValueError("invalid Redis host")
            port = int(env.get("IC_MACAULAY_CACHE_PORT", "6379"))
            scheme = env.get("IC_MACAULAY_CACHE_SCHEME", "redis")
            if not 1 <= port <= 65535 or scheme not in ("redis", "rediss"):
                raise ValueError("invalid Redis port or scheme")
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            password = env.get("IC_MACAULAY_CACHE_PASSWORD")
            auth = ""
            if password is not None:
                username = env.get("IC_MACAULAY_CACHE_USERNAME", "default")
                auth = f"{quote(username, safe='')}:{quote(password, safe='')}@"
            url = f"{scheme}://{auth}{host}:{port}/0"
        url = url or env.get("IC_GROEBNER_CACHE_URL")
        ca_cert = env.get("IC_MACAULAY_CACHE_CA_CERT")
        if ca_cert:
            parts = urlsplit(url)
            if parts.scheme != "rediss":
                raise ValueError("Redis CA certificate requires TLS")
            query = dict(parse_qsl(parts.query, keep_blank_values=True))
            query["ssl_ca_certs"] = ca_cert
            url = urlunsplit(parts._replace(query=urlencode(query)))
        return url

    @staticmethod
    def _client_from_url(url, timeout):
        scheme = urlsplit(url).scheme
        if scheme not in ("redis", "rediss", "unix"):
            raise ValueError("unsupported Redis URL scheme")
        import redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        options = dict(
            decode_responses=False, socket_timeout=timeout,
            socket_connect_timeout=timeout, retry=Retry(NoBackoff(), 0),
            retry_on_timeout=False, retry_on_error=[], health_check_interval=0,
            protocol=2,
        )
        if scheme == "rediss":
            options.update(ssl_cert_reqs="required", ssl_check_hostname=True)
        # URL options take precedence over kwargs in redis-py. Remove enforced
        # options before construction: changing protocol afterwards leaves
        # redis-py 8 TCP pools with incompatible maintenance-notification state.
        parts = urlsplit(url)
        query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                 if key not in options]
        url = urlunsplit(parts._replace(query=urlencode(query)))
        if scheme == "unix" and not url.startswith("unix://"):
            # urlunsplit removes the empty authority for nonstandard schemes;
            # redis-py requires the unix:// prefix even for a local socket.
            url = "unix://" + url[len("unix:"):]
        pool = redis.ConnectionPool.from_url(url, **options)
        return redis.Redis(connection_pool=pool)

    def key(self, digest: str, schema: int) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid Macaulay cache digest")
        return f"{self.namespace}:macaulay:v{schema}:{digest}"

    def _ready(self) -> bool:
        if self.client is None:
            return False
        if time.monotonic() < self._retry_after:
            self.stats["backoff_skips"] += 1
            return False
        return True

    def get(self, key: str, limit: int):
        if not self._ready():
            return None
        limit = min(limit, self.max_bytes)
        started = time.perf_counter()
        self.stats["read_attempts"] += 1
        try:
            # Inclusive end reads one extra byte to detect oversize values
            # without downloading an arbitrarily large remote string.
            value = self.client.getrange(key, 0, limit)
            if not isinstance(value, bytes):
                self.stats["invalid_entries"] += 1
                return None
            self.stats["bytes_read"] += len(value)
            if len(value) > limit:
                self.stats["oversize_skips"] += 1
                self.stats["invalid_entries"] += 1
                return None
            if not value:
                self.stats["misses"] += 1
                return None
            return value
        except Exception:
            self.stats["read_errors"] += 1
            self._retry_after = time.monotonic() + 5
            return None
        finally:
            self.stats["read_seconds"] += time.perf_counter() - started

    def put(self, key: str, value: bytes) -> None:
        if len(value) > self.max_bytes:
            self.stats["oversize_skips"] += 1
            return
        if not self._ready():
            return
        started = time.perf_counter()
        self.stats["write_attempts"] += 1
        try:
            if not self.client.set(key, value, ex=self.ttl_secs):
                raise OSError("cache write was not confirmed")
            self.stats["writes"] += 1
            self.stats["bytes_written"] += len(value)
        except Exception:
            self.stats["write_errors"] += 1
            self._retry_after = time.monotonic() + 5
        finally:
            self.stats["write_seconds"] += time.perf_counter() - started
