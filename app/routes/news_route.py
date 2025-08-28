import uuid
import requests
from datetime import datetime
from flask import Blueprint, jsonify, request
from app.services.news_service import NewsService
import google.generativeai as genai
import logging
import re
import os
import math

logger = logging.getLogger(__name__)
news_bp = Blueprint("news", __name__)
news_service = NewsService()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyCQtwJMf6N7ZWPpzQ-hhN1krk2EnZmJDz4")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyDQMvla98RH0xfwAguSbOgHLyQJVhvjBrQ")
genai.configure(api_key=GOOGLE_API_KEY)


def initialize_gemini_model():
    """
    Robust Gemini model initialization with extensive error handling
    """
    try:
        genai.configure(api_key=GOOGLE_API_KEY)

        try:
            models = genai.list_models()
            available_models = [
                m.name
                for m in models
                if "generateContent" in m.supported_generation_methods
            ]

            logger.info(f"Total available models: {len(available_models)}")
            logger.info(f"Available models: {available_models}")

        except Exception as list_error:
            logger.error(f"Failed to list models: {list_error}")
            available_models = []

        model_candidates = [
            "gemini-2.0-flash",
            "gemini-pro",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-flash",
            "gemini-1.5-pro-latest",
        ]

        for candidate in model_candidates:
            try:
                model = genai.GenerativeModel(candidate)
                test_response = model.generate_content(
                    "Hello, can you confirm you're working?"
                )
                logger.info(f"Successfully initialized and tested model: {candidate}")
                return model
            except Exception as model_error:
                logger.warning(
                    f"Model {candidate} initialization failed: {model_error}"
                )

        logger.error("No Gemini model could be successfully initialized")
        return None

    except Exception as e:
        logger.error(f"Critical error in model initialization: {e}", exc_info=True)
        return None


def calculate_read_time(content):
    if content is None:
        return 5

    match = re.search(r"\[.*?(\d+)\s*chars\]", content)

    if match:
        chars_count = int(match.group(1))
        total_chars = len(content.split("[")[0]) + chars_count
    else:
        total_chars = len(content)

    word_count = total_chars // 5
    read_time = math.ceil(word_count / 200)

    rounded_time = round(read_time / 5) * 5
    rounded_time = max(5, min(rounded_time, 120))

    return rounded_time


@news_bp.route("/", methods=["GET"])
def get_all_news():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    return jsonify(news_service.get_all_news(page, per_page))


