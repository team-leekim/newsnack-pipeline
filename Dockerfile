FROM apache/airflow:2.10.4-python3.12

WORKDIR /opt/airflow

# Copy package configuration files
COPY setup.py pyproject.toml MANIFEST.in requirements.txt ./

# Copy source code
COPY src ./src

# Switch to root to install packages
USER root

# Install build tools and package
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# Verify installation
RUN pip list | grep newsnack-data

# Switch back to airflow user
USER airflow
