import os
import sqlite3

from sqlalchemy import create_engine, MetaData, Table, select, text


SQLITE_URL = "sqlite:///./siteaegis.db"
POSTGRES_URL = os.environ["DATABASE_URL"]


def main():
    print("=" * 70)
    print("SITEAEGIS SQLITE -> POSTGRESQL MIGRATION")
    print("=" * 70)

    sqlite_engine = create_engine(SQLITE_URL)
    postgres_engine = create_engine(POSTGRES_URL)

    metadata = MetaData()
    metadata.reflect(bind=postgres_engine)

    tables = [
        metadata.tables["sites"],
        metadata.tables["cameras"],
        metadata.tables["zones"],
        metadata.tables["scans"],
        metadata.tables["monitoring_events"],
        metadata.tables["alerts"],
        metadata.tables["safety_events"],
        metadata.tables["incidents"],
    ]

    print("\n[1/4] PostgreSQL tables detected:")
    for table in tables:
        print(f"  - {table.name}")

    print("\n[2/4] Reading SQLite data...")

    with sqlite_engine.connect() as sqlite_conn:
        source_data = {}

        for table in tables:
            result = sqlite_conn.execute(select(table))
            rows = result.mappings().all()
            source_data[table.name] = rows
            print(f"  {table.name}: {len(rows)} rows")

    print("\n[3/4] Migrating data to PostgreSQL...")

    with postgres_engine.begin() as pg_conn:
        for table in tables:
            rows = source_data[table.name]

            if not rows:
                print(f"  {table.name}: 0 rows - skipped")
                continue

            pg_conn.execute(table.insert(), [dict(row) for row in rows])
            print(f"  {table.name}: {len(rows)} rows migrated")

    print("\n[4/4] Resetting PostgreSQL sequences...")

    with postgres_engine.begin() as pg_conn:
        for table in tables:
            try:
                for column in table.columns:
                    if column.autoincrement:
                        sequence_sql = text(
                            """
                            SELECT setval(
                                pg_get_serial_sequence(:table_name, :column_name),
                                COALESCE(
                                    (SELECT MAX(id) FROM """
                            + table.name
                            + """),
                                    1
                                ),
                                true
                            )
                            """
                        )

                        pg_conn.execute(
                            sequence_sql,
                            {
                                "table_name": table.name,
                                "column_name": column.name,
                            },
                        )
            except Exception as exc:
                print(
                    f"  Sequence reset warning for {table.name}: {exc}"
                )

    print("\n" + "=" * 70)
    print("MIGRATION COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()
