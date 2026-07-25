"""
File: database.py

Purpose:
Database engine, session factory, declarative Base, and schema bootstrap.

Schema note:
`create_all` creates missing *tables* but never alters existing ones. This
project gained columns on `flashcards` and `qa_pairs` after those tables were
already live, so `sync_schema()` adds any missing columns in place. It is
idempotent and additive only - it never drops or retypes anything. Swap it for
Alembic migrations if this ever needs to run against data you cannot rebuild.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

# SINGLE Base (IMPORTANT)
Base = declarative_base()

# Import models after Base exists so SQLAlchemy can register metadata
from ..models import *  # noqa: E402,F401,F403

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables defined on Base."""
    Base.metadata.create_all(bind=engine)


def sync_schema():
    """
    Add columns that exist on the models but not yet in the database.

    Columns are added as NULLable even when the model marks them NOT NULL:
    existing rows have no value for them, and the ORM default fills new rows.
    Returns the list of "table.column" additions applied.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    applied = []

    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all handles brand-new tables

            present = {col["name"] for col in inspector.get_columns(table.name)}

            for column in table.columns:
                if column.name in present:
                    continue

                try:
                    type_sql = column.type.compile(dialect=engine.dialect)
                except Exception:
                    print(f"[schema] skipping {table.name}.{column.name}: uncompilable type")
                    continue

                connection.execute(
                    text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {type_sql}')
                )
                applied.append(f"{table.name}.{column.name}")

                # Backfill a sensible value so NOT NULL model fields are not
                # read back as None on pre-existing rows.
                default = getattr(column.default, "arg", None)
                if default is not None and not callable(default):
                    connection.execute(
                        text(
                            f'UPDATE {table.name} SET "{column.name}" = :value '
                            f'WHERE "{column.name}" IS NULL'
                        ),
                        {"value": default},
                    )

    if applied:
        print(f"[schema] added columns: {', '.join(applied)}")

    return applied


def init_db():
    """Create tables then reconcile columns. Safe to call on every startup."""
    create_tables()
    sync_schema()
