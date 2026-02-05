"""
뉴스 수집 DAG
매 30분마다 언론사 RSS를 크롤링하여 raw_article 테이블에 적재
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'newsnack',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

def run_rss_collector():
    """RSS 수집 실행"""
    # src 디렉토리를 Python path에 추가
    sys.path.insert(0, '/opt/airflow/src')
    
    try:
        from collector.rss_parser import collect_rss
        logger.info("Starting RSS collection...")
        collect_rss()
        logger.info("RSS collection completed successfully")
    except Exception as e:
        logger.error(f"RSS collection failed: {str(e)}")
        raise

with DAG(
    'news_collection_dag',
    default_args=default_args,
    description='매 30분마다 언론사 RSS 수집',
    schedule_interval='*/30 * * * *',  # 매 30분
    start_date=datetime(2026, 2, 1),
    catchup=False,
    tags=['newsnack', 'collection', 'rss'],
    max_active_runs=1,  # 동시 실행 방지
) as dag:
    
    collect_task = PythonOperator(
        task_id='collect_rss_feeds',
        python_callable=run_rss_collector,
    )
