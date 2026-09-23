"""
Extracts the daily USD-based currency exchange rate fixing from the public
Frankfurter REST API and loads it into the raw.exchange_rates table in
PostgreSQL.

This is a real, free, no-auth-required external REST API integration
(as opposed to the synthetic Faker-generated clients/loans/transactions
data) -- it demonstrates pulling and landing data from a live third-party
source as part of the pipeline.

API docs: https://www.frankfurter.app/docs/
Endpoint used: GET https://api.frankfurter.app/latest?from=USD
Rates are published on ECB business days; on weekends/holidays the API
returns the last valid published rate.

Run:
    python extract/extract_exchange_rates.py
"""

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

FRANKFURTER_API_URL = "https://api.frankfurter.app/latest"
MAX_RETRIES = 3
BACKOFF_SECONDS = 2  # doubles after each retry: 2s, 4s, 8s

DB_USER = os.getenv("DB_USER", "dwh_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "dwh_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "loan_dwh")

CONNECTION_STRING = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def fetch_exchange_rates() -> pd.DataFrame:
    """Call the Frankfurter REST API and return the daily USD-based fixing
    as a DataFrame.

    Retries with exponential backoff on network errors, timeouts, and
    5xx/429 responses -- a real external API can be temporarily
    unavailable or rate-limited, so a single failed request should not
    fail the whole pipeline run immediately.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                FRANKFURTER_API_URL, params={"from": "USD"}, timeout=15
            )

            if response.status_code == 429 or response.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"Frankfurter API returned {response.status_code}, retrying..."
                )

            response.raise_for_status()

            payload = response.json()
            rates = payload.get("rates", {})
            if not rates:
                raise RuntimeError("Frankfurter API returned no exchange rate data.")

            df = pd.DataFrame(
                [
                    {"currency_code": code, "rate_per_usd": rate}
                    for code, rate in rates.items()
                ]
            )
            df["valid_for"] = payload["date"]
            return df[["valid_for", "currency_code", "rate_per_usd"]]

        except (
            requests.exceptions.RequestException,
            RuntimeError,
        ) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                wait = BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(
                    f"  attempt {attempt}/{MAX_RETRIES} failed ({exc}), "
                    f"retrying in {wait}s..."
                )
                time.sleep(wait)

    raise RuntimeError(
        f"Frankfurter API request failed after {MAX_RETRIES} attempts: {last_error}"
    )


def load_to_raw(df: pd.DataFrame):
    engine = create_engine(CONNECTION_STRING)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        conn.execute(text("DROP TABLE IF EXISTS raw.exchange_rates CASCADE;"))

    df.to_sql(
        name="exchange_rates",
        con=engine,
        schema="raw",
        if_exists="append",
        index=False,
    )


def main():
    print("Fetching exchange rates from the Frankfurter REST API (USD base)...")
    df = fetch_exchange_rates()
    print(f"  fetched {len(df)} currencies, valid for {df['valid_for'].iloc[0]}")

    load_to_raw(df)
    print(f"  raw.exchange_rates <- {len(df)} rows")
    print("Done.")


if __name__ == "__main__":
    main()
