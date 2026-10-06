"""Apply and verify the ECC2K-130 RDS schema."""

from pathlib import Path

from handler import Config, PostgresIndex, database_url

MIGRATION_LOCK = 0x454343324B313330


def main():
    import boto3
    import psycopg

    config = Config.from_env()
    if not config.db_url and not config.db_host:
        raise SystemExit("set DATABASE_URL, or RHO_DB_HOST plus RHO_DB_SECRET")
    url = database_url(config, boto3.client("secretsmanager"))
    connection = psycopg.connect(url, connect_timeout=30, autocommit=False)
    try:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
            cur.execute(schema)
        connection.commit()
        PostgresIndex(connection, config.campaign).assert_schema()
    finally:
        connection.close()
    print("ECC2K-130 schema is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
