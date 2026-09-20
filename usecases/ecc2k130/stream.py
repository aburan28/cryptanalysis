"""Durable Redis Streams queue and backpressure for ECC2K-130 object refs.

The stream carries S3 object references, never distinguished-point bytes.
Workers keep bytes in their local spool until ``publish()`` succeeds. Consumers
ACK and delete an entry atomically only after the RDS transaction commits.
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import dataclass

from handler import CHECKPOINT_KEY_RE, MAX_SLOT, parse_object_key

ENQUEUE_LUA = """
local existing = redis.call('HGET', KEYS[4], ARGV[10])
if existing then
  return {'DUPLICATE', existing, redis.call('HGET', KEYS[3], 'state') or 'green'}
end
local state = redis.call('HGET', KEYS[3], 'state') or 'green'
local messages = redis.call('XLEN', KEYS[1])
local bytes = tonumber(redis.call('HGET', KEYS[2], 'bytes') or '0')
local offered_bytes = tonumber(ARGV[5])
local object_bytes = tonumber(ARGV[13])
local offered_records = tonumber(ARGV[6])
if not offered_bytes or not object_bytes or not offered_records
   or offered_bytes <= 0 or object_bytes <= 0 or offered_records < 0
   or (ARGV[3] == 'dp' and (offered_records <= 0
       or object_bytes ~= offered_records * 32 or offered_bytes ~= object_bytes))
   or (ARGV[3] == 'dp' and object_bytes > tonumber(ARGV[11]))
   or (ARGV[3] == 'checkpoint'
       and (object_bytes < 40 or object_bytes > tonumber(ARGV[12])
            or offered_bytes ~= 40)) then
  return {'INVALID', state, tostring(messages), tostring(bytes)}
end
if state == 'red'
   or messages >= tonumber(ARGV[7])
   or bytes + offered_bytes > tonumber(ARGV[8]) then
  return {'BACKPRESSURE', state, tostring(messages), tostring(bytes)}
end
local id = redis.call(
  'XADD', KEYS[1], '*',
  'bucket', ARGV[1], 'key', ARGV[2], 'kind', ARGV[3],
  'eventTime', ARGV[4], 'bytes', ARGV[5], 'records', ARGV[6],
  'versionId', ARGV[9], 'identity', ARGV[10], 'objectBytes', ARGV[13])
redis.call('HINCRBY', KEYS[2], 'messages', 1)
redis.call('HINCRBY', KEYS[2], 'bytes', ARGV[5])
redis.call('HINCRBY', KEYS[2], 'records', ARGV[6])
redis.call('HINCRBY', KEYS[2], 'enqueued', 1)
redis.call('HSET', KEYS[4], ARGV[10], id)
return {'OK', id, state}
"""

ACK_LUA = """
local acked = redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
if acked == 1 then
  redis.call('XDEL', KEYS[1], ARGV[2])
  local messages = tonumber(redis.call('HGET', KEYS[2], 'messages') or '0')
  local bytes = tonumber(redis.call('HGET', KEYS[2], 'bytes') or '0')
  local records = tonumber(redis.call('HGET', KEYS[2], 'records') or '0')
  redis.call('HSET', KEYS[2],
    'messages', math.max(0, messages - 1),
    'bytes', math.max(0, bytes - tonumber(ARGV[3])),
    'records', math.max(0, records - tonumber(ARGV[4])))
  redis.call('HINCRBY', KEYS[2], 'acked', 1)
  redis.call('HDEL', KEYS[3], ARGV[5])
end
return acked
"""

DEAD_LETTER_LUA = """
local pending = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[2], ARGV[2], 1)
if #pending == 0 or pending[1][2] ~= ARGV[3] then
  return {'0', ''}
end
local dlq = redis.call(
  'XADD', KEYS[3], '*',
  'sourceId', ARGV[2], 'bucket', ARGV[6], 'key', ARGV[7],
  'kind', ARGV[8], 'eventTime', ARGV[9], 'bytes', ARGV[4],
  'records', ARGV[5], 'versionId', ARGV[10], 'identity', ARGV[11],
  'error', ARGV[12], 'objectBytes', ARGV[13], 'failedAt', redis.call('TIME')[1])