@news_bp.route("/external", methods=["POST"])
def fetch_external_news():
    try:
        NEWS_API_KEY = os.getenv("NEWS_API_KEY", "2c2fc7c86f0a423da4c2dd31d78cedcf")
        NEWS_API_URL = "https://newsapi.org/v2/everything"

        keywords = [
            "S&P 500",
            "NASDAQ 100",
            "Dow Jones",
            "Stock Market",
            "Market Trends",
            "Investing",
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "TSLA",
            "META",
            "GOOG",
            "V",
            "MA",
            "UNH",
            "JPM",
            "JNJ",
            "WMT",
            "XOM",
            "Market Capitalization",
            "Stock Performance",
            "Financial Analysis",
            "Investment Strategy",
            "Market Forecast",
            "Economic Trends",
        ]

        search_query = " OR ".join([f'"{keyword}"' for keyword in keywords])

        params = {
            "q": search_query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 50,
            "apiKey": NEWS_API_KEY,
            "domains": "forbes.com,aljazeera.com,cnbc.com",
        }

        response = requests.get(NEWS_API_URL, params=params)

        if response.status_code != 200:
            return jsonify(
                {"error": f"NewsAPI returned status code {response.status_code}"}
            ), 400

        articles = response.json().get("articles", [])
        saved_articles = []
        unique_articles = set()

        for article in articles:
            article_hash = hash(article.get("title", "") + article.get("url", ""))
            if article_hash in unique_articles:
                continue
            unique_articles.add(article_hash)

            source_name = article.get("source", {}).get("name", "")
            if source_name not in ["Forbes", "Al Jazeera English", "CNBC"]:
                continue

            content = article.get("content") or article.get("description") or ""

            if not any(
                keyword.lower() in content.lower()
                or keyword.lower() in article.get("title", "").lower()
                for keyword in keywords
            ):
                continue

            estimated_read_time = calculate_read_time(content)

            article_data = {
                "id": str(uuid.uuid4()),
                "title": article.get("title"),
                "description": article.get("description"),
                "url": article.get("url"),
                "source": source_name,
                "publishedAt": datetime.strptime(
                    article.get("publishedAt"), "%Y-%m-%dT%H:%M:%SZ"
                )
                if article.get("publishedAt")
                else None,
                "scrapedContent": content,
                "estimatedReadTime": estimated_read_time,
            }

            result = news_service.create_news(article_data)
            if result:
                saved_articles.append(result)

            if len(saved_articles) >= 50:
                break

        return jsonify(
            {
                "message": f"Successfully saved {len(saved_articles)} new articles",
                "articles": saved_articles,
            }
        ), 201

    except Exception as e:
        logger.error(f"Failed to fetch and save news: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@news_bp.route("/ai", methods=["POST"])
def generate_daily_top_news():
    try:
        latest_news = news_service.get_latest_news(limit=30)

        if not latest_news:
            return jsonify(
                {
                    "title": "ไม่สามารถสร้างบทวิเคราะห์ได้",
                    "content": "ระบบขัดข้อง กรุณาลองใหม่ในภายหลัง",
                    "link": None,
                }
            ), 404

        summary = generate_ai_news_summary(latest_news)

        return jsonify(summary), 200

    except Exception as e:
        logger.error(f"Failed to generate daily top news: {str(e)}", exc_info=True)
        return jsonify(
            {
                "title": "ไม่สามารถสร้างบทวิเคราะห์ได้",
                "content": "ระบบขัดข้อง กรุณาลองใหม่ในภายหลัง",
                "link": None,
            }
        ), 500


def generate_ai_news_summary(articles):
    try:
        model = initialize_gemini_model()

        if not model:
            return {
                "title": "ไม่สามารถสร้างบทวิเคราะห์ได้",
                "content": "ระบบขัดข้อง กรุณาลองใหม่ในภายหลัง",
                "link": None,
            }

        articles_context = "\n\n".join(
            [
                f"ข่าวที่ {idx+1}:\n"
                f"- หัวข้อ: {article.get('title', 'ไม่มีหัวข้อ')}\n"
                f"- แหล่งที่มา: {article.get('source', 'ไม่ทราบแหล่งที่มา')}\n"
                f"- วันที่: {article.get('publishedAt', 'ไม่มีข้อมูลวันที่')}\n"
                f"- คำอธิบายย่อ: {article.get('description', 'ไม่มีคำอธิบาย')}"
                for idx, article in enumerate(articles[:10])
            ]
        )

        prompt = f"""
        บทวิเคราะห์ตลาดการเงินและการลงทุนประจำวัน

        คำแนะนำในการเขียน:
        - เขียนอย่างละเอียด เป็นมืออาชีพ
        - ใช้ภาษาที่เข้าใจง่าย กระชับ และน่าสนใจ
        - ครอบคลุมประเด็นสำคัญทางเศรษฐกิจและการเงิน
        - ให้มุมมองเชิงลึกที่เป็นประโยชน์ต่อนักลงทุน
        - อธิบายแนวโน้มและปัจจัยที่ส่งผลกระทบ

        บริบทข่าวล่าสุด:
        {articles_context}

        โครงสร้างบทวิเคราะห์:
        1. สรุปภาพรวมตลาดการเงินในวันนี้
        2. วิเคราะห์แนวโน้มและปัจจัยสำคัญ
        3. ผลกระทบต่อการลงทุนและเศรษฐกิจ
        4. คำแนะนำเชิงปฏิบัติสำหรับนักลงทุน
        5. มุมมองและคาดการณ์ในอนาคต

        ข้อกำหนดพิเศษ:
        - เขียนความยาวประมาณ 20-25 บรรทัด
        - ใช้ข้อมูลเชิงลึกและวิเคราะห์อย่างเป็นระบบ
        - นำเสนอมุมมองที่รอบด้านและน่าเชื่อถือ
        - เน้นให้ความรู้และสร้างความเข้าใจ

        โปรดเขียนบทวิเคราะห์เป็นภาษาไทยที่มีคุณภาพ 
        ให้ข้อมูลที่เป็นประโยชน์และน่าสนใจ
        """

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        recommended_link = next(
            (article.get("url") for article in articles if article.get("url")),
            "https://www.set.or.th/th/market/market-highlight",
        )

        summary = {
            "title": "บทวิเคราะห์ตลาดการเงิน: แนวโน้มและโอกาสการลงทุนประจำวัน",
            "content": response.text.strip(),
            "link": recommended_link,
        }

        return summary

    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการสร้างบทวิเคราะห์: {e}", exc_info=True)
        return {
            "title": "บทวิเคราะห์ตลาดการเงิน",
            "content": "ระบบขัดข้อง ไม่สามารถสร้างบทวิเคราะห์ได้ในขณะนี้ กรุณาลองใหม่ในภายหลัง",
            "link": "https://www.set.or.th/th/market/market-highlight",
        }
