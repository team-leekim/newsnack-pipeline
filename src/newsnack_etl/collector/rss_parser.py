"""
RSS Parser

RSS 피드를 수집하고 DB에 저장
"""
import os
import re
import yaml
import time
import feedparser
import logging
import calendar
from importlib import resources
from datetime import timezone, datetime
from typing import List, Dict, Any

from newsnack_etl.database import session_scope
from newsnack_etl.repository import ArticleRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
}

PHOTO_ARTICLE_TITLE_PATTERNS = re.compile(
    r"^\[사진\]|^\[포토\]|^\(포토\)|"
    r"^\[포토뉴스\]|^\[경향포토\]|^\[포토 종합\]|^\[포토에세이\]"
)

def load_sources() -> List[Dict[str, str]]:
    """
    sources.yaml 파일 로드
    
    Returns:
        소스 설정 리스트
    """
    try:
        sources_path = resources.files("newsnack_etl.collector").joinpath("sources.yaml")
    except (ImportError, AttributeError):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sources_path = os.path.join(current_dir, "sources.yaml")
    
    if isinstance(sources_path, (str, os.PathLike)):
        with open(sources_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    else:
        with resources.as_file(sources_path) as sources_file:
            with open(sources_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)


def is_photo_article(title: str) -> bool:
    """
    기사 제목을 분석하여 포토뉴스인지 판별
    """
    return bool(PHOTO_ARTICLE_TITLE_PATTERNS.match(title))


def parse_rss_feed(url: str, source: str, category_id: int) -> List[Dict[str, Any]]:
    """
    RSS 피드를 파싱하여 기사 데이터 리스트로 변환 (순수 로직)
    
    Args:
        url: RSS 피드 URL
        source: 언론사명
        category_id: 카테고리 ID
        
    Returns:
        기사 데이터 딕셔너리 리스트
    """
    feed = feedparser.parse(url, request_headers=USER_AGENT)
    articles = []
    
    for entry in feed.entries:
        title = entry.get('title', '제목 없음')

        if is_photo_article(title):
            continue

        # 날짜 파싱 (없으면 현재 시간)
        if 'published_parsed' in entry and entry.published_parsed:
            pub_date = datetime.fromtimestamp(
                calendar.timegm(entry.published_parsed), 
                tz=timezone.utc
            )
        else:
            pub_date = datetime.now(timezone.utc)
        articles.append({
            "title": title,
            "content": entry.get('summary', entry.get('description', '')),
            "origin_url": entry.link,
            "source": source,
            "category_id": category_id,
            "published_at": pub_date
        })
    return articles


def collect_rss():
    """
    RSS 피드 수집 및 DB 저장 (orchestration)
    """
    start_time = time.perf_counter()
    sources = load_sources()
    
    with session_scope() as db:
        repo = ArticleRepository(db)
        category_map = repo.get_category_map()
        
        total_processed = 0
        total_new_inserted = 0
        
        for src in sources:
            logger.info(f"Collecting from {src['source']} - {src['category']}...")
            
            try:
                cat_id = category_map.get(src['category'])
                if not cat_id:
                    logger.warning(f"Category '{src['category']}' not found in DB. Skipping...")
                    continue
                
                # RSS 파싱 (순수 로직)
                articles = parse_rss_feed(src['url'], src['source'], cat_id)
                total_processed += len(articles)
                
                # DB 저장 (repository)
                inserted_count = repo.bulk_insert_or_ignore(articles)
                total_new_inserted += inserted_count
                skipped_count = len(articles) - inserted_count
                
                logger.info(
                    f"Source: {src['source']} | "
                    f"New: {inserted_count} | "
                    f"Skip: {skipped_count} | "
                    f"Total: {len(articles)}"
                )
            except Exception:
                logger.exception(f"Error processing source {src['source']}")
                continue
            finally:
                time.sleep(0.1)
    
    elapsed_seconds = time.perf_counter() - start_time
    logger.info(
        f"All finished! Total: {total_processed}, "
        f"New: {total_new_inserted}, "
        f"Elapsed: {elapsed_seconds:.2f}s"
    )


if __name__ == "__main__":
    collect_rss()
