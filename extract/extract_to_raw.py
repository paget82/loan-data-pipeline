"""
Extraction layer of the pipeline.

Reads CSV files from data/raw/ and loads them into PostgreSQL into the
`raw` schema (without any transformation -- that's the job of the dbt
staging models).

Run:
    python extract/extract_to_raw.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

DB_USER = os.getenv("DB_USER", "dwh_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "dwh_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "loan_dwh")

CONNECTION_STRING = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

TABLES = ["clients", "loans", "transactions"]


def get_engine():
    return create_engine(CONNECTION_STRING)


def ensure_schema(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))


def load_table(engine, table_name: str):
    csv_path = RAW_DATA_DIR / f"{table_name}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Could not find {csv_path}. Run generator/generate_data.py first."
        )

    df = pd.read_csv(csv_path)

    # Explicitly drop the table with CASCADE so the run doesn't fail if
    # dbt staging views from a previous pipeline run depend on it.
    # (pandas to_sql(if_exists="replace") does a plain DROP TABLE without CASCADE.)
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS raw.{table_name} CASCADE;"))

    df.to_sql(
        name=table_name,
        con=engine,
        schema="raw",
        if_exists="append",
        index=False,
    )
    print(f"  raw.{table_name} <- {len(df)} rows")


def main():
    engine = get_engine()
    ensure_schema(engine)

    print("Loading raw data into PostgreSQL (raw schema)...")
    for table in TABLES:
        load_table(engine, table)

    print("Done.")


if __name__ == "__main__":
    main()
