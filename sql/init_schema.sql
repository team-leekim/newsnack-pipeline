-- [1] 기초/분류 관련
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
                                      persona_code VARCHAR(20)
);

-- [2] 수집 파이프라인 관련
CREATE TABLE IF NOT EXISTS raw_article (
                                           id BIGSERIAL PRIMARY KEY,
                                           title VARCHAR(500) NOT NULL,
                                           content TEXT NOT NULL,
                                           origin_url TEXT NOT NULL UNIQUE,
                                           source VARCHAR(50) NOT NULL,
                                           category_id INT REFERENCES category(id),
                                           published_at TIMESTAMPTZ NOT NULL,
                                           crawled_at TIMESTAMPTZ DEFAULT NOW(),
                                           group_id BIGINT
);

CREATE TABLE IF NOT EXISTS issue (
                                     id BIGSERIAL PRIMARY KEY,
                                     issue_title VARCHAR(255),
                                     category_id INT REFERENCES category(id),
                                     batch_time TIMESTAMPTZ NOT NULL,
                                     raw_article_ids JSONB NOT NULL,
                                     is_processed BOOLEAN DEFAULT FALSE
);

-- [3] AI 콘텐츠 관련
CREATE TABLE IF NOT EXISTS ai_content (
                                          id BIGSERIAL PRIMARY KEY,
                                          content_type VARCHAR(20) NOT NULL, -- 'WEBTOON', 'CARD_NEWS', 'TODAY_NEWSNACK'
                                          published_at TIMESTAMPTZ DEFAULT NOW(),
                                          thumbnail_url TEXT
);

CREATE TABLE IF NOT EXISTS ai_article (
                                          ai_content_id BIGINT PRIMARY KEY REFERENCES ai_content(id),
                                          title VARCHAR(255) NOT NULL,
                                          editor_id INT REFERENCES editor(id),
                                          category_id INT REFERENCES category(id),
                                          summary JSONB, -- ["요약1", "요약2", "요약3"]
                                          body TEXT,
                                          image_data JSONB, -- {"imageUrls": ["url1", "url2"]}
                                          origin_articles JSONB -- 원본 링크 리스트
);

CREATE TABLE IF NOT EXISTS today_newsnack (
                                              ai_content_id BIGINT PRIMARY KEY REFERENCES ai_content(id),
                                              audio_data JSONB -- {"audioUrl": "...", "script": [...]}
);

-- [4] 유저 반응/통계 관련
CREATE TABLE IF NOT EXISTS reaction_count (
                                              ai_content_id BIGINT PRIMARY KEY REFERENCES ai_content(id),
                                              happy_count INT DEFAULT 0,
                                              surprised_count INT DEFAULT 0,
                                              sad_count INT DEFAULT 0,
                                              angry_count INT DEFAULT 0,
                                              empathy_count INT DEFAULT 0
);
