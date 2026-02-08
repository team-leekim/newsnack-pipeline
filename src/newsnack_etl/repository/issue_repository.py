"""
Issue Repository

Issue 테이블에 대한 DB I/O 담당
"""
from typing import List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from newsnack_etl.database.models import Issue, RawArticle


class IssueRepository:
    """Issue CRUD"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_issue(
        self, 
        title: str, 
        category_id: int,
        article_ids: List[int]
    ) -> Issue:
        """
        이슈 생성 및 기사 연결
        
        Args:
            title: 이슈 제목
            category_id: 카테고리 ID
            article_ids: 이슈에 포함될 기사 ID 리스트
            
        Returns:
            생성된 Issue 객체
        """
        # 이슈 생성
        new_issue = Issue(
            title=title,
            category_id=category_id,
            batch_time=datetime.now(timezone.utc),
            is_processed=False
        )
        self.db.add(new_issue)
        self.db.flush()  # ID 획득
        
        # 기사 연결
        if article_ids:
            self.db.query(RawArticle).filter(
                RawArticle.id.in_(article_ids)
            ).update(
                {RawArticle.issue_id: new_issue.id},
                synchronize_session=False
            )
        
        return new_issue
