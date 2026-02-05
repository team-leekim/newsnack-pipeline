import os
import yaml
import time
import feedparser
import logging
import calendar
from datetime import timezone, datetime
from sqlalchemy.dialects.postgresql import insert

from database.models import RawArticle, Category
from database.connection import session_scope

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
}

def get_category_map(db):
    """DB에서 카테고리 이름:ID 매핑 정보를 가져옴"""
    categories = db.query(Category).all()
    return {cat.name: cat.id for cat in categories}

def collect_rss():
    start_time = time.perf_counter()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    sources_path = os.path.join(current_dir, 'sources.yaml')

    with session_scope() as db:
        category_map = get_category_map(db)
        
        with open(sources_path, "r", encoding='utf-8') as f:
            sources = yaml.safe_load(f)
        
        total_processed = 0
        total_new_inserted = 0

        for src in sources:
            logger.info(f"Collecting from {src['source']} - {src['category']}...")
            try:
                feed = feedparser.parse(src['url'], request_headers=USER_AGENT)
                
                cat_id = category_map.get(src['category'])
                if not cat_id:
                    logger.warning(f"Category '{src['category']}' not found in DB. Skipping...")
                    continue

                article_data_list = []

                for entry in feed.entries:
                    total_processed += 1
                    # 날짜 파싱 (없으면 현재 시간)
                    if 'published_parsed' in entry and entry.published_parsed:
                        pub_date = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), tz=timezone.utc)
                    else:
                        pub_date = datetime.now(timezone.utc)

                    article_data_list.append({
                        "title": entry.get('title', '제목 없음'),
                        "content": entry.get('summary', entry.get('description', '')),
                        "origin_url": entry.link,
                        "source": src['source'],
                        "category_id": cat_id,
                        "published_at": pub_date
                    })

                if article_data_list:
                    stmt = insert(RawArticle).values(article_data_list)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['origin_url'])
                    result = db.execute(stmt)

                    inserted_in_this_batch = result.rowcount
                    skipped_in_this_batch = len(article_data_list) - inserted_in_this_batch
                    total_new_inserted += inserted_in_this_batch

                    logger.info(f"Source: {src['source']} | New: {inserted_in_this_batch} | Skip: {skipped_in_this_batch} | Total: {len(article_data_list)}")
            except Exception:
                logger.exception(f"Error processing source {src['source']}")
                continue
            finally:
                time.sleep(0.1)

    elapsed_seconds = time.perf_counter() - start_time
    logger.info(
        f"All finished! Total: {total_processed}, New: {total_new_inserted}, Elapsed: {elapsed_seconds:.2f}s"
    )

if __name__ == "__main__":
    collect_rss()
