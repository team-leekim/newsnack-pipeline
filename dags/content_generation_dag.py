"""
AI 콘텐츠 생성 DAG
이슈 집계 후 AI 서버에 콘텐츠 생성 요청 및 오늘의 뉴스낵 조립
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sensors.sql import SqlSensor
from airflow.models import Variable
from airflow.exceptions import AirflowSkipException
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'newsnack',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

def select_target_issues(ti, **context):
    """
    미처리 이슈 중 화제성(기사 개수) 높은 순으로 Top 5와 Extra N 선정
    Top 5: 오늘의 뉴스낵용
    Extra N: 추가 피드용
    """
    # Airflow Variables에서 설정값 가져오기
    top_count = int(Variable.get("TOP_NEWSNACK_COUNT", default_var=5))
    extra_count = int(Variable.get("EXTRA_FEED_COUNT", default_var=5))
    
    logger.info(f"Selecting issues: Top {top_count}, Extra {extra_count}")
    
    # PostgresHook을 사용하여 DB 연결
    pg_hook = PostgresHook(postgres_conn_id='newsnack_db_conn')
    
    # 미처리 이슈를 화제성(기사 개수) 순으로 조회
    # 기사 개수가 많을수록 화제성이 높다고 판단
    query = """
        SELECT i.id, COUNT(ra.id) as article_count
        FROM issue i
        LEFT JOIN raw_article ra ON ra.issue_id = i.id
        WHERE i.is_processed = FALSE
        GROUP BY i.id
        ORDER BY article_count DESC, i.batch_time DESC
        LIMIT %s
    """
    
    results = pg_hook.get_records(query, parameters=(top_count + extra_count,))
    
    if not results:
        logger.warning("No unprocessed issues found. Skipping content generation.")
        # 빈 리스트 반환
        ti.xcom_push(key='top_5_issues', value=[])
        ti.xcom_push(key='extra_issues', value=[])
        return {"top_5": [], "extra": [], "total": 0}
    
    # issue_id만 추출
    issue_ids = [row[0] for row in results]
    
    top_5 = issue_ids[:top_count]
    extra_n = issue_ids[top_count:]
    
    logger.info(f"Selected {len(top_5)} top issues and {len(extra_n)} extra issues (sorted by article count)")
    logger.info(f"Top 5 IDs: {top_5}")
    logger.info(f"Extra IDs: {extra_n}")
    
    # XCom에 저장 (다음 태스크에서 사용)
    ti.xcom_push(key='top_5_issues', value=top_5)
    ti.xcom_push(key='extra_issues', value=extra_n)
    
    return {"top_5": top_5, "extra": extra_n, "total": len(issue_ids)}

def check_generation_needed(ti, **context):
    """생성할 이슈가 있는지 확인하여 후속 태스크 스킵 여부 결정"""
    top_5 = ti.xcom_pull(
        task_ids='select_target_issues', 
        key='top_5_issues'
    )
    
    if not top_5:
        logger.info("No issues to generate. This run will be skipped.")
        raise AirflowSkipException("No unprocessed issues found. Gracefully skipping DAG run.")
    
    logger.info(f"Found {len(top_5)} issues to process. Continuing...")
    return True

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
    
    # Task 3: Top 5 AI 기사 생성 요청
    generate_top5 = SimpleHttpOperator(
        task_id='generate_top5_articles',
        http_conn_id='ai_server_api',
        endpoint='/ai-articles',
        method='POST',
        data='{"issue_ids": {{ task_instance.xcom_pull(task_ids="select_target_issues", key="top_5_issues") | tojson }} }',
        headers={
            "Content-Type": "application/json",
            "x-api-key": "{{ var.value.AI_SERVER_API_KEY }}"
        },
        response_check=lambda response: response.status_code in [200, 201],
        log_response=True,
    )
    
    # Task 4: Top 5 생성 완료 대기 (SQL Sensor)
    # is_processed가 모두 TRUE가 될 때까지 대기
    wait_top5 = SqlSensor(
        task_id='wait_for_top5_completion',
        conn_id='newsnack_db_conn',
        # Top 5 이슈가 모두 처리되었는지 확인
        # COUNT(*) = 0 이면 미처리 이슈가 없다는 의미 (완료)
        sql="""
            SELECT COUNT(*) = 0 
            FROM issue 
            WHERE id = ANY(ARRAY[{{ task_instance.xcom_pull(task_ids='select_target_issues', key='top_5_issues') | join(',') }}])
            AND is_processed = FALSE
        """,
        poke_interval=30,  # 30초마다 체크
        timeout=1800,  # 30분 타임아웃
        mode='poke',
    )
    
    # Task 5: 오늘의 뉴스낵 조립
    assemble_newsnack = SimpleHttpOperator(
        task_id='assemble_today_newsnack',
        http_conn_id='ai_server_api',
        endpoint='/today-newsnack',
        method='POST',
        headers={
            "Content-Type": "application/json",
            "x-api-key": "{{ var.value.AI_SERVER_API_KEY }}"
        },
        response_check=lambda response: response.status_code in [200, 201],
        log_response=True,
    )
    
    # Task 6: Extra 기사 생성 (Top 5와 병렬 실행 가능)
    generate_extra = SimpleHttpOperator(
        task_id='generate_extra_articles',
        http_conn_id='ai_server_api',
        endpoint='/ai-articles',
        method='POST',
        data='{"issue_ids": {{ task_instance.xcom_pull(task_ids="select_target_issues", key="extra_issues") | tojson }} }',
        headers={
            "Content-Type": "application/json",
            "x-api-key": "{{ var.value.AI_SERVER_API_KEY }}"
        },
        response_check=lambda response: response.status_code in [200, 201],
        log_response=True,
    )
    
    # Task 의존성 정의
    # 1. 이슈 선정
    # 2. 생성 필요 여부 체크
    # 3. Top 5와 Extra 생성 요청 (병렬)
    # 4. Top 5 완료 대기
    # 5. 뉴스낵 조립
    select_issues >> check_needed >> [generate_top5, generate_extra]
    generate_top5 >> wait_top5 >> assemble_newsnack
