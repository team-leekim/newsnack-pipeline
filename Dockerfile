FROM apache/airflow:2.10.4-python3.12

# Copy package files FIRST
COPY --chown=airflow:root setup.py pyproject.toml MANIFEST.in requirements.txt ./
COPY --chown=airflow:root src ./src

# Install as airflow user
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# Verify installation
RUN pip list | grep newsnack-data
