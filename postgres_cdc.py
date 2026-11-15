import argparse
import json
import os

import psycopg2
from psycopg2 import sql
from psycopg2.extras import (
    REPLICATION_LOGICAL,
    LogicalReplicationConnection,
    RealDictCursor,
)

ACTIONS = {"I": "insert", "U": "update", "D": "delete", "T": "truncate"}


def emit(event):
    print(json.dumps(event, default=str, ensure_ascii=False), flush=True)


def cols_to_dict(cols):
    return {c["name"]: c["value"] for c in (cols or [])}


def snapshot(dsn, schema, tables, batch=1000):
    """Envia o conteúdo atual das tabelas (operation = 'snapshot')."""
    conn = psycopg2.connect(dsn)
    try:
        for i, table in enumerate(tables):
            with conn.cursor(name=f"snap_{i}", cursor_factory=RealDictCursor) as cur:
                cur.itersize = batch
                cur.execute(
                    sql.SQL("SELECT * FROM {}.{}").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
                )
                for row in cur:
                    emit(
                        {
                            "operation": "snapshot",
                            "schema": schema,
                            "table": table,
                            "data": dict(row),
                        }
                    )
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--schema", default=os.getenv("PG_SCHEMA", "public"))
    p.add_argument("--tables", required=True, help="separadas por vírgula, ex.: orders,customers")
    p.add_argument("--slot", default="py_cdc_slot")
    p.add_argument(
        "--snapshot",
        action="store_true",
        help="envia o estado atual das tabelas quando o slot é criado",
    )
    args = p.parse_args()

    dsn = os.environ["POSTGRES_DSN"]
    tables = [t.strip() for t in args.tables.split(",") if t.strip()]

    conn = psycopg2.connect(dsn, connection_factory=LogicalReplicationConnection)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_replication_slots WHERE slot_name = %s", (args.slot,))
    if cur.fetchone() is None:
        cur.create_replication_slot(
            args.slot, slot_type=REPLICATION_LOGICAL, output_plugin="wal2json"
        )
        if args.snapshot:
            snapshot(dsn, args.schema, tables)

    def handle(msg):
        change = json.loads(msg.payload)
        action = change.get("action")
        if action in ACTIONS:
            event = {
                "operation": ACTIONS[action],
                "schema": change.get("schema"),
                "table": change.get("table"),
                "data": cols_to_dict(change.get("columns") or change.get("identity")),
                "lsn": msg.data_start,
            }
            if action == "U":
                event["old"] = cols_to_dict(change.get("identity"))
            emit(event)
        msg.cursor.send_feedback(flush_lsn=msg.data_start)

    cur.start_replication(
        slot_name=args.slot,
        slot_type=REPLICATION_LOGICAL,
        decode=True,
        options={
            "format-version": "2",
            "include-transaction": "false",
            "actions": "insert,update,delete,truncate",
            "add-tables": ",".join(f"{args.schema}.{t}" for t in tables),
        },
    )

    try:
        cur.consume_stream(handle)
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()


if __name__ == "__main__":
    main()