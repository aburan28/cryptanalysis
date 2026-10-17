"""Read-only ECC2K-130 ingest status; prints no connection secret."""

import psycopg
import dp_ingest

with psycopg.connect(dp_ingest.databaseUrl(), connect_timeout=10) as conn:
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = '5s'")
        cur.execute(
            "SELECT dps, last_dp_at FROM dp_ingest_totals "
            "WHERE campaign_id = %s", (dp_ingest.CAMPAIGN,)
        )
        print("totals", cur.fetchone(), flush=True)
        cur.execute(
            "SELECT state, wait_event_type, wait_event, count(*), "
            "max(extract(epoch from now() - query_start))::int "
            "FROM pg_stat_activity WHERE datname = current_database() "
            "GROUP BY 1, 2, 3 ORDER BY 4 DESC"
        )
        for row in cur.fetchall():
            print("activity", row, flush=True)
