"""Scheduled and manual Airflow DAGs for StockSearcher v2 dataset workflows.

The two DAGs deliberately run independently: JP and KR collection have their
own source script, external market data, and database tables. No migration
script is imported or executed by this Airflow configuration.
"""

from __future__ import annotations

import pendulum

from airflow import DAG
from airflow.operators.bash import BashOperator


SOURCE_DIR = "/opt/stocksearcher"
MODEL_DIR = f"{SOURCE_DIR}/create_model"
PREDICT_DIR = f"{SOURCE_DIR}/predict"
SEOUL_TIMEZONE = pendulum.timezone("Asia/Seoul")
SCHEDULE_BY_MARKET = {
    "JP": "0 12,18 * * 1-5",
    "KR": "0 14,20 * * 1-5",
}


def build_dataset_predict_dag(market: str, script_name: str) -> DAG:
    """Collect one market, then run its daily and weekly CPU predictions."""
    with DAG(
        dag_id=f"stocksearcher_dataset_{market.lower()}",
        description=f"Run StockSearcher {market} dataset collection.",
        start_date=pendulum.datetime(2026, 1, 1, tz=SEOUL_TIMEZONE),
        #schedule=SCHEDULE_BY_MARKET[market],
        schedule=None,
        catchup=False,
        max_active_runs=1,
        default_args={"retries": 0},
        tags=["stocksearcher", "dataset", market.lower(), "scheduled"],
    ) as dag:
        collect = BashOperator(
            task_id=f"collect_dataset_{market.lower()}",
            bash_command=(
                f"set -euo pipefail\nexport PYTHONPATH={SOURCE_DIR}\n"
                f"cd {SOURCE_DIR}\npython {script_name}\n"
            ),
        )
        predict_daily = BashOperator(
            task_id=f"predict_daily_{market.lower()}",
            bash_command=(
                f"set -euo pipefail\nexport PYTHONPATH={SOURCE_DIR}:{MODEL_DIR}:${PREDICT_DIR}\n"
                f"cd {PREDICT_DIR}\npython predict_{market.lower()}_v2.py --save-db\n"
            ),
        )
        predict_weekly = BashOperator(
            task_id=f"predict_weekly_{market.lower()}",
            bash_command=(
                f"set -euo pipefail\nexport PYTHONPATH={SOURCE_DIR}:{MODEL_DIR}:${PREDICT_DIR}\n"
                f"cd {PREDICT_DIR}\npython predict_week_{market.lower()}_v2.py --save-db\n"
            ),
        )
        collect >> [predict_daily, predict_weekly]
    return dag


def build_dataset_dag(market: str, script_name: str) -> DAG:
    """Create a manually triggered DAG that only collects one market dataset."""
    with DAG(
        dag_id=f"stocksearcher_manual_dataset_{market.lower()}",
        description=f"Manually collect the StockSearcher {market} dataset only.",
        start_date=pendulum.datetime(2026, 1, 1, tz=SEOUL_TIMEZONE),
        schedule=SCHEDULE_BY_MARKET[market],
        #schedule=None,
        catchup=False,
        max_active_runs=1,
        default_args={"retries": 0},
        tags=["stocksearcher", "dataset", market.lower(), "manual"],
    ) as dag:
        BashOperator(
            task_id=f"collect_dataset_{market.lower()}",
            bash_command=(
                f"set -euo pipefail\nexport PYTHONPATH={SOURCE_DIR}\n"
                f"cd {SOURCE_DIR}\npython {script_name}\n"
            ),
        )
    return dag


def build_predict_dag(market: str) -> DAG:
    """Create a manually triggered DAG for daily and weekly predictions."""
    with DAG(
        dag_id=f"stocksearcher_manual_predict_{market.lower()}",
        description=f"Manually run StockSearcher {market} daily and weekly predictions.",
        start_date=pendulum.datetime(2026, 1, 1, tz=SEOUL_TIMEZONE),
        schedule=None,
        catchup=False,
        max_active_runs=1,
        default_args={"retries": 0},
        tags=["stocksearcher", "predict", market.lower(), "manual"],
    ) as dag:
        predict_daily = BashOperator(
            task_id=f"predict_daily_{market.lower()}",
            bash_command=(
                f"set -euo pipefail\nexport PYTHONPATH={SOURCE_DIR}:{MODEL_DIR}:${PREDICT_DIR}\n"
                f"cd {PREDICT_DIR}\npython predict_{market.lower()}_v2.py --save-db\n"
            ),
        )
        predict_weekly = BashOperator(
            task_id=f"predict_weekly_{market.lower()}",
            bash_command=(
                f"set -euo pipefail\nexport PYTHONPATH={SOURCE_DIR}:{MODEL_DIR}:${PREDICT_DIR}\n"
                f"cd {PREDICT_DIR}\npython predict_week_{market.lower()}_v2.py --save-db\n"
            ),
        )
    return dag


stocksearcher_dataset_jp = build_dataset_predict_dag("JP", "dataset/dataset_jp.py")
stocksearcher_dataset_kr = build_dataset_predict_dag("KR", "dataset/dataset_kr.py")
stocksearcher_manual_dataset_jp = build_dataset_dag("JP", "dataset/dataset_jp.py")
stocksearcher_manual_dataset_kr = build_dataset_dag("KR", "dataset/dataset_kr.py")
stocksearcher_manual_predict_jp = build_predict_dag("JP")
stocksearcher_manual_predict_kr = build_predict_dag("KR")
