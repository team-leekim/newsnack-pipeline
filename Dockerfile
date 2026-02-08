FROM apache/airflow:2.10.4-python3.12

COPY --chown=airflow:root requirements.txt ./
RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

COPY --chown=airflow:root setup.py pyproject.toml MANIFEST.in ./
COPY --chown=airflow:root src ./src

RUN pip install --no-deps -e .

# Verify installation
RUN pip list | grep newsnack-pipeline
