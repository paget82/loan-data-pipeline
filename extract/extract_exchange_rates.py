"""
Extracts the daily currency exchange rate fixing from the public Czech
National Bank (CNB) REST API and loads it into the raw.exchange_rates
table in PostgreSQL.

This is a real, free, no-auth-required external REST API integration
(as opposed to the synthetic Faker-generated clients/loans/transactions
data) -- it demonstrates pulling and landing data from a live third-party
source as part of the pipeline.

API docs: https://api.cnb.cz (Swagger UI at https://api.cnb.cz/cnbapi/swagger-ui.html)
Endpoint used: GET https://api.cnb.cz/cnbapi/exrates/daily?lang=EN
On weekends/holidays the API returns the last valid published rate.

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

CNB_API_URL = "https://api.cnb.cz/cnbapi/exrates/daily"
MAX_RETRIES = 3
BACKOFF_SECONDS = 2  # doubles after each retry: 2s, 4s, 8s

DB_USER = os.getenv("DB_USER", "dwh_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "dwh_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "loan_dwh")

CONNECTION_STRING = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def fetch_exchange_rates() -> pd.DataFrame:
    """Call the CNB REST API and return the daily fixing as a DataFrame.

    Retries with exponential backoff on network errors, timeouts, and
    5xx/429 responses -- a real external API can be temporarily
    unavailable or rate-limited, so a single failed request should not
    fail the whole pipeline run immediately.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(CNB_API_URL, params={"lang": "EN"}, timeout=15)

            if response.status_code == 429 or response.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"CNB API returned {response.status_code}, retrying..."
                )

            response.raise_for_status()

            payload = response.json()
            rates = payload.get("rates", [])
            if not rates:
                raise RuntimeError("CNB API returned no exchange rate data.")

            df = pd.DataFrame(rates)
            df = df.rename(
                columns={"currencyCode": "currency_code", "validFor": "valid_for"}
            )
            return df[
                ["valid_for", "country", "currency", "currency_code", "amount", "rate"]
            ]

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
        f"CNB API request failed after {MAX_RETRIES} attempts: {last_error}"
    )


def load_to_raw(df: pd.DataFrame):
    engine = create_engine(CONNECTION_STRING)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        # Explicit DROP ... CASCADE so the run doesn't fail if dbt staging
        # views from a previous run depend on this table.
        conn.execute(text("DROP TABLE IF EXISTS raw.exchange_rates CASCADE;"))

    df.to_sql(
        name="exchange_rates",
        con=engine,
        schema="raw",
        if_exists="append",
        index=False,
    )


def main():
    print("Fetching exchange rates from the CNB REST API...")
    df = fetch_exchange_rates()
    print(f"  fetched {len(df)} currencies, valid for {df['valid_for'].iloc[0]}")

    load_to_raw(df)
    print(f"  raw.exchange_rates <- {len(df)} rows")
    print("Done.")


if __name__ == "__main__":
    main()
