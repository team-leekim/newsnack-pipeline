from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Category(Base):
    __tablename__ = "category"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

class RawArticle(Base):
    __tablename__ = "raw_article"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    origin_url = Column(Text, unique=True, nullable=False)
    source = Column(String(50), nullable=False)
    category_id = Column(Integer, ForeignKey("category.id"))
    published_at = Column(DateTime(timezone=True), nullable=False)
    crawled_at = Column(DateTime(timezone=True), server_default=func.now())
    group_id = Column(BigInteger, nullable=True)