local acked = redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
if acked == 1 then
  redis.call('XDEL', KEYS[1], ARGV[2])
  local messages = tonumber(redis.call('HGET', KEYS[2], 'messages') or '0')
  local bytes = tonumber(redis.call('HGET', KEYS[2], 'bytes') or '0')
  local records = tonumber(redis.call('HGET', KEYS[2], 'records') or '0')
  redis.call('HSET', KEYS[2],
    'messages', math.max(0, messages - 1),
    'bytes', math.max(0, bytes - tonumber(ARGV[4])),
    'records', math.max(0, records - tonumber(ARGV[5])))
  redis.call('HINCRBY', KEYS[2], 'deadLettered', 1)
  redis.call('HSET', KEYS[4], ARGV[11], 'dead:' .. dlq)
end
return {tostring(acked), dlq}
"""

PRESSURE_LUA = """
local previous = tonumber(redis.call('HGET', KEYS[1], 'version') or '0')
local offered = tonumber(ARGV[1])
if offered <= previous then
  return 0
end
redis.call('HSET', KEYS[1], 'version', offered)
for i = 2, #ARGV, 2 do
  redis.call('HSET', KEYS[1], ARGV[i], ARGV[i + 1])
end
return 1
"""

TIME_LUA = "return redis.call('TIME')"


class Backpressure(RuntimeError):
    """The producer must retain its spool entry and retry later."""

    def __init__(self, state, messages, queued_bytes):
        self.state = state
        self.messages = int(messages)
        self.queued_bytes = int(queued_bytes)
        super().__init__(
            f"Redis queue is {state} ({self.messages} messages, "
            f"{self.queued_bytes} bytes); retain spool and retry"
        )


class PermanentMessageError(RuntimeError):
    """The queued reference is deterministic poison, not an outage."""


@dataclass(frozen=True)
class QueueConfig:
    campaign: str = "ecc2k-130"
    redis_url: str = ""
    backend: str = "memorydb"
    cluster: bool = True
    consumer: str = ""
    block_ms: int = 5000
    batch_size: int = 8
    claim_idle_ms: int = 60000
    max_deliveries: int = 8
    max_dp_bytes: int = 8 * 1024**2
    max_checkpoint_bytes: int = 16 * 1024**3
    high_messages: int = 10000
    critical_messages: int = 50000
    high_bytes: int = 2 * 1024**3
    critical_bytes: int = 6 * 1024**3
    high_age_seconds: int = 300
    critical_age_seconds: int = 1800
    high_memory_ratio: float = 0.70
    critical_memory_ratio: float = 0.85

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env

        def text(name, default=""):
            return (env.get(name) or default).strip()

        def integer(name, default):
            return int(text(name, str(default)))

        def ratio(name, default):
            return float(text(name, str(default)))

        def flag(name, default):
            raw = text(name, "1" if default else "0").lower()
            return raw in ("1", "true", "yes", "on")

        consumer = text("RHO_QUEUE_CONSUMER")
        if not consumer:
            consumer = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        return cls(
            campaign=text("RHO_CAMPAIGN", "ecc2k-130"),
            redis_url=text("RHO_QUEUE_REDIS_URL"),
            backend=text("RHO_QUEUE_BACKEND", "memorydb"),
            cluster=flag("RHO_QUEUE_CLUSTER", True),
            consumer=consumer,
            block_ms=integer("RHO_QUEUE_BLOCK_MS", 5000),
            batch_size=integer("RHO_QUEUE_BATCH_SIZE", 8),
            claim_idle_ms=integer("RHO_QUEUE_CLAIM_IDLE_MS", 60000),
            max_deliveries=integer("RHO_QUEUE_MAX_DELIVERIES", 8),
            max_dp_bytes=integer("RHO_QUEUE_MAX_DP_BYTES", 8 * 1024**2),
            max_checkpoint_bytes=integer(
                "RHO_QUEUE_MAX_CHECKPOINT_BYTES", 16 * 1024**3
            ),
            high_messages=integer("RHO_QUEUE_HIGH_MESSAGES", 10000),
            critical_messages=integer("RHO_QUEUE_CRITICAL_MESSAGES", 50000),
            high_bytes=integer("RHO_QUEUE_HIGH_BYTES", 2 * 1024**3),
            critical_bytes=integer("RHO_QUEUE_CRITICAL_BYTES", 6 * 1024**3),
            high_age_seconds=integer("RHO_QUEUE_HIGH_AGE_SECONDS", 300),
            critical_age_seconds=integer("RHO_QUEUE_CRITICAL_AGE_SECONDS", 1800),
            high_memory_ratio=ratio("RHO_QUEUE_HIGH_MEMORY_RATIO", 0.70),
            critical_memory_ratio=ratio(
                "RHO_QUEUE_CRITICAL_MEMORY_RATIO", 0.85
            ),
        )

    def validate(self):
        if not self.redis_url:
            raise ValueError("RHO_QUEUE_REDIS_URL is required")
        if self.backend not in ("memorydb", "standalone"):
            raise ValueError("RHO_QUEUE_BACKEND must be memorydb or standalone")
        for high, critical, name in (
            (self.high_messages, self.critical_messages, "messages"),
            (self.high_bytes, self.critical_bytes, "bytes"),
            (self.high_age_seconds, self.critical_age_seconds, "age"),
            (self.high_memory_ratio, self.critical_memory_ratio, "memory ratio"),
        ):
            if high <= 0 or critical <= high:
                raise ValueError(
                    f"queue {name} thresholds require 0 < high < critical"
                )
        if (
            self.batch_size <= 0
            or self.max_deliveries <= 0
            or self.max_dp_bytes <= 0
            or self.max_checkpoint_bytes <= 0
        ):
            raise ValueError("batch, delivery, and object limits must be positive")

    @property
    def tag(self):
        return f"rho:{{{self.campaign}}}:dp"

    @property
    def stream(self):
        return self.tag + ":ready"

    @property
    def group(self):
        return "indexers"

    @property
    def stats(self):
        return self.tag + ":stats"

    @property
    def pressure(self):
        return self.tag + ":pressure"

    @property
    def dead_letter(self):
        return self.tag + ":dead"

    @property
    def queued(self):
        return self.tag + ":queued"

    @property
    def pressure_sequence(self):
        return self.tag + ":pressure:sequence"


def pressure_state(snapshot, config):
    """Classify lag; red means producers must stop clearing their spool."""
    red = (
        snapshot["messages"] >= config.critical_messages
        or snapshot["bytes"] >= config.critical_bytes
        or snapshot["oldestAgeSeconds"] >= config.critical_age_seconds
        or snapshot["memoryRatio"] >= config.critical_memory_ratio
    )
    if red:
        return "red"
    yellow = (
        snapshot["messages"] >= config.high_messages
        or snapshot["bytes"] >= config.high_bytes
        or snapshot["oldestAgeSeconds"] >= config.high_age_seconds
        or snapshot["memoryRatio"] >= config.high_memory_ratio
    )
    return "yellow" if yellow else "green"


def _text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def _mapping(values):
    return {_text(key): _text(value) for key, value in values.items()}


class RedisStreamQueue:
    """One durable stream and consumer group."""

    def __init__(self, client, config=None, clock=time.time):
        self.client = client
        self.config = config or QueueConfig.from_env()
        self.config.validate()
        self.clock = clock
        self._enqueue = client.register_script(ENQUEUE_LUA)
        self._ack = client.register_script(ACK_LUA)
        self._dead_letter = client.register_script(DEAD_LETTER_LUA)
        self._pressure = client.register_script(PRESSURE_LUA)
        self._time = client.register_script(TIME_LUA)
        self._claim_cursor = "0-0"

    @classmethod
    def from_env(cls, config=None):
        config = config or QueueConfig.from_env()
        config.validate()
        import redis

        client_type = redis.RedisCluster if config.cluster else redis.Redis
        client = client_type.from_url(
            config.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=10,
            health_check_interval=30,
            retry_on_timeout=False,
        )
        queue = cls(client, config)
        queue.validate_server()
        return queue

    def ensure_group(self):
        try:
            self.client.xgroup_create(
                self.config.stream, self.config.group, id="0-0", mkstream=True
            )
            return True
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise
            return False

    def _memory_info(self):
        kwargs = {}
        if self.config.cluster and hasattr(self.client, "get_primaries"):
            kwargs["target_nodes"] = list(self.client.get_primaries())
        raw = self.client.info("memory", **kwargs)
        if "used_memory" in raw:
            nodes = [raw]
        else:
            nodes = [
                value
                for value in raw.values()
                if isinstance(value, dict) and "used_memory" in value
            ]
        if not nodes:
            raise RuntimeError("Redis did not return memory information")
        policies = {str(node.get("maxmemory_policy") or "") for node in nodes}
        ratios = [
            float(node.get("used_memory") or 0) / int(node.get("maxmemory") or 1)
            for node in nodes
            if int(node.get("maxmemory") or 0) > 0
        ]
        return {
            "used_memory": sum(int(node.get("used_memory") or 0) for node in nodes),
            "maxmemory": sum(int(node.get("maxmemory") or 0) for node in nodes),
            "maxmemory_policy": (
                policies.pop() if len(policies) == 1 else ",".join(sorted(policies))
            ),
            "max_memory_ratio": max(ratios, default=0.0),
        }

    def validate_server(self):
        """Fail closed when a production queue can evict accepted entries."""
        if self.config.backend == "standalone":
            return True
        memory = self._memory_info()
        if memory["maxmemory"] <= 0:
            raise RuntimeError("durable queue requires a finite Redis maxmemory")
        if memory["maxmemory_policy"] != "noeviction":
            raise RuntimeError(
                "durable queue requires maxmemory-policy=noeviction, got "
                f"{memory['maxmemory_policy']!r}"
            )
        return True

    def publish(
        self,
        bucket,
        key,
        *,
        size=0,
        records=0,
        event_time=None,
        version_id="",
    ):
        """Enqueue after S3 succeeds; a red queue raises before accepting it."""
        if key.endswith(".bin"):
            parse_object_key(key)
            kind = "dp"
        elif key.endswith(".ck") and CHECKPOINT_KEY_RE.fullmatch(key):
            kind = "checkpoint"
        else:
            raise ValueError(f"unsupported ECC2K-130 object key: {key}")
        size = int(size)
        records = int(records)
        if size <= 0 or size > 2**63 - 1 or records < 0 or records > 2**63 - 1:
            raise ValueError("object bytes/records are outside signed 64-bit bounds")
        if kind == "dp" and (records <= 0 or size != records * 32):
            raise ValueError("DP queue metadata requires bytes == records * 32")
        if kind == "dp" and size > self.config.max_dp_bytes:
            raise ValueError(
                f"DP object exceeds {self.config.max_dp_bytes} byte limit"
            )
        if kind == "checkpoint" and (size < 40 or records != 0):
            raise ValueError("checkpoint queue metadata requires bytes >= 40, records == 0")
        if kind == "checkpoint" and size > self.config.max_checkpoint_bytes:
            raise ValueError(
                "checkpoint object exceeds "
                f"{self.config.max_checkpoint_bytes} byte limit"
            )
        checkpoint_match = CHECKPOINT_KEY_RE.fullmatch(key)
        if checkpoint_match and int(checkpoint_match.group(1)) > MAX_SLOT:
            raise ValueError("checkpoint slot exceeds the 16-bit run-id space")
        if (
            kind == "checkpoint"
            and checkpoint_match.group(2) is None
            and (not version_id or version_id == "null")
        ):
            raise ValueError("mutable checkpoint keys require an S3 VersionId")
        if kind != "checkpoint" or checkpoint_match.group(2) is not None:
            version_id = ""
        queue_bytes = size if kind == "dp" else 40
        identity = json.dumps(
            [bucket, key, version_id], separators=(",", ":"), ensure_ascii=True
        )
        # Producers refresh pressure too. If every consumer is down, memory
        # and age still move toward red instead of leaving a stale green hash.
        self.refresh_pressure()
        event_time = event_time or time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock())
        )
        response = self._enqueue(
            keys=[
                self.config.stream,
                self.config.stats,
                self.config.pressure,
                self.config.queued,
            ],
            args=[
                bucket,
                key,
                kind,
                event_time,
                queue_bytes,
                records,
                self.config.critical_messages,
                self.config.critical_bytes,
                version_id,
                identity,
                self.config.max_dp_bytes,
                self.config.max_checkpoint_bytes,
                size,
            ],
        )
        values = [_text(value) for value in response]
        if values[0] == "BACKPRESSURE":
            raise Backpressure(values[1], values[2], values[3])
        if values[0] == "INVALID":
            raise ValueError("Redis rejected invalid queue metadata")
        return {
            "id": values[1],
            "pressure": values[2],
            "duplicate": values[0] == "DUPLICATE",
        }

    def refresh_pressure(self):
        observed_version = int(self.client.incr(self.config.pressure_sequence))
        server_time = self._time(keys=[self.config.pressure], args=[])
        seconds, micros = (int(_text(value)) for value in server_time)
        now_float = float(seconds) + float(micros) / 1_000_000
        length = int(self.client.xlen(self.config.stream))
        raw = _mapping(self.client.hgetall(self.config.stats))
        queued_bytes = max(0, int(raw.get("bytes") or 0))
        queued_records = max(0, int(raw.get("records") or 0))
        try:
            pending = self.client.xpending(self.config.stream, self.config.group)
        except Exception as exc:
            if "NOGROUP" not in str(exc):
                raise
            pending = {}
        pending_count = int((pending or {}).get("pending") or 0)
        first = self.client.xrange(self.config.stream, min="-", max="+", count=1)
        oldest_age = 0
        if first:
            millis = int(_text(first[0][0]).split("-", 1)[0])
            oldest_age = max(0, int(now_float - millis / 1000.0))
        memory = self._memory_info()
        used = int(memory["used_memory"])
        maximum = int(memory["maxmemory"])
        memory_ratio = float(memory["max_memory_ratio"])
        now = seconds
        snapshot = {
            "messages": length,
            "pending": pending_count,
            "bytes": queued_bytes,
            "records": queued_records,
            "oldestAgeSeconds": oldest_age,
            "memoryBytes": used,
            "maxMemoryBytes": maximum,
            "memoryRatio": memory_ratio,
            "deadLetters": int(self.client.xlen(self.config.dead_letter)),
            "updatedAt": now,
        }
        snapshot["state"] = pressure_state(snapshot, self.config)
        self.client.hset(self.config.stats, mapping={"messages": length})
        pressure_args = [observed_version]
        for key, value in snapshot.items():
            pressure_args.extend(
                [key, json.dumps(value) if isinstance(value, float) else value]
            )
        self._pressure(
            keys=[self.config.pressure],
            args=pressure_args,
        )
        return snapshot

    def ack(self, message_id, fields):
        values = _mapping(fields)
        return bool(
            int(
                self._ack(
                    keys=[self.config.stream, self.config.stats, self.config.queued],
                    args=[
                        self.config.group,
                        message_id,
                        int(values.get("bytes") or 0),
                        int(values.get("records") or 0),
                        values.get("identity") or "",
                    ],
                )
            )
        )

    def delivery_count(self, message_id):
        rows = self.client.xpending_range(
            self.config.stream,
            self.config.group,
            min=message_id,
            max=message_id,
            count=1,
        )
        if not rows:
            return 0
        row = rows[0]
        return int(row.get("times_delivered") or row.get("times-delivered") or 0)

    def dead_letter(self, message_id, fields, error):
        values = _mapping(fields)
        result = self._dead_letter(
            keys=[
                self.config.stream,
                self.config.stats,
                self.config.dead_letter,
                self.config.queued,
            ],
            args=[
                self.config.group,
                message_id,
                self.config.consumer,
                int(values.get("bytes") or 0),
                int(values.get("records") or 0),
                values.get("bucket") or "",
                values.get("key") or "",
                values.get("kind") or "",
                values.get("eventTime") or "",
                values.get("versionId") or "",
                values.get("identity") or "",
                str(error)[:1024],
                int(values.get("objectBytes") or values.get("bytes") or 0),
            ],
        )
        return {"acked": bool(int(_text(result[0]))), "deadLetterId": _text(result[1])}

    def claim_stale(self):
        result = self.client.xautoclaim(
            self.config.stream,
            self.config.group,
            self.config.consumer,
            min_idle_time=self.config.claim_idle_ms,
            start_id=self._claim_cursor,
            count=self.config.batch_size,
        )
        if result:
            self._claim_cursor = _text(result[0])
        return result[1] if result and len(result) > 1 else []

    def read_new(self):
        rows = self.client.xreadgroup(
            self.config.group,
            self.config.consumer,
            {self.config.stream: ">"},
            count=self.config.batch_size,
            block=self.config.block_ms,
        )
        return rows[0][1] if rows else []


class StreamConsumer:
    """Recover pending entries, consume new ones, and ACK only after success."""

    def __init__(self, queue):
        self.queue = queue
        self.queue.ensure_group()

    def consume_once(self, process, permanent=None):
        permanent = permanent or (lambda exc: isinstance(exc, PermanentMessageError))
        self.queue.refresh_pressure()
        messages = self.queue.claim_stale()
        if not messages:
            messages = self.queue.read_new()
        results = []
        for message_id, fields in messages:
            message_id = _text(message_id)
            values = _mapping(fields)
            try:
                result = process(values)
            except Exception as exc:  # noqa: BLE001 - pending retry/DLQ is the policy
                deliveries = self.queue.delivery_count(message_id)
                if permanent(exc) and deliveries >= self.queue.config.max_deliveries:
                    dead = self.queue.dead_letter(message_id, values, exc)
                    status = "dead-letter" if dead["acked"] else "stale-owner"
                    results.append(
                        {
                            "id": message_id,
                            "status": status,
                            "error": str(exc),
                            **dead,
                        }
                    )
                else:
                    results.append(
                        {
                            "id": message_id,
                            "status": "retry",
                            "deliveries": deliveries,
                            "error": str(exc),
                        }
                    )
                continue
            self.queue.ack(message_id, values)
            results.append({"id": message_id, "status": "acked", "result": result})
        pressure = self.queue.refresh_pressure()
        return {"messages": results, "pressure": pressure}
