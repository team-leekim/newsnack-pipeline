"""
Issue Repository

Issue 테이블에 대한 DB I/O 담당
"""
from __future__ import annotations

from typing import List, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from newsnack_etl.database.models import Issue

if TYPE_CHECKING:
    from newsnack_etl.repository.article_repository import ArticleRepository


class IssueRepository:
    """Issue CRUD"""
    
    def __init__(self, db: Session, article_repo: ArticleRepository) -> None:
        self.db = db
        self.article_repo = article_repo
    
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
            self.article_repo.link_articles_to_issue(
                article_ids=article_ids,
                issue_id=new_issue.id
            )
        
        return new_issue
