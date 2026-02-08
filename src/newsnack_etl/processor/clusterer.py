"""
Article Clusterer

유사 기사를 군집화하여 이슈 생성
"""
import logging
from collections import defaultdict
from typing import List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from newsnack_etl.database import session_scope
from newsnack_etl.database.models import RawArticle
from newsnack_etl.repository import ArticleRepository, IssueRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.60
MIN_CLUSTER_SIZE = 3
ISSUE_TIME_WINDOW_HOURS = 14


def cluster_articles_by_similarity(
    articles: List[RawArticle],
    threshold: float = SIMILARITY_THRESHOLD,
    min_size: int = MIN_CLUSTER_SIZE
) -> List[List[RawArticle]]:
    """
    기사 제목 유사도 기반 클러스터링 (순수 로직)
    
    Args:
        articles: 클러스터링할 기사 리스트
        threshold: 유사도 임계값 (0.0 ~ 1.0)
        min_size: 최소 클러스터 크기
        
    Returns:
        클러스터 리스트 (각 클러스터는 기사 리스트)
    """
    if len(articles) < min_size:
        return []
    
    # 제목 벡터화
    titles = [a.title for a in articles]
    vectorizer = TfidfVectorizer(token_pattern=r'(?u)\b\w\w+\b')
    tfidf_matrix = vectorizer.fit_transform(titles)
    
    # 코사인 유사도 계산
    cosine_sim = cosine_similarity(tfidf_matrix)
    
    # 클러스터링
    visited = [False] * len(articles)
    clusters = []
    
    for i in range(len(articles)):
        if visited[i]:
            continue
        
        # 유사 기사 찾기
        similar_indices = [
            j for j, score in enumerate(cosine_sim[i])
            if score >= threshold and not visited[j]
        ]
        
        # 최소 크기 이상이면 클러스터로 등록
        if len(similar_indices) >= min_size:
            cluster = [articles[idx] for idx in similar_indices]
            clusters.append(cluster)
            
            for idx in similar_indices:
                visited[idx] = True
    
    return clusters


def select_representative_title(cluster: List[RawArticle]) -> str:
    """
    클러스터에서 대표 제목 선정
    
    Args:
        cluster: 기사 클러스터
        
    Returns:
        대표 제목
    """
    # 가장 긴 제목 선택 (추후 개선 가능)
    sorted_articles = sorted(cluster, key=lambda x: len(x.title), reverse=True)
    return sorted_articles[0].title


def run_clustering():
    """
    이슈 클러스터링 및 DB 저장 (orchestration)
    """
    logger.info("=== Start Clustering Job ===")
    
    with session_scope() as db:
        article_repo = ArticleRepository(db)
        issue_repo = IssueRepository(db)
        
        # 미처리 기사 조회
        articles = article_repo.fetch_unissued_articles(hours=ISSUE_TIME_WINDOW_HOURS)
        
        if not articles:
            logger.info("No articles to cluster. Job finished.")
            return
        
        logger.info(f"Processing {len(articles)} articles...")
        
        # 카테고리별 그룹핑
        grouped_articles = defaultdict(list)
        for article in articles:
            grouped_articles[article.category_id].append(article)
        
        # 카테고리별 클러스터링
        for cat_id, cat_articles in grouped_articles.items():
            if len(cat_articles) < MIN_CLUSTER_SIZE:
                continue
            
            # 클러스터링 실행 (순수 로직)
            clusters = cluster_articles_by_similarity(
                cat_articles,
                threshold=SIMILARITY_THRESHOLD,
                min_size=MIN_CLUSTER_SIZE
            )
            
            # 이슈 생성 (repository)
            for cluster in clusters:
                title = select_representative_title(cluster)
                article_ids = [a.id for a in cluster]
                
                new_issue = issue_repo.create_issue(
                    title=title,
                    category_id=cat_id,
                    article_ids=article_ids
                )
                
                logger.info(
                    f"[New Issue] ID:{new_issue.id} | "
                    f"Articles:{len(cluster)} | "
                    f"{title[:20]}..."
                )
    
    logger.info("=== Job Finished ===")


if __name__ == "__main__":
    run_clustering()
