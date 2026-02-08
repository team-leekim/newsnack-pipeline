# Newsnack Pipeline

Apache Airflow 기반 뉴스 데이터 ETL 및 오케스트레이션 파이프라인입니다.

RSS 피드에서 뉴스를 수집하고, 유사 기사들을 군집화하여 이슈를 생성하며, AI 서비스(newsnack-ai)를 통해 뉴스데스크와 웹툰 콘텐츠를 자동으로 생성합니다. 모든 워크플로우는 Apache Airflow DAG로 정의되며 일정에 따라 자동으로 실행됩니다. 생성된 콘텐츠는 PostgreSQL 데이터베이스에 저장되며, newsnack-backend API 서버에서 조회하여 사용자에게 제공합니다.

## 시스템 아키텍처

```mermaid
graph LR
    A["RSS Sources<br/>(언론사)"] -->|수집| B["news_collection_dag<br/>(30분 주기)"]
    B -->|저장| D[("PostgreSQL<br/>Database")]
    D -->|조회| C["issue_clustering_dag<br/>(07:00, 17:00)"]
    C -->|저장| D
    D -->|조회| E["content_generation_dag<br/>(07:30, 17:30)"]
    E -->|요청| F["newsnack-ai<br/>Server"]
    F -->|생성| G["콘텐츠<br/>(웹툰/카드뉴스, 오늘의 뉴스낵)"]
    G -->|저장| D
    D -->|조회| H["newsnack-backend<br/>API Server"]
    H -->|배포| I["사용자"]
    
    style B fill:#4A90E2
    style C fill:#4A90E2
    style E fill:#4A90E2
    style D fill:#50C878
    style F fill:#FF6B6B
    style H fill:#FFA500
    
```

## 프로젝트 구조 (계획)

```
newsnack-pipeline/
├── dags/                    # Airflow DAG 정의
│   ├── news_collection_dag.py        # 뉴스 수집 (RSS)
│   ├── issue_clustering_dag.py       # 이슈 군집화
│   └── content_generation_dag.py     # AI 콘텐츠 생성
├── src/newsnack_etl/               # Python ETL 패키지
│   ├── collector/           # 데이터 수집
│   │   ├── rss_parser.py
│   │   └── sources.yaml
│   ├── processor/           # 데이터 처리
│   │   └── clusterer.py
│   ├── repository/          # DB I/O
│   └── database/            # DB 설정
│       ├── connection.py
│       └── models.py
├── docker-compose.yml
├── Dockerfile
├── setup.py
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
python -m src.collector.rss_parser
python -m src.processor.clusterer
```

### 자동 배포 (GitHub Actions)

코드를 `main` 브랜치에 푸시하면 GitHub Actions 워크플로우가 자동으로 실행됩니다:

1. 코드 푸시 → `.github/workflows/deploy.yml` 트리거
2. Docker 이미지 빌드: `newsnack-pipeline:latest`
3. EC2 인스턴스에 자동 배포
4. 컨테이너 재시작

**주의**: EC2에서 직접 명령어를 실행할 필요가 없습니다. PR을 머지하기만 하면 자동으로 배포됩니다.

## 주요 DAG

| DAG | 스케줄 | 역할 |
|-----|--------|------|
| `news_collection_dag` | `*/30 * * * *` | RSS 피드에서 뉴스 수집 |
| `issue_clustering_dag` | `0 22,8 * * *` | 유사 기사 군집화 |
| `content_generation_dag` | `30 22,8 * * *` | AI 콘텐츠 생성 |

## Import 경로

```python
from collector.rss_parser import collect_rss
from processor.clusterer import run_clustering
from database.connection import session_scope
from database.models import RawArticle, Issue, Category
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
