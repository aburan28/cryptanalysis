-- Event-driven ECC2K-130 index. Safe to apply repeatedly.
--
-- S3 remains authoritative. These tables are an index and a commit ledger;
-- dropping them never loses the corpus.

CREATE TABLE IF NOT EXISTS distinguished_points (
    campaign_id text        NOT NULL,
    point_key   bytea       NOT NULL,
    a           bytea,
    b           bytea,
    walk_seed   bytea,
    worker_id   text        NOT NULL,
    found_at    timestamptz NOT NULL,
    PRIMARY KEY (campaign_id, point_key)
);

CREATE INDEX IF NOT EXISTS distinguished_points_campaign_found_at
    ON distinguished_points (campaign_id, found_at);

CREATE TABLE IF NOT EXISTS rho_collisions (
    campaign_id text        NOT NULL,
    point_key   bytea       NOT NULL,
    detected_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, point_key)
);

CREATE TABLE IF NOT EXISTS dp_ingest_progress (
    campaign_id text        NOT NULL,
    object_key  text        NOT NULL,
    records     bigint      NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, object_key)
);

CREATE TABLE IF NOT EXISTS dp_ingest_totals (
    campaign_id text PRIMARY KEY,
    dps         bigint NOT NULL DEFAULT 0,
    first_dp_at timestamptz,
    last_dp_at  timestamptz
);

CREATE TABLE IF NOT EXISTS dp_ingest_hourly (
    campaign_id text        NOT NULL,
    hour        timestamptz NOT NULL,
    dps         bigint      NOT NULL,
    PRIMARY KEY (campaign_id, hour)
);

-- The object has been fully verified and indexed when committed_at is set.
-- Insertion and indexing share one transaction, so an incomplete row cannot
-- survive a failed invocation.
CREATE TABLE IF NOT EXISTS ecc2k130_commits (
    campaign_id text        NOT NULL,
    object_key  text        NOT NULL,
    manifest_key text       NOT NULL,
    sha256      text        NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    bytes       bigint      NOT NULL CHECK (bytes > 0 AND bytes % 32 = 0),
    records     bigint      NOT NULL CHECK (records > 0),
    slot        integer     NOT NULL CHECK (slot BETWEEN 0 AND 65534),
    stream_id   text        NOT NULL CHECK (stream_id ~ '^[0-9a-f]{32}$'),
    byte_offset bigint      NOT NULL CHECK (byte_offset >= 0),
    produced_at timestamptz NOT NULL,
    added       bigint      NOT NULL DEFAULT 0,
    collisions  bigint      NOT NULL DEFAULT 0,
    committed_at timestamptz,
    PRIMARY KEY (campaign_id, object_key)
);

CREATE INDEX IF NOT EXISTS ecc2k130_commits_produced
    ON ecc2k130_commits (campaign_id, produced_at);

-- Compatible with the control-plane ledger in the live campaign. The event
-- consumer fills fence=0 because the S3 commit marker, not a slot lease, is
-- the authority for post-upload indexing.
CREATE TABLE IF NOT EXISTS rho_objects (
    campaign_id text    NOT NULL,
    object_key  text    NOT NULL,
    slot        integer NOT NULL,
    stream_id   text,
    byte_offset bigint  NOT NULL DEFAULT 0,
    bytes       bigint  NOT NULL DEFAULT 0,
    records     bigint  NOT NULL DEFAULT 0,
    sha256      text,
    fence       bigint  NOT NULL DEFAULT 0,
    uploaded_at bigint  NOT NULL DEFAULT 0,
    PRIMARY KEY (campaign_id, object_key)
);

CREATE INDEX IF NOT EXISTS rho_objects_slot
    ON rho_objects (campaign_id, slot, byte_offset);

CREATE INDEX IF NOT EXISTS rho_objects_uploaded
    ON rho_objects (campaign_id, uploaded_at);

-- Latest cumulative checkpoint per run id. Checkpoint headers carry both the
-- iteration base and walk geometry, so dashboard work no longer requires an
-- S3 prefix scan.
CREATE TABLE IF NOT EXISTS ecc2k130_checkpoints (
    campaign_id   text        NOT NULL,
    slot          integer     NOT NULL CHECK (slot BETWEEN 0 AND 65534),
    object_key    text        NOT NULL,
    sha256        text        NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    iteration_base bigint     NOT NULL CHECK (iteration_base >= 0),
    walks         bigint      NOT NULL CHECK (walks > 0),
    iterations    numeric(40) NOT NULL CHECK (iterations >= 0),
    produced_at   timestamptz NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, slot)
);

CREATE INDEX IF NOT EXISTS ecc2k130_checkpoints_produced
    ON ecc2k130_checkpoints (campaign_id, produced_at);

CREATE TABLE IF NOT EXISTS ecc2k130_checkpoint_objects (
    campaign_id   text        NOT NULL,
    object_key    text        NOT NULL,
    version_id    text        NOT NULL DEFAULT '',
    slot          integer     NOT NULL CHECK (slot BETWEEN 0 AND 65534),
    iteration_base bigint     NOT NULL CHECK (iteration_base >= 0),
    processed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, object_key, version_id)
);

-- Fleet status is read from the same fenced slot table used by the existing
-- ECC2K-130 control plane. The worker/control-plane migration may already
-- have created it; this definition is intentionally compatible.
CREATE TABLE IF NOT EXISTS rho_slots (
    campaign_id   text    NOT NULL,
    slot          integer NOT NULL,
    owner         text,
    lease_until   bigint  NOT NULL DEFAULT 0,
    fence         bigint  NOT NULL DEFAULT 0,
    state         text    NOT NULL DEFAULT 'idle',
    instance      text,
    gpu           integer,
    gpu_name      text,
    gpu_family    text,
    instance_type text,
    iters         bigint  NOT NULL DEFAULT 0,
    points        bigint  NOT NULL DEFAULT 0,
    reason        text,
    created_at    bigint  NOT NULL DEFAULT 0,
    claimed_at    bigint  NOT NULL DEFAULT 0,
    updated_at    bigint  NOT NULL DEFAULT 0,
    PRIMARY KEY (campaign_id, slot)
);

CREATE INDEX IF NOT EXISTS rho_slots_lease
    ON rho_slots (campaign_id, lease_until);
