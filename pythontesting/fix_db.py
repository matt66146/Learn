"""fix_db.py

Detects missing columns on the User table and adds them using ALTER TABLE.
Run with the project's Python environment, for example:

  venv/Scripts/python.exe fix_db.py
"""

from app import app, db, User
from sqlalchemy import text

EXPECTED_COLUMNS = {
    'failed_logins': "INTEGER NOT NULL DEFAULT 0",
    'last_failed_at': "DATETIME",
    'locked_until': "DATETIME",
}


def get_existing_columns(table_name: str):
    q = text(f"PRAGMA table_info('{table_name}')")
    rows = db.session.execute(q).fetchall()
    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
    return [row[1] for row in rows]


def add_column(table_name: str, column_name: str, column_type_sql: str):
    stmt = text(
        f"ALTER TABLE '{table_name}' ADD COLUMN {column_name} {column_type_sql}")
    print(f"Adding column {column_name} to {table_name} ({column_type_sql})")
    db.session.execute(stmt)
    db.session.commit()


def main():
    table_name = User.__table__.name
    print(f"Checking table: {table_name}")
    with app.app_context():
        existing = get_existing_columns(table_name)
        print("Existing columns:", existing)

        added = []
        for col, col_sql in EXPECTED_COLUMNS.items():
            if col not in existing:
                add_column(table_name, col, col_sql)
                added.append(col)
            else:
                print(f"Column {col} already exists")

        if added:
            print("Added columns:", added)
        else:
            print("No columns needed to be added.")


if __name__ == '__main__':
    main()
