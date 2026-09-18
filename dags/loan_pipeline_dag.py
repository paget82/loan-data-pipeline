"""
DAG orchestrating the loan data pipeline.

Runs the full batch flow daily:
  1a. generate_data          -> generates new synthetic CSV data
  1b. extract_exchange_rates -> pulls the daily EUR/CZK rate from the
                                 public CNB REST API (runs in parallel
                                 with 1a/2, independent external source)
  2.  extract_to_raw         -> loads the CSVs into the raw schema in PostgreSQL
  3.  dbt_deps               -> installs dbt package dependencies (dbt_utils)
  4.  dbt_run                -> builds the staging and mart models (dbt)
  5.  dbt_test               -> runs data quality tests

The project is mounted into /opt/airflow/project (see docker-compose.yml).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/project"
VENV_PYTHON = "/opt/dbt_venv/bin/python"
VENV_DBT = "/opt/dbt_venv/bin/dbt"

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="loan_data_pipeline",
    description="Batch pipeline: generate -> extract (incl. external REST API) -> dbt transform -> test",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["loan-pipeline", "batch", "dbt"],
) as dag:

    generate_data = BashOperator(
        task_id="generate_data",
        bash_command=f"cd {PROJECT_DIR} && {VENV_PYTHON} generator/generate_data.py",
    )

    extract_to_raw = BashOperator(
        task_id="extract_to_raw",
        bash_command=f"cd {PROJECT_DIR} && {VENV_PYTHON} extract/extract_to_raw.py",
    )

    # Independent external REST API source (CNB exchange rates) -- does
    # not depend on generate_data, so it can run in parallel.
    extract_exchange_rates = BashOperator(
        task_id="extract_exchange_rates",
        bash_command=f"cd {PROJECT_DIR} && {VENV_PYTHON} extract/extract_exchange_rates.py",
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {PROJECT_DIR}/dbt_project && {VENV_DBT} deps",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/dbt_project && {VENV_DBT} run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt_project && {VENV_DBT} test",
    )

    generate_data >> extract_to_raw
    [extract_to_raw, extract_exchange_rates] >> dbt_deps >> dbt_run >> dbt_test
