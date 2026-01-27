import feedparser
import yaml
import logging
from datetime import datetime
from time import mktime
from src.database.connection import SessionLocal
from src.database.models import RawArticle, Category

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_category_map(db):
    """DB에서 카테고리 이름:ID 매핑 정보를 가져옴"""
    categories = db.query(Category).all()
    return {cat.name: cat.id for cat in categories}

def collect_rss():
    db = SessionLocal()
    category_map = get_category_map(db)
    
    with open("src/collector/sources.yaml", "r", encoding='utf-8') as f:
        sources = yaml.safe_load(f)
    
    total_count = 0
    new_count = 0
    
    for src in sources:
        logger.info(f"Collecting from {src['source']} - {src['category']}...")
        feed = feedparser.parse(src['url'])
        
        cat_id = category_map.get(src['category'])
        if not cat_id:
            logger.warning(f"Category '{src['category']}' not found in DB. Skipping...")
            continue

        for entry in feed.entries:
            total_count += 1
            # 날짜 파싱 (없으면 현재 시간)
            if 'published_parsed' in entry:
                pub_date = datetime.fromtimestamp(mktime(entry.published_parsed))
            else:
                pub_date = datetime.now()

            article = RawArticle(
                title=entry.get('title', '제목 없음'),
                content=entry.get('summary', entry.get('description', '')),
                source=src['source'],
                category_id=cat_id,
                published_at=pub_date
            )

            try:
                db.add(article)
                db.commit() # 하나씩 커밋해서 중복 발생 시 해당 건만 스킵
                new_count += 1
            except Exception:
                db.rollback()
                continue
                
    logger.info(f"Finished! Total processed: {total_count}, Newly added: {new_count}")
    db.close()

if __name__ == "__main__":
    collect_rss()
