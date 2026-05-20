import argparse
import os
import sqlite3

from sqlalchemy import text as sql_text

from app import BASE_DIR, engine, metadata


TABLE_ORDER = ['users', 'novels', 'chapters', 'favorites', 'library', 'comments']


def sqlite_rows(sqlite_path, table_name):
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in source.execute(f"SELECT * FROM {table_name}").fetchall()]
    finally:
        source.close()


def target_count(conn, table_name):
    return conn.execute(sql_text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()


def reset_postgres_sequence(conn, table_name):
    conn.execute(sql_text(f"""
        SELECT setval(
            pg_get_serial_sequence('{table_name}', 'id'),
            GREATEST(COALESCE((SELECT MAX(id) FROM {table_name}), 0), 1),
            true
        )
    """))


def migrate(sqlite_path, replace):
    if engine.dialect.name != 'postgresql':
        raise SystemExit('Set SUPABASE_DATABASE_URL to your Supabase Postgres connection string before running this.')

    if not os.path.exists(sqlite_path):
        raise SystemExit(f'Source SQLite database was not found: {sqlite_path}')

    metadata.create_all(engine)

    with engine.begin() as conn:
        existing = {table: target_count(conn, table) for table in TABLE_ORDER}
        if any(existing.values()) and not replace:
            raise SystemExit(
                'Supabase already has data. Re-run with --replace to overwrite it, '
                'or leave it as-is to protect existing production data.'
            )

        if replace:
            for table in reversed(TABLE_ORDER):
                conn.execute(sql_text(f"DELETE FROM {table}"))

        for table_name in TABLE_ORDER:
            rows = sqlite_rows(sqlite_path, table_name)
            if rows:
                conn.execute(metadata.tables[table_name].insert(), rows)
            print(f'{table_name}: migrated {len(rows)} rows')

        for table_name in TABLE_ORDER:
            reset_postgres_sequence(conn, table_name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Copy local NovelVerse SQLite data into Supabase Postgres.')
    parser.add_argument(
        '--sqlite',
        default=os.path.join(BASE_DIR, 'novels.db'),
        help='Path to the source SQLite database. Defaults to novels.db in this project.',
    )
    parser.add_argument(
        '--replace',
        action='store_true',
        help='Delete existing Supabase rows before importing the SQLite data.',
    )
    args = parser.parse_args()
    migrate(args.sqlite, args.replace)
