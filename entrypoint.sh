#!/bin/bash
set -e

python -m pip install -e /opt/airflow/project

exec "$@"
