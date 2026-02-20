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
from newsnack_etl.common.enums import IssueStatusEnum

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
    화제성(기사 개수) 높은 순으로 Top N 선정 (상태 무관)
    이미 생성된 이슈는 제외하고 미처리된 이슈만 선별하여 반환
    """
    # Airflow Variables에서 설정값 가져오기
    target_count = int(Variable.get("TOP_NEWSNACK_COUNT", default_var=5))
    lookback_hours = int(Variable.get("DAG_GENERATION_LOOKBACK_HOURS", default_var=24))
    
    logger.info(f"Selecting target issues: Top {target_count}, Lookback {lookback_hours}h")
    
    # PostgresHook을 사용하여 DB 연결
    pg_hook = PostgresHook(postgres_conn_id='newsnack_db_conn')
    
    # 상태 무관하게 화제성 상위 N개 조회
    query = """
        SELECT i.id, i.processing_status, COUNT(ra.id) as article_count
        FROM issue i
        LEFT JOIN raw_article ra ON ra.issue_id = i.id
        WHERE i.batch_time >= NOW() - INTERVAL %s
        GROUP BY i.id, i.processing_status
        ORDER BY article_count DESC, i.batch_time DESC
        LIMIT %s
    """
    
    results = pg_hook.get_records(query, parameters=(f'{lookback_hours} HOURS', target_count))
    
    if not results:
        logger.warning(f"No issues found in the last {lookback_hours} hours.")
        ti.xcom_push(key='target_issues', value=[])
        ti.xcom_push(key='all_top_issues', value=[])
        return []
    
    # 전체 Top N 이슈 ID (조립용)
    all_top_ids = [row[0] for row in results]
    
    # 그 중 PENDING 또는 FAILED 상태인 이슈 ID (생성 요청용 - 재시도 포함)
    target_ids = [row[0] for row in results if row[1] in (IssueStatusEnum.PENDING.value, IssueStatusEnum.FAILED.value)]
    
    logger.info(f"Top {target_count} issues selected: {all_top_ids}")
    # 이미 완료된 것들 (전체 집합 - 생성 대상 집합)
    logger.info(f"Already completed: {set(all_top_ids) - set(target_ids)}")
    logger.info(f"Issues to generate (PENDING/FAILED): {target_ids}")
    
    # XCom에 두 가지 리스트 모두 저장
    ti.xcom_push(key='target_issues', value=target_ids)      # Task 3에서 사용
    ti.xcom_push(key='all_top_issues', value=all_top_ids)     # Task 5에서 사용 (Wait Task 통해 전달 예정)
    
    return target_ids

def check_generation_needed(ti, **context):
    """생성할 이슈 혹은 이미 생성된 이슈가 있는지 확인하여 후속 태스크 스킵 여부 결정"""
    targets = ti.xcom_pull(task_ids='select_target_issues', key='target_issues')
    all_top_ids = ti.xcom_pull(task_ids='select_target_issues', key='all_top_issues')
    
    # 전체 Top N 이슈 자체가 없으면 스킵 (lookback 기간 내 이슈 없음)
    if not all_top_ids:
        logger.info("No issues found in lookback period. Gracefully skipping DAG run.")
        raise AirflowSkipException("No issues found.")
        
    # 생성할 이슈는 없지만 이미 완료된 이슈는 있는 경우 -> 생성 단계 건너뛰고 조립 단계로 진행
    if not targets:
        logger.info(f"All top {len(all_top_ids)} issues are already completed. Checking if assembly is possible.")
        return True
    
    logger.info(f"Found {len(targets)} issues to process. Continuing...")
    return True

def wait_for_completion(ti, **context):
    """
    AI 콘텐츠 생성 완료 대기 (Smart Wait)
    새로 요청한 이슈들의 완료를 기다린 후, 기존 완료된 이슈와 합쳐서 반환
    """
    target_ids = ti.xcom_pull(task_ids='select_target_issues', key='target_issues')    # 새로 요청한 것 (PENDING)
    all_top_ids = ti.xcom_pull(task_ids='select_target_issues', key='all_top_issues') # 전체 Top N (PENDING + COMPLETED)
    
    if not all_top_ids:
        raise AirflowSkipException("No top issues found.")

    # 새로 생성할 것이 없으면 바로 전체 리스트 반환
    if not target_ids:
        logger.info("No generated issues to wait for. Returning all top issues.")
        ti.xcom_push(key='completed_issue_ids', value=all_top_ids)
        return True

    # 설정값 로드
    timeout = int(Variable.get("CONTENT_GEN_TIMEOUT", default_var=600))
    interval = int(Variable.get("CONTENT_GEN_CHECK_INTERVAL", default_var=30))
    min_completion_count = int(Variable.get("CONTENT_GEN_MIN_COMPLETION", default_var=3))

    pg_hook = PostgresHook(postgres_conn_id='newsnack_db_conn')
    
    start_time = time.time()
    
    current_completed_ids = []
    
    while time.time() - start_time < timeout:
        # 전체 Top N 이슈의 상태 확인 (기존 완료 + 새로 완료 모두 포함)
        placeholders = ','.join(['%s'] * len(all_top_ids))
        query = f"""
            SELECT id FROM issue 
            WHERE id IN ({placeholders}) 
            AND processing_status = '{IssueStatusEnum.COMPLETED.value}'
        """
        records = pg_hook.get_records(query, parameters=tuple(all_top_ids))
        current_completed_ids = [r[0] for r in records]
        
        logger.info(f"Waiting... Total Completed {len(current_completed_ids)}/{len(all_top_ids)} (Targets: {len(target_ids)})")
        
        # 1. 대상 이슈가 모두 완료되었으면 성공 (혹은 전체 Top N이 모두 완료)
        if len(current_completed_ids) == len(all_top_ids):
            logger.info("All top issues are completed!")
            ti.xcom_push(key='completed_issue_ids', value=current_completed_ids)
            return True
            
        time.sleep(interval)
    
    # Timeout 발생 시 로직
    # 마지막으로 조회된 완료 목록 사용
    logger.info(f"Timeout reached. Final completed count: {len(current_completed_ids)}")
    
    # 2. 최소 조건 충족 시 통과
    # 기준: 전체 Top N 중 완료된 개수가 min_completion_count 이상인지
    if len(current_completed_ids) >= min_completion_count:
        logger.warning(f"Timeout but sufficient issues completed ({len(current_completed_ids)} >= {min_completion_count}). Proceeding.")
        ti.xcom_push(key='completed_issue_ids', value=current_completed_ids)
        return True
    
    # 3. 최소 조건 미달 시 Skip
    else:
        logger.error(f"Insufficient issues completed ({len(current_completed_ids)} < {min_completion_count}). Skipping newsnack assembly.")
        raise AirflowSkipException(f"Only {len(current_completed_ids)} issues completed. Skipping.")

with DAG(
    'content_generation_dag',
    default_args=default_args,
    description='AI 기사 및 오늘의 뉴스낵 생성',
    # 클러스터링 30분 후 실행
    schedule_interval='30 8,22 * * *',
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
    # 새로 요청한 이슈 뿐만 아니라, 이미 완료된 이슈까지 포함하여 대기
    wait_completion = PythonOperator(
        task_id='wait_for_completion',
        python_callable=wait_for_completion,
    )
    
    # Task 5: 오늘의 뉴스낵 생성 요청
    # 전체 Top N 이슈(신규 완료 + 기존 완료)를 사용하여 조립 요청
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
