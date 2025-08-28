from typing import Optional
import logging
from app import db
from app.models.news_model import NewsArticle
from sqlalchemy import desc

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
                "data": [article.to_dict() for article in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            logger.error(f"Error fetching news articles: {str(e)}")
            return {
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "data": [],
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

    def get_latest_news(self, limit: int = 50):
        """
        Retrieve the latest news articles
        """
        try:
            latest_news = (
                NewsArticle.query.order_by(NewsArticle.publishedAt.desc())
                .limit(limit)
                .all()
            )

            return [article.to_dict() for article in latest_news]
        except Exception as e:
            logger.error(f"Error retrieving latest news: {str(e)}")
            return []
