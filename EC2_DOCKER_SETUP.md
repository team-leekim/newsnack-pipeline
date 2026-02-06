# EC2 Airflow Docker Compose 설정 가이드

이 프로젝트는 공식 Airflow 이미지를 사용하고 entrypoint에서 패키지를 설치합니다.

## EC2 초기 설정

### 1. 컨테이너 시작

```bash
cd ~/newsnack-data

# 컨테이너 시작
docker compose up -d
```

### 2. 패키지 변경 시 재시작

`setup.py`, `requirements.txt` 등이 변경되면 컨테이너를 재시작해야 합니다:

```bash
cd ~/newsnack-data

# 컨테이너 중지
docker compose down

# 컨테이너 재시작
docker compose up -d
```

### 3. 배포 후 확인

```bash
# 패키지 설치 확인
docker compose exec airflow-scheduler pip list | grep newsnack-data

# Import 테스트
docker compose exec airflow-scheduler python -c "from database.connection import session_scope; print('✅ Import 성공!')"

# 컨테이너 상태 확인
docker compose ps

# 로그 확인
docker compose logs airflow-scheduler --tail=50
```

## 주의사항

1. **환경변수 설정**: 
   `.env` 파일에 다음 필수 환경변수 설정 필요:
   ```bash
   DATABASE_URL=postgresql://user:password@host:5432/dbname
   AIRFLOW__CORE__SQL_ALCHEMY_CONN=sqlite:////opt/airflow/airflow.db
   AIRFLOW_UID=50000
   ```

2. **재배포 시**: 
   - DAG/src 파일만 변경: 자동 반영 (볼륨 마운트)
   - 패키지 설정 변경: 컨테이너 재시작 필요
   - GitHub Actions에서 자동으로 처리됨

3. **볼륨 마운트**: 
   - `./src:/opt/airflow/src` - 개발 중 코드 변경 즉시 반영
   - DAG 수정 시 Airflow가 자동으로 새로고침

## 현재 프로젝트의 docker-compose.yml

레포지토리의 `docker-compose.yml` 파일을 사용하세요. 주요 특징:

- **공식 이미지 사용**: entrypoint에서 패키지 설치
- **볼륨 마운트**: 개발 중 코드 변경 즉시 반영
- **간단한 설정**: `_PIP_ADDITIONAL_REQUIREMENTS` 불필요

```bash
# EC2에서 사용법
cd ~/newsnack-data

# 최초: 컨테이너 시작
docker compose up -d

# 이후: 패키지 변경 시 재시작
docker compose down
docker compose up -d

# DAG/src 변경은 자동 반영 (재시작 불필요)
```

## GitHub Actions 자동 배포

패키지 설정 파일이 변경되면 자동으로:
1. EC2에 파일 배포
2. 이미지 재빌드
3. 컨테이너 재시작
