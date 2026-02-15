"""
이슈 클러스터링 DAG
매일 2회(07:00, 17:00) 유사 기사를 묶어 Issue 생성
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
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

def run_issue_clustering():
    """이슈 클러스터링 실행"""
    try:
        from newsnack_etl.processor import run_clustering
        logger.info("Starting issue clustering...")
        run_clustering()
        logger.info("Issue clustering completed successfully")
    except Exception as e:
        logger.error(f"Issue clustering failed: {str(e)}")
        raise

with DAG(
    'issue_clustering_dag',
    default_args=default_args,
    description='매일 2회(07:00, 17:00 KST) 이슈 집계',
    schedule_interval='0 8,22 * * *',
    start_date=datetime(2026, 2, 5),
    catchup=False,
    tags=['newsnack', 'clustering', 'issue'],
    max_active_runs=1,  # 동시 실행 방지
) as dag:
    
    clustering_task = PythonOperator(
        task_id='cluster_articles_into_issues',
        python_callable=run_issue_clustering,
    )
