-- 카테고리 초기 데이터 삽입
INSERT INTO category (name) VALUES
('정치'), ('경제'), ('사회'), ('국제'), ('문화'), ('IT'), ('스포츠'), ('연예'), ('라이프'), ('기타')
ON CONFLICT (name) DO NOTHING;
