import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database.connection import session_scope
from database.models import RawArticle, Issue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.60
MIN_CLUSTER_SIZE = 3
ISSUE_TIME_WINDOW_HOURS = 14

def fetch_target_articles(db):
    """최근 14시간 내, 아직 이슈가 없는 기사 조회"""
    time_limit = datetime.now(timezone.utc) - timedelta(hours=ISSUE_TIME_WINDOW_HOURS)
    logger.info(f"Fetching articles...")
    return db.query(RawArticle).filter(
        RawArticle.issue_id.is_(None),
        RawArticle.published_at >= time_limit
    ).all()


def group_articles_by_category(articles):
    """카테고리별 그룹핑"""
    grouped = defaultdict(list)
    for article in articles:
        grouped[article.category_id].append(article)
    return grouped


def create_issue_from_cluster(db, category_id, cluster_articles):
    if not cluster_articles:
        return

    # 제목 선정 (가장 긴 제목 사용. 추후 개선 가능)
    sorted_articles = sorted(cluster_articles, key=lambda x: len(x.title), reverse=True)
    representative_title = sorted_articles[0].title

    # 이슈 생성
    new_issue = Issue(
        title=representative_title, 
        category_id=category_id,
        batch_time=datetime.now(timezone.utc),
        is_processed=False
    )
    db.add(new_issue)
    db.flush()

    # 기사 매핑 (UPDATE)
    for article in cluster_articles:
        article.issue_id = new_issue.id
    
    logger.info(f"[New Issue] ID:{new_issue.id} | Articles:{len(cluster_articles)} | {representative_title[:20]}...")


def run_clustering():
    logger.info("=== Start Clustering Job ===")
    with session_scope() as db:
        articles = fetch_target_articles(db)
        if not articles:
            logger.info("No articles to cluster. Job finished.")
            return

        logger.info(f"Processing {len(articles)} articles...")
        grouped_articles = group_articles_by_category(articles)

        for cat_id, cat_articles in grouped_articles.items():
            if len(cat_articles) < MIN_CLUSTER_SIZE:
                continue
            
            # 제목 벡터화
            titles = [a.title for a in cat_articles]
            vectorizer = TfidfVectorizer(token_pattern=r'(?u)\b\w\w+\b')
            tfidf_matrix = vectorizer.fit_transform(titles)

            cosine_sim = cosine_similarity(tfidf_matrix)
            visited = [False] * len(cat_articles)
            
            for i in range(len(cat_articles)):
                if visited[i]: continue
                
                # 유사 기사 찾기
                similar_indices = [
                    j for j, score in enumerate(cosine_sim[i])
                    if score >= SIMILARITY_THRESHOLD and not visited[j]
                ]

                # MIN_CLUSTER_SIZE 이상이면 이슈 생성
                if len(similar_indices) >= MIN_CLUSTER_SIZE:
                    cluster = [cat_articles[idx] for idx in similar_indices]
                    create_issue_from_cluster(db, cat_id, cluster)
                    
                    for idx in similar_indices:
                        visited[idx] = True
    logger.info(f"=== Job Finished ===")


if __name__ == "__main__":
    run_clustering()
