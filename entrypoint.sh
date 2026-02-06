#!/bin/bash
set -e

python -m pip install --user -e /opt/airflow/project

exec "$@"
