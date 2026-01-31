-- 기초/분류 관련
CREATE TABLE IF NOT EXISTS category (
                                        id SERIAL PRIMARY KEY,
                                        name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS editor (
                                      id SERIAL PRIMARY KEY,
                                      name VARCHAR(50) NOT NULL,
                                      profile_image_url TEXT,
                                      description TEXT,
                                      keywords JSONB, -- ["#친절한", "#테크"]
                                      persona_prompt TEXT
);

CREATE TABLE IF NOT EXISTS editor_category (
    id BIGSERIAL PRIMARY KEY,
    editor_id INT NOT NULL,
    category_id INT NOT NULL,
    
    FOREIGN KEY (editor_id) REFERENCES editor(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE,

    CONSTRAINT uk_editor_category UNIQUE (editor_id, category_id)
);

-- 수집 파이프라인 관련
CREATE TABLE IF NOT EXISTS issue (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255),
    category_id INT REFERENCES category(id),
    batch_time TIMESTAMPTZ NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_issue_batch_time ON issue(batch_time);

-- 수집 기사 테이블 (Many)
CREATE TABLE IF NOT EXISTS raw_article (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    origin_url TEXT NOT NULL UNIQUE,
    source VARCHAR(50) NOT NULL,
    category_id INT REFERENCES category(id),
    issue_id BIGINT REFERENCES issue(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ NOT NULL,
    crawled_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_raw_article_published_at ON raw_article(published_at);
CREATE INDEX IF NOT EXISTS idx_raw_article_cluster_target ON raw_article(issue_id, published_at);

-- AI 콘텐츠 관련
-- [AI 기사: 웹툰/카드뉴스]
CREATE TABLE IF NOT EXISTS ai_article (
    id BIGSERIAL PRIMARY KEY,
    issue_id BIGINT, -- 상위 이슈 ID (FK 제약 없음, DW 전환 대비)
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('WEBTOON', 'CARD_NEWS')),
    title VARCHAR(255) NOT NULL,
    thumbnail_url TEXT,
    editor_id INT REFERENCES editor(id),
    category_id INT REFERENCES category(id),
    summary JSONB, -- ["요약1", "요약2", "요약3"]
    body TEXT, -- 에디터 재작성 본문
    image_data JSONB, -- {"image_urls": ["url1", "url2"]}
    origin_articles JSONB, -- 연관된 원본 기사 링크 리스트 (최대 3개)
    published_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_article_published_at ON ai_article(published_at);

-- [오늘의 뉴스낵: 오디오 브리핑]
CREATE TABLE IF NOT EXISTS today_newsnack (
    id BIGSERIAL PRIMARY KEY,
    audio_url TEXT NOT NULL,
    -- briefing_articles: [{ "article_id": 101, "title": "엔비디아 역대급 실적 발표", "thumbnail_url": "https://example.com", "start_time": 0.0, "end_time": 20.5 }, ...]
    briefing_articles JSONB NOT NULL, 
    published_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_today_newsnack_published_at ON today_newsnack(published_at);

-- 유저 반응 및 통계 (AI 기사 전용)
CREATE TABLE IF NOT EXISTS reaction_count (
    article_id BIGINT PRIMARY KEY REFERENCES ai_article(id) ON DELETE CASCADE,
    happy_count INT DEFAULT 0,
    surprised_count INT DEFAULT 0,
    sad_count INT DEFAULT 0,
    angry_count INT DEFAULT 0,
    empathy_count INT DEFAULT 0
);
