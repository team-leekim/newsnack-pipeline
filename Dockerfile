FROM apache/airflow:2.10.4-python3.12

# 작업 디렉토리 설정
WORKDIR /opt/airflow

# 패키지 설정 파일 복사
COPY setup.py pyproject.toml MANIFEST.in ./
COPY requirements.txt ./

# 소스 코드 복사
COPY src ./src

# 패키지 설치 (개발 모드)
USER root
RUN pip install --no-cache-dir -e .
USER airflow

# 설치 확인
RUN python -c "from database.connection import session_scope; from collector.rss_parser import collect_rss; from processor.clusterer import run_clustering; print('✅ Package installation verified!')"
