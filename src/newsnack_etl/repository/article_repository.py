"""
Article Repository

RawArticle 테이블에 대한 DB I/O 담당
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from newsnack_etl.database.models import RawArticle, Category


class ArticleRepository:
    """RawArticle CRUD"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_category_map(self) -> Dict[str, int]:
        """카테고리 이름:ID 매핑 조회"""
        categories = self.db.query(Category).all()
        return {cat.name: cat.id for cat in categories}
    
    def bulk_insert_or_ignore(self, articles: List[Dict[str, Any]]) -> int:
        """
        기사 일괄 삽입 (중복은 무시)
        
        Args:
            articles: 삽입할 기사 데이터 리스트
            
        Returns:
            실제 삽입된 기사 수
        """
        if not articles:
            return 0
        
        stmt = insert(RawArticle).values(articles)
        stmt = stmt.on_conflict_do_nothing(index_elements=['origin_url'])
        result = self.db.execute(stmt)
        return result.rowcount
    
    def fetch_unissued_articles(self, hours: int = 14) -> List[RawArticle]:
        """
        최근 N시간 내, 아직 이슈가 할당되지 않은 기사 조회
        
        Args:
            hours: 조회 기간 (시간 단위)
            
        Returns:
            이슈 미할당 기사 리스트
        """
        time_limit = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.db.query(RawArticle).filter(
            RawArticle.issue_id.is_(None),
            RawArticle.published_at >= time_limit
        ).all()
    
    def link_articles_to_issue(self, article_ids: List[int], issue_id: int) -> None:
        """
        기사들을 특정 이슈에 연결
        
        Args:
            article_ids: 연결할 기사 ID 리스트
            issue_id: 이슈 ID
        """
        self.db.query(RawArticle).filter(
            RawArticle.id.in_(article_ids)
        ).update(
            {RawArticle.issue_id: issue_id},
            synchronize_session=False
        )
