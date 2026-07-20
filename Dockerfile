FROM apache/airflow:2.10.5-python3.11

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        git \
        libasound2 \
        libgbm1 \
        libgtk-3-0 \
        libnss3 \
        libxss1 \
        libu2f-udev \
        fonts-liberation \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements-stocksearcher.txt /requirements-stocksearcher.txt
RUN pip install --no-cache-dir \
        --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.11.txt" \
        -r /requirements-stocksearcher.txt

COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root src /opt/stocksearcher
