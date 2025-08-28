import uuid
import requests
from datetime import datetime
from flask import Blueprint, jsonify, request
from app.services.news_service import NewsService
import logging
import os

logger = logging.getLogger(__name__)
news_bp = Blueprint("news", __name__)
news_service = NewsService()
@news_bp.route("/", methods=["GET"])
def get_all_news():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    return jsonify(news_service.get_all_news(page, per_page))

@news_bp.route("/external", methods=["POST"])
def fetch_external_news():
    try:
        # NewsAPI configuration
        NEWS_API_KEY = os.getenv("NEWS_API_KEY", "809b9d50e9db4d1daee740f4ae53b5b8")
        NEWS_API_URL = "https://newsapi.org/v2/everything"

        # Parameters for NewsAPI
        params = {
            "q": request.args.get("q", "technology"),
            "language": request.args.get("language", "en"),
            "sortBy": "publishedAt",
            "pageSize": int(request.args.get("pageSize", "100")),
            "apiKey": NEWS_API_KEY,
        }

        # Fetch news from NewsAPI
        response = requests.get(NEWS_API_URL, params=params)

        if response.status_code != 200:
            return jsonify({"error": f"NewsAPI returned status code {response.status_code}"}), 400

        articles = response.json().get("articles", [])
        saved_articles = []

        for article in articles:
            article_data = {
                "id": str(uuid.uuid4()),
                "title": article.get("title"),
                "description": article.get("description"),
                "url": article.get("url"),
                "source": article.get("source", {}).get("name"),
                "publishedAt": datetime.strptime(
                    article.get("publishedAt"), "%Y-%m-%dT%H:%M:%SZ"
                ) if article.get("publishedAt") else None,
                "scrapedContent": article.get("content"),
                "estimatedReadTime": len(article.get("content", "").split()) // 200 + 1,
            }

            result = news_service.create_news(article_data)
            if result:
                saved_articles.append(result)

        return jsonify({
            "message": f"Successfully saved {len(saved_articles)} new articles",
            "articles": saved_articles,
        }), 201

    except Exception as e:
        logger.error(f"Failed to fetch and save news: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
