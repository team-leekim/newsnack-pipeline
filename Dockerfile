# 필요한 Provider는 requirements.txt에서 명시적으로 관리
FROM apache/airflow:slim-2.10.4-python3.12

# Airflow 공식 constraint 파일
ARG AIRFLOW_VERSION=2.10.4
ARG CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"

COPY --chown=airflow:root requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt --constraint "${CONSTRAINT_URL}"

COPY --chown=airflow:root pyproject.toml MANIFEST.in ./
COPY --chown=airflow:root src ./src

RUN pip install -e . --constraint "${CONSTRAINT_URL}"

# Verify installation
RUN pip list | grep newsnack-etl
