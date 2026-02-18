# EC2 Airflow Docker Compose 설정 가이드

이 프로젝트는 Dockerfile을 사용하여 newsnack-etl 패키지가 설치된 커스텀 Airflow 이미지를 빌드합니다.

## EC2 초기 설정 (최초 1회)

### 1. 레포지토리 클론

EC2에 Deploy Key가 등록되어 있어야 합니다.

```bash
git clone git@github.com:team-leekim/newsnack-pipeline.git /home/ec2-user/newsnack-pipeline
cd /home/ec2-user/newsnack-pipeline
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 실제 값 입력
```

### 3. 컨테이너 시작

```bash
cd /home/ec2-user/newsnack-pipeline

# 이미지 빌드 및 컨테이너 시작
docker compose up -d --build
```

### 4. 배포 후 확인

```bash
# 패키지 설치 확인
docker compose exec airflow-scheduler pip list | grep newsnack-etl

# Import 테스트
docker compose exec airflow-scheduler python -c "from database.connection import session_scope; print('✅ Import 성공!')"

# 컨테이너 상태 확인
docker compose ps

# 로그 확인
docker compose logs airflow-scheduler --tail=50
```

## 주의사항

1. **환경변수 설정**:
   `.env.example`을 참고하여 `.env` 파일 작성

2. **재배포 시**:
   - DAG/src 파일만 변경: GitHub Actions가 `git pull` 후 `docker compose up -d`로 자동 반영
   - 패키지 설정 변경: GitHub Actions가 `git pull` 후 `docker compose up -d --build`로 이미지 재빌드 및 자동 반영
   - **EC2에서 직접 명령어를 실행할 필요 없음**

3. **볼륨 마운트**:
   - `./src:/opt/airflow/src` - 코드 변경 시 이미지 재빌드 없이 즉시 반영
   - `./dags:/opt/airflow/dags` - DAG 수정 시 Airflow가 자동으로 새로고침

## 현재 프로젝트의 docker-compose.yml

레포지토리의 `docker-compose.yml` 파일을 사용하세요. 주요 특징:

- **커스텀 이미지**: Dockerfile로 빌드하여 패키지 사전 설치
- **볼륨 마운트**: 코드 변경 즉시 반영 (이미지 재빌드 불필요)
- **간단한 설정**: `_PIP_ADDITIONAL_REQUIREMENTS` 불필요

## GitHub Actions 자동 배포

`main` 브랜치에 푸시하면 자동으로:

1. DAG 문법 검증
2. 변경 파일 감지 (`requirements.txt`, `Dockerfile` 등 패키지 설정 변경 여부 확인)
3. EC2에서 `git pull`로 최신 코드 동기화
4. 변경 유형에 따라 컨테이너 처리:
   - 패키지 설정 변경 → `docker compose up -d --build` (이미지 재빌드)
   - 코드만 변경 → `docker compose up -d` (재빌드 없이 재생성)
5. 배포 결과 검증

## EC2에서 수동으로 컨테이너를 관리해야 할 경우

```bash
# 컨테이너 상태 확인
cd /home/ec2-user/newsnack-pipeline
docker compose ps

# 패키지 변경 시 이미지 재빌드
docker compose down
docker compose up -d --build

# DAG/src 변경은 git pull 후 자동 반영 (재빌드 불필요)
git pull origin main
docker compose up -d
```
