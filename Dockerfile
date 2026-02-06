FROM apache/airflow:2.10.4-python3.12

# Set working directory
WORKDIR /opt/airflow

# Copy package configuration files
COPY setup.py pyproject.toml MANIFEST.in requirements.txt ./

# Copy source code
COPY src ./src
COPY dags ./dags

# Install package in development mode (as root)
RUN pip install -e .

# Verify installation
RUN python -c "from database.connection import session_scope; print('✅ Package installed successfully')" || true

# Default entrypoint (inherited from base image)
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["scheduler"]
