# 뉴스낵 Pipeline

Apache Airflow 기반 뉴스 데이터 ETL 및 오케스트레이션 파이프라인입니다.

RSS 피드에서 뉴스를 수집하고, 유사 기사들을 군집화하여 이슈를 생성하며, AI 엔진(`newsnack-ai`)을 통해 뉴스데스크와 웹툰 콘텐츠를 자동으로 생성합니다. 모든 워크플로우는 Apache Airflow DAG로 정의되며 일정에 따라 자동으로 실행됩니다. 생성된 콘텐츠는 PostgreSQL 데이터베이스에 저장되며, Core API 서버(`newsnack-backend`)에서 조회하여 사용자에게 제공합니다.

## 시스템 아키텍처

```mermaid
graph LR
    A["RSS Sources<br/>(언론사)"] -->|수집| B["news_collection_dag<br/>(1시간 주기)"]
    B -->|저장| D[("PostgreSQL<br/>Database")]
    D -->|조회| C["issue_clustering_dag<br/>(07:10, 17:10)"]
    C -->|저장| D
    D -->|조회| E["content_generation_dag<br/>(07:30, 17:30)"]
    E -->|요청| F["newsnack-ai<br/>Server"]
    F -->|생성| G["콘텐츠<br/>(웹툰/카드뉴스, 오늘의 뉴스낵)"]
    G -->|저장| D
    D -->|조회| H["newsnack-backend<br/>API Server"]
    H -->|배포| I["사용자"]
```

## ETL 프로세스

### 프로세스 상세
```mermaid
flowchart TD
    subgraph 기사 수집
        A[RSS 피드] --> B[뉴스 파싱 및 DB 저장]
    end
    subgraph 이슈 집계
        C[DB에서 미처리 기사 조회] --> D[카테고리별 기사 그룹핑]
        D --> E[기사 제목 유사도 클러스터링]
        E --> F[대표 제목 선정 및 이슈 생성]
        F --> G[DB 저장]
    end
    B --> C
```

### 단계별 설명

- **기사 수집**: RSS 피드에서 기사 데이터를 파싱하여 DB에 저장합니다. 포토뉴스 등 불필요한 기사 필터링, 카테고리 매핑, 중복 기사 제외 등은 자동 처리됩니다.
- **이슈 집계**: DB에서 최근 미처리 기사들을 카테고리별로 그룹핑한 뒤, 기사 제목 유사도(TF-IDF + 코사인 유사도) 기반으로 클러스터링합니다. 각 클러스터는 대표 제목을 선정하여 하나의 이슈로 DB에 저장됩니다.

## 프로젝트 구조

```
newsnack-pipeline/
├── dags/                             # Airflow DAG 정의
│   ├── news_collection_dag.py        # 뉴스 수집 (RSS)
│   ├── issue_clustering_dag.py       # 이슈 군집화
│   └── content_generation_dag.py     # AI 콘텐츠 생성
├── src/newsnack_etl/                 # Python ETL 패키지
│   ├── collector/                    # 데이터 수집
│   │   ├── rss_parser.py
│   │   └── sources.yaml
│   ├── processor/                    # 데이터 처리
│   │   └── clusterer.py
│   ├── repository/                   # DB I/O
│   └── database/                     # DB 설정
│       ├── connection.py
│       └── models.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## 빠른 시작

### 로컬 개발

```bash
# 1. Python 3.12로 가상환경 생성
python3.12 -m venv venv
source venv/bin/activate

# 2. 패키지 설치
pip install -e .

# 3. 환경변수 설정
cat > .env << EOF
DATABASE_URL=postgresql://user:password@localhost:5432/newsnack
EOF

# 4. 스크립트 실행
python -m newsnack_etl.collector.rss_parser
python -m newsnack_etl.processor.clusterer
```

### 자동 배포 (GitHub Actions)

코드를 `main` 브랜치에 푸시하면 GitHub Actions 워크플로우가 자동으로 실행됩니다:

1. 코드 푸시 → `.github/workflows/deploy.yml` 트리거
2. DAG 문법 검증
3. 변경 파일 감지 (패키지 설정 변경 여부 확인)
4. EC2에서 `git pull`로 최신 코드 동기화
5. 변경 유형에 따라 컨테이너 처리:
   - 패키지 설정 변경 → 이미지 재빌드 후 재시작
   - 코드만 변경 → 재빌드 없이 컨테이너 재생성

**주의**: EC2에서 직접 명령어를 실행할 필요가 없습니다. PR을 머지하기만 하면 자동으로 배포됩니다.

## 의존성 관리

의존성의 성격에 따라 관리 파일이 분리되어 있습니다.

| 파일 | 책임 | 예시 |
|------|------|------|
| `pyproject.toml` | `newsnack_etl` 패키지 의존성 | `feedparser`, `scikit-learn`, `psycopg2-binary` |
| `requirements.txt` | Airflow 환경 의존성 (Provider) | `apache-airflow-providers-postgres` |

### 새 패키지 추가 시

**ETL 코드(`src/`) 내부에서 사용하는 패키지**
→ `pyproject.toml`의 `dependencies`에 추가

**Airflow Provider 추가** (새로운 Operator/Hook 사용 시)
→ `requirements.txt`에 추가

### 로컬 개발 환경 구성

```bash
# pip install -e . 하나로 newsnack_etl과 모든 의존성이 설치됩니다
pip install -e .

# requirements.txt(Airflow Provider)는 로컬 개발에 필요하지 않습니다
```

> **버전 관리**: `feedparser`, `scikit-learn`, `numpy`처럼 Airflow가 사용하지 않는 패키지는 버전을 고정합니다.
> `SQLAlchemy`, `psycopg2-binary`, `requests`처럼 Airflow와 공유되는 패키지는 버전을 고정하지 않으며, Airflow constraint 파일이 호환 버전을 결정합니다.

## 주요 DAG

| DAG | 스케줄 | 역할 |
|-----|--------|------|
| `news_collection_dag` | `0 * * * *` | RSS 피드에서 뉴스 수집 (매 1시간) |
| `issue_clustering_dag` | `10 8,22 * * *` | 유사 기사 군집화 (07:10, 17:10 KST) |
| `content_generation_dag` | `30 8,22 * * *` | AI 콘텐츠 생성 (07:30, 17:30 KST) |

## Import 경로

```python
from newsnack_etl.collector import collect_rss
from newsnack_etl.processor import run_clustering
from newsnack_etl.database import session_scope, RawArticle, Issue, Category
from newsnack_etl.repository import ArticleRepository, IssueRepository
```

## 트러블슈팅

**패키지 미설치**
```bash
pip install -e .
pip list | grep newsnack-etl
```

**Airflow import 에러**
```bash
docker compose down && docker compose up -d
docker compose exec airflow-scheduler pip list | grep newsnack-etl
```

**DAG 문법 에러**
```bash
python -m py_compile dags/news_collection_dag.py
```

## 참고 문서

- [Apache Airflow](https://airflow.apache.org/)
- [EC2_DOCKER_SETUP.md](./EC2_DOCKER_SETUP.md)
- [newsnack-ai](https://github.com/team-leekim/newsnack-ai)
- [newsnack-backend](https://github.com/team-leekim/newsnack-backend)
