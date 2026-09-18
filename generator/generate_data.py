"""
Synthetic data generator for the loan pipeline.

Creates three linked tables:
  - clients.csv       : clients (demographics, income, credit score)
  - loans.csv          : loans (amount, interest rate, status)
  - transactions.csv    : transactions (installments, late payments, early repayments)

Intentionally includes "dirty" data (missing values, duplicates, outliers)
so the transformation layer (Pandas/dbt) has something real to handle.
"""

import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker("cs_CZ")
# Separate US-locale instance used only for the fields that mirror the
# "bank_loan_data" reference dataset (US states, job titles), so the
# output can populate a flat table compatible with that dataset's schema.
fake_us = Faker("en_US")
Faker.seed(42)
random.seed(42)
np.random.seed(42)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

N_CLIENTS = 5_000
N_LOANS = 8_000
N_TRANSACTIONS = 60_000

LOAN_STATUSES = ["active", "paid_off", "defaulted", "delinquent"]
TRANSACTION_TYPES = ["installment", "late_payment", "early_repayment", "fee"]

EMP_LENGTHS = [
    "< 1 year", "1 year", "2 years", "3 years", "4 years", "5 years",
    "6 years", "7 years", "8 years", "9 years", "10+ years",
]
HOME_OWNERSHIP = ["RENT", "OWN", "MORTGAGE", "OTHER"]
HOME_OWNERSHIP_WEIGHTS = [0.45, 0.15, 0.35, 0.05]
VERIFICATION_STATUSES = ["Verified", "Source Verified", "Not Verified"]
LOAN_PURPOSES = [
    "Debt consolidation", "credit card", "home improvement", "major purchase",
    "small business", "car", "medical", "moving", "vacation", "house",
    "educational", "renewable_energy", "wedding", "other",
]
APPLICATION_TYPES = ["INDIVIDUAL", "JOINT"]
APPLICATION_TYPE_WEIGHTS = [0.95, 0.05]


def generate_clients(n: int) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        rows.append(
            {
                "client_id": str(uuid.uuid4()),
                "full_name": fake.name(),
                "birth_date": fake.date_of_birth(minimum_age=18, maximum_age=75),
                "city": fake.city(),
                "monthly_income": round(np.random.lognormal(mean=10.0, sigma=0.4)),
                "credit_score": random.randint(300, 900),
                "signup_date": fake.date_between(start_date="-5y", end_date="today"),
                # Fields added to support a flat output table compatible
                # with the "bank_loan_data" reference dataset schema
                "address_state": fake_us.state_abbr(),
                "emp_length": random.choice(EMP_LENGTHS),
                "emp_title": fake_us.job(),
                "home_ownership": random.choices(
                    HOME_OWNERSHIP, weights=HOME_OWNERSHIP_WEIGHTS
                )[0],
                "verification_status": random.choice(VERIFICATION_STATUSES),
                "total_acc": random.randint(1, 40),
            }
        )
    df = pd.DataFrame(rows)

    # Intentionally injected "dirty" data
    dirty_idx = df.sample(frac=0.03, random_state=1).index
    df.loc[dirty_idx, "monthly_income"] = np.nan

    dup_rows = df.sample(frac=0.01, random_state=2)
    df = pd.concat([df, dup_rows], ignore_index=True)

    return df


def generate_loans(n: int, client_ids: list[str]) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        origination = fake.date_between(start_date="-4y", end_date="today")
        rows.append(
            {
                "loan_id": str(uuid.uuid4()),
                "client_id": random.choice(client_ids),
                "principal_amount": round(np.random.lognormal(mean=9.5, sigma=0.6), 2),
                "interest_rate": round(random.uniform(3.5, 24.9), 2),
                "origination_date": origination,
                "term_months": random.choice([36, 60]),
                "status": random.choices(
                    LOAN_STATUSES, weights=[0.55, 0.25, 0.10, 0.10]
                )[0],
                # Fields added to support a flat output table compatible
                # with the "bank_loan_data" reference dataset schema
                "application_type": random.choices(
                    APPLICATION_TYPES, weights=APPLICATION_TYPE_WEIGHTS
                )[0],
                "purpose": random.choice(LOAN_PURPOSES),
                "last_credit_pull_date": fake.date_between(
                    start_date="-3m", end_date="today"
                ),
                "dti": round(random.uniform(0.01, 0.40), 4),
            }
        )
    df = pd.DataFrame(rows)

    # A handful of missing interest rates (e.g. an import glitch from the source system)
    dirty_idx = df.sample(frac=0.02, random_state=3).index
    df.loc[dirty_idx, "interest_rate"] = np.nan

    return df


def generate_transactions(n: int, loan_ids: list[str]) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        tx_date = fake.date_between(start_date="-4y", end_date="today")
        rows.append(
            {
                "transaction_id": str(uuid.uuid4()),
                "loan_id": random.choice(loan_ids),
                "transaction_date": tx_date,
                "amount": round(abs(np.random.normal(loc=3500, scale=1200)), 2),
                "transaction_type": random.choices(
                    TRANSACTION_TYPES, weights=[0.70, 0.15, 0.10, 0.05]
                )[0],
            }
        )
    df = pd.DataFrame(rows)

    # Duplicate transactions (a common real-world issue caused by source system retry logic)
    dup_rows = df.sample(frac=0.015, random_state=4)
    df = pd.concat([df, dup_rows], ignore_index=True)

    return df


def main():
    print("Generating clients...")
    clients = generate_clients(N_CLIENTS)
    clients.to_csv(OUTPUT_DIR / "clients.csv", index=False)

    print("Generating loans...")
    loans = generate_loans(N_LOANS, clients["client_id"].tolist())
    loans.to_csv(OUTPUT_DIR / "loans.csv", index=False)

    print("Generating transactions...")
    transactions = generate_transactions(N_TRANSACTIONS, loans["loan_id"].tolist())
    transactions.to_csv(OUTPUT_DIR / "transactions.csv", index=False)

    print(f"Done. Files saved to: {OUTPUT_DIR}")
    print(f"  clients.csv       -> {len(clients)} rows")
    print(f"  loans.csv         -> {len(loans)} rows")
    print(f"  transactions.csv  -> {len(transactions)} rows")


if __name__ == "__main__":
    main()
