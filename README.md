# Newsnack Data - 뉴스 수집 및 이슈 클러스터링 자동화

뉴스 RSS 수집 및 유사 기사 클러스터링을 통한 이슈 집계 시스템

## 📋 목차

- [프로젝트 개요](#프로젝트-개요)
- [로컬 개발 환경 설정](#로컬-개발-환경-설정)
- [EC2 Airflow 환경 설정](#ec2-airflow-환경-설정)
- [프로젝트 구조](#프로젝트-구조)
- [사용법](#사용법)

## 프로젝트 개요

이 프로젝트는 Apache Airflow를 사용하여 다음 작업을 자동화합니다:

- **뉴스 수집**: 30분마다 RSS 피드에서 뉴스 기사 수집
- **이슈 클러스터링**: 매일 2회(07:00, 17:00 KST) 유사 기사를 묶어 이슈 생성

## 로컬 개발 환경 설정

### 1. 가상환경 생성 및 활성화

```bash
python -m venv venv
source ./venv/bin/activate  # macOS/Linux
# 또는
.\venv\Scripts\activate  # Windows
```

### 2. 패키지 설치

이 프로젝트는 설치 가능한 패키지로 구성되어 있습니다. 개발 모드로 설치하면 코드 수정이 즉시 반영됩니다.

```bash
# 개발 모드로 설치 (권장)
pip install -e .

# 이 명령은 다음을 자동으로 수행합니다:
# - requirements.txt의 모든 의존성 설치
# - src/ 디렉토리를 Python 패키지로 설치
```

### 3. 환경변수 설정

`.env` 파일을 생성하고 데이터베이스 연결 정보를 설정합니다:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### 4. 로컬에서 스크립트 실행

패키지 설치 후 어디서든 동일한 import 경로로 사용할 수 있습니다:

```bash
# RSS 수집 실행
python -c "from collector.rss_parser import collect_rss; collect_rss()"

# 이슈 클러스터링 실행
python -c "from processor.clusterer import run_clustering; run_clustering()"
```

## EC2 Airflow 환경 설정

### 초기 설정 (최초 1회)

EC2 인스턴스에서 다음 단계를 수행합니다:

#### 1. 이미지 빌드 및 컨테이너 시작

```bash
cd ~/newsnack-data

# 이미지 빌드
docker build -t newsnack-airflow:latest .

# 컨테이너 시작
docker compose up -d
```

#### 2. 설치 확인

```bash
# 패키지 설치 확인
docker compose exec airflow-scheduler pip list | grep newsnack-data

# Import 테스트
docker compose exec airflow-scheduler python -c "from database.connection import session_scope; print('✅ Import 성공!')"

# 컨테이너 상태 확인
docker compose ps
```

#### 3. 패키지 변경 시 재배포

`setup.py`, `requirements.txt` 등이 변경되면:

```bash
cd ~/newsnack-data
docker compose down
docker compose up -d
```

**참고**: DAG나 src 코드 변경은 볼륨 마운트로 자동 반영되므로 재시작 불필요

### 자동 배포

GitHub Actions를 통해 자동으로 배포됩니다:

- **트리거**: `main` 또는 `hotfix/*` 브랜치에 push
- **배포 대상**:
  - `dags/` 디렉토리
  - `src/` 디렉토리
  - 패키지 설정 파일 (requirements.txt, setup.py 등이 변경된 경우)

패키지 설정 파일이 변경되면 자동으로 컨테이너를 재시작합니다.

## 프로젝트 구조

```
newsnack-data/
├── setup.py              # 패키지 설정 파일
├── pyproject.toml        # Modern Python 패키지 설정
├── MANIFEST.in           # 패키지에 포함할 파일 정의
├── requirements.txt      # Python 의존성
├── dags/                 # Airflow DAG 파일
│   ├── news_collection_dag.py
│   └── issue_clustering_dag.py
├── src/                  # 소스 코드 (Python 패키지)
│   ├── collector/
│   │   ├── rss_parser.py
│   │   └── sources.yaml
│   ├── database/
│   │   ├── connection.py
│   │   └── models.py
│   └── processor/
│       └── clusterer.py
└── sql/                  # 데이터베이스 스키마
    ├── schema.sql
    └── data.sql
```

## 사용법

### Import 경로

패키지 설치 덕분에 로컬과 Airflow 환경 모두에서 동일한 import 경로를 사용합니다:

```python
# 데이터베이스
from database.connection import session_scope
from database.models import RawArticle, Category, Issue

# RSS 수집
from collector.rss_parser import collect_rss

# 클러스터링
from processor.clusterer import run_clustering
```

### DAG 스케줄

- **뉴스 수집** (`news_collection_dag`): 매 30분마다 실행
- **이슈 클러스터링** (`issue_clustering_dag`): 매일 07:00, 17:00 KST (UTC 22:00, 08:00)

### 로컬 테스트

```bash
# 가상환경 활성화
source ./venv/bin/activate

# RSS 수집
python -m collector.rss_parser

# 이슈 클러스터링
python -m processor.clusterer
```

## 트러블슈팅

### Import 에러 발생 시

```bash
# 패키지가 설치되어 있는지 확인
pip list | grep newsnack-data

# 없다면 재설치
pip install -e .
```

### Airflow에서 import 에러 발생 시

```bash
# EC2에서 컨테이너 내부 확인
docker compose exec airflow-scheduler pip list | grep newsnack-data

# 없다면 컨테이너 재시작
docker compose down
docker compose up -d
```

## 개발 워크플로우

1. 기능 브랜치 생성: `git checkout -b feature/your-feature`
2. 코드 수정
3. 로컬 테스트: `pip install -e .` 후 테스트
4. Pull Request 생성 (자동으로 DAG 유효성 검사 실행)
5. `main` 브랜치에 머지 시 자동 배포

## 라이선스

Proprietary - Newsnack
