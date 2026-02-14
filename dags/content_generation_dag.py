"""
AI 콘텐츠 생성 DAG
이슈 집계 후 AI 서버에 콘텐츠 생성 요청 및 오늘의 뉴스낵 조립
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable
from airflow.exceptions import AirflowSkipException
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'newsnack',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

common_api_headers = {
    "Content-Type": "application/json",
    "x-api-key": "{{ var.value.AI_SERVER_API_KEY }}"
}

async_response_check = lambda response: response.status_code == 202

def select_target_issues(ti, **context):
    """
    미처리 이슈 중 화제성(기사 개수) 높은 순으로 Top N 선정
    """
    # Airflow Variables에서 설정값 가져오기
    target_count = int(Variable.get("TOP_NEWSNACK_COUNT", default_var=5))
    lookback_hours = int(Variable.get("DAG_GENERATION_LOOKBACK_HOURS", default_var=24))
    
    logger.info(f"Selecting target issues: Top {target_count}, Lookback {lookback_hours}h")
    
    # PostgresHook을 사용하여 DB 연결
    pg_hook = PostgresHook(postgres_conn_id='newsnack_db_conn')
    
    # 미처리 이슈를 화제성(기사 개수) 순으로 조회
    query = """
        SELECT i.id, COUNT(ra.id) as article_count
        FROM issue i
        LEFT JOIN raw_article ra ON ra.issue_id = i.id
        WHERE i.processing_status = 'PENDING'
        AND i.batch_time >= NOW() - INTERVAL %s
        GROUP BY i.id
        ORDER BY article_count DESC, i.batch_time DESC
        LIMIT %s
    """
    
    results = pg_hook.get_records(query, parameters=(f'{lookback_hours} HOURS', target_count))
    
    if not results:
        logger.warning("No unprocessed issues found.")
        ti.xcom_push(key='target_issues', value=[])
        return []
    
    # issue_id만 추출
    target_ids = [row[0] for row in results]
    
    logger.info(f"Selected {len(target_ids)} issues: {target_ids}")
    
    # XCom에 저장 (다음 태스크에서 사용)
    ti.xcom_push(key='target_issues', value=target_ids)
    
    return target_ids

def check_generation_needed(ti, **context):
    """생성할 이슈가 있는지 확인하여 후속 태스크 스킵 여부 결정"""
    targets = ti.xcom_pull(task_ids='select_target_issues', key='target_issues')
    
    if not targets:
        logger.info("No issues to generate. This run will be skipped.")
        raise AirflowSkipException("No unprocessed issues found. Gracefully skipping DAG run.")
    
    logger.info(f"Found {len(targets)} issues to process. Continuing...")
    return True

def wait_for_completion(ti, **context):
    """
    AI 콘텐츠 생성 완료 대기 (Smart Wait)
    """
    target_ids = ti.xcom_pull(task_ids='select_target_issues', key='target_issues')
    if not target_ids:
        raise AirflowSkipException("No target issues.")

    # 설정값 로드
    timeout = int(Variable.get("CONTENT_GEN_TIMEOUT", default_var=600))
    interval = int(Variable.get("CONTENT_GEN_CHECK_INTERVAL", default_var=30))
    min_completion_count = int(Variable.get("CONTENT_GEN_MIN_COMPLETION", default_var=3))

    pg_hook = PostgresHook(postgres_conn_id='newsnack_db_conn')
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # 상태 확인 쿼리
        placeholders = ','.join(['%s'] * len(target_ids))
        query = f"""
            SELECT id FROM issue 
            WHERE id IN ({placeholders}) 
            AND processing_status = 'COMPLETED'
        """
        records = pg_hook.get_records(query, parameters=tuple(target_ids))
        completed_ids = [r[0] for r in records]
        
        logger.info(f"Waiting... Completed {len(completed_ids)}/{len(target_ids)}")
        
        # 1. 모두 완료되었으면 즉시 성공
        if len(completed_ids) == len(target_ids):
            logger.info("All target issues completed!")
            ti.xcom_push(key='completed_issue_ids', value=completed_ids)
            return True
            
        time.sleep(interval)
    
    # Timeout 발생 시 로직
    # 다시 한 번 최종 확인
    placeholders = ','.join(['%s'] * len(target_ids))
    query = f"""
        SELECT id FROM issue 
        WHERE id IN ({placeholders}) 
        AND processing_status = 'COMPLETED'
    """
    records = pg_hook.get_records(query, parameters=tuple(target_ids))
    completed_ids = [r[0] for r in records]
    
    logger.info(f"Timeout reached. Final completed count: {len(completed_ids)}")
    
    # 2. 최소 조건(3개) 충족 시 통과
    if len(completed_ids) >= 3:
        logger.warning(f"Timeout but sufficient issues completed ({len(completed_ids)}). Proceeding.")
        ti.xcom_push(key='completed_issue_ids', value=completed_ids)
        return True
    
    # 3. 최소 조건 미달 시 Skip
    else:
        logger.error(f"Insufficient issues completed ({len(completed_ids)}). Skipping newsnack assembly.")
        raise AirflowSkipException(f"Only {len(completed_ids)} issues completed. Skipping.")

with DAG(
    'content_generation_dag',
    default_args=default_args,
    description='AI 콘텐츠 생성 및 오늘의 뉴스낵 조립',
    # 클러스터링 30분 후 실행 (한국 시간 07:30, 17:30)
    schedule_interval='30 22,8 * * *',  # 매일 22:30, 08:30 (UTC) = 07:30, 17:30 (KST)
    start_date=datetime(2026, 2, 5),
    catchup=False,
    tags=['newsnack', 'ai', 'generation'],
    max_active_runs=1,
) as dag:
    
    # Task 1: 대상 이슈 선정
    select_issues = PythonOperator(
        task_id='select_target_issues',
        python_callable=select_target_issues,
    )
    
    # Task 2: 생성 필요 여부 체크
    check_needed = PythonOperator(
        task_id='check_generation_needed',
        python_callable=check_generation_needed,
    )
    
    # Task 3: AI 기사 생성 요청
    generate_content = SimpleHttpOperator(
        task_id='generate_content',
        http_conn_id='ai_server_api',
        endpoint='/ai-articles',
        method='POST',
        data='{"issue_ids": {{ task_instance.xcom_pull(task_ids="select_target_issues", key="target_issues") | tojson }} }',
        headers=common_api_headers,
        response_check=async_response_check,
        log_response=True,
    )
    
    # Task 4: 생성 완료 대기 (Smart Wait)
    wait_completion = PythonOperator(
        task_id='wait_for_completion',
        python_callable=wait_for_completion,
    )
    
    # Task 5: 오늘의 뉴스낵 조립
    assemble_newsnack = SimpleHttpOperator(
        task_id='assemble_today_newsnack',
        http_conn_id='ai_server_api',
        endpoint='/today-newsnack',
        method='POST',
        data='{"issue_ids": {{ task_instance.xcom_pull(task_ids="wait_for_completion", key="completed_issue_ids") | tojson }} }',
        headers=common_api_headers,
        response_check=async_response_check,
        log_response=True,
    )
    
    # Task 의존성 정의 (순차 실행)
    select_issues >> check_needed >> generate_content >> wait_completion >> assemble_newsnack
