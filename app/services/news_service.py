from typing import Optional
import logging
from app import db
from app.models.news_model import NewsArticle

logger = logging.getLogger(__name__)

class NewsService:
    def get_all_news(self, page: int = 1, per_page: int = 10) -> dict:
        """
        Get all news articles from the database with pagination
        """
        try:
            pagination = NewsArticle.query.order_by(
                NewsArticle.publishedAt.desc()
            ).paginate(page=page, per_page=per_page)

            return {
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
                "per_page": per_page,
                "items": [article.to_dict() for article in pagination.items],
            }
        except Exception as e:
            logger.error(f"Error fetching news articles: {str(e)}")
            return {
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "items": [],
            }

    def create_news(self, news_data: dict) -> Optional[dict]:
        """
        Create a new news article
        """
        try:
            article = NewsArticle(**news_data)
            db.session.add(article)
            db.session.commit()
            return article.to_dict()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating news article: {str(e)}")
            return None
