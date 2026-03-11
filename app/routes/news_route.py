import uuid
import requests
from datetime import datetime
from flask import Blueprint, jsonify, request
from app.services.news_service import NewsService
from app.services.gemini_prompt_service import GeminiPromptService
import google.generativeai as genai
import logging
import re
import os
import math

logger = logging.getLogger(__name__)
news_bp = Blueprint("news", __name__)
news_service = NewsService()
gemini_prompt_service = GeminiPromptService()

TOOL_CARDS = [
        {
            "order": 1,
            "title": "คำนวณค่าเฉลี่ยหุ้น",
            "description": "คำนวณราคาเฉลี่ยของหุ้นเพื่อวางแผนการลงทุน",
        },
        {
            "order": 2,
            "title": "แบ่งเงินลงทุนกับเงินสดเก็บออม",
            "description": "จัดสรรเงินระหว่างการลงทุนและการออมอย่างสมดุล",
        },
        {
            "order": 3,
            "title": "แนวรับเบื้องต้น",
            "description": "วิเคราะห์แนวรับและแนวต้านของราคาหุ้น",
        },
        {
            "order": 4,
            "title": "คำนวณการขายต้นทุนแบบ FIFO",
            "description": "คำนวณกำไรขาดทุนด้วยวิธี First In First Out",
        },
        {
            "order": 5,
            "title": "คำนวณกำไรเป้าหมาย",
            "description": "กำหนดเป้าหมายกำไรและคำนวณจุดขาย",
        },
        {
            "order": 6,
            "title": "คำนวณดอกเบี้ยทบต้น",
            "description": "คำนวณการเติบโตของเงินด้วยดอกเบี้ยทบต้น",
        },
        {
            "order": 7,
            "title": "คำนวณเป้าหมายเงินปันผล",
            "description": "คำนวณจำนวนหุ้นที่ต้องซื้อเพื่อให้ได้เงินปันผลตามเป้าหมาย",
        },
        {
            "order": 8,
            "title": "คำนวณภาษีการลงทุน",
            "description": "คำนวณภาษีจากกำไรการลงทุนและการซื้อขาย",
        },
        {
            "order": 9,
            "title": "คำนวณ Stop Loss & Take Profit",
            "description": "กำหนดจุดตัดขาดทุนและเก็บกำไรอย่างมีระบบ",
        },
        {
            "order": 10,
            "title": "คำนวณ Emergency Fund",
            "description": "คำนวณเงินสำรองฉุกเฉินที่เหมาะสมกับรายได้",
        },
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)


def initialize_gemini_model():
    """
    เจาะจงใช้ Gemini 2.5 Flash Lite เพื่อความเร็วและประหยัด Quota
    """
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        
        model_name = "gemini-2.5-flash-lite" 
        
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 1024,
            }
        )
        
        
        model.generate_content("Ping") 
        logger.info(f"Successfully initialized: {model_name}")
        return model

    except Exception as e:
        logger.error(f"Gemini Init Error: {e}")
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


def translate_to_thai(model, text):
    """Translate text to Thai using Gemini; fallback to original on failure."""
    if not text:
        return text
    if not model:
        return text
    try:
        prompt = (
            "แปลข้อความต่อไปนี้เป็นภาษาไทยแบบกระชับ ชัดเจน และไม่ขยายความเกินจริง:\n"
            f"{text}"
        )
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else text
    except Exception as translate_error:
        logger.warning(f"Translation failed, using original text: {translate_error}")
        return text


def _fallback_tool_recommendation(summary_text):
    text = (summary_text or "").lower()

    score_map = {i: 0 for i in range(1, 11)}

    keyword_rules = {
        1: ["หุ้น", "ทยอยซื้อ", "ต้นทุนเฉลี่ย", "dca", "volatility"],
        2: ["จัดพอร์ต", "allocation", "สัดส่วน", "cash", "สภาพคล่อง"],
        3: ["แนวรับ", "แนวต้าน", "เทคนิค", "breakout", "support"],
        4: ["ขาย", "take profit", "realized", "fifo", "ล็อต"],
        5: ["เป้าหมาย", "target", "จุดขาย", "upside"],
        6: ["ดอกเบี้ย", "compound", "ระยะยาว", "ทบต้น"],
        7: ["ปันผล", "dividend", "yield"],
        8: ["ภาษี", "tax", "withholding", "capital gain"],
        9: ["ความเสี่ยง", "risk", "stop loss", "take profit", "ผันผวน"],
        10: ["ฉุกเฉิน", "emergency", "สำรอง", "เงินสด", "recession"],
    }

    for tool_no, keywords in keyword_rules.items():
        for kw in keywords:
            if kw in text:
                score_map[tool_no] += 1

    ranked = sorted(score_map.items(), key=lambda x: (-x[1], x[0]))
    top = [tool_no for tool_no, score in ranked if score > 0][:3]

    if len(top) < 3:
        defaults = [2, 9, 1]
        for item in defaults:
            if item not in top:
                top.append(item)
            if len(top) == 3:
                break

    return top


def recommend_tools_from_summary(summary_text):
    model = initialize_gemini_model()

    if not model:
        return _fallback_tool_recommendation(summary_text)

    tools_text = "\n".join(
        [f"{tool['order']}. {tool['title']} - {tool['description']}" for tool in TOOL_CARDS]
    )

    prompt = f"""
วิเคราะห์บทสรุปข่าวการเงินด้านล่าง แล้วเลือก "เครื่องมือที่เกี่ยวข้องที่สุด 3 อันดับแรก" จากรายการที่กำหนด

รายการเครื่องมือ:
{tools_text}

บทสรุปข่าว:
{summary_text}

กติกาการตอบ:
1) ตอบเป็นตัวเลขล้วน 3 ตัวตามลำดับความเกี่ยวข้องมาก -> น้อย
2) รูปแบบคำตอบต้องเป็น: 1,2,3
3) ห้ามมีข้อความอื่นประกอบ
"""

    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip() if response and response.text else ""
        numbers = [int(x) for x in re.findall(r"\b(10|[1-9])\b", raw_text)]

        unique_numbers = []
        for num in numbers:
            if 1 <= num <= 10 and num not in unique_numbers:
                unique_numbers.append(num)
            if len(unique_numbers) == 3:
                break

        if len(unique_numbers) < 3:
            fallback = _fallback_tool_recommendation(summary_text)
            for num in fallback:
                if num not in unique_numbers:
                    unique_numbers.append(num)
                if len(unique_numbers) == 3:
                    break

        return unique_numbers[:3]
    except Exception as e:
        logger.warning(f"Tool recommendation fallback because of AI error: {e}")
        return _fallback_tool_recommendation(summary_text)


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
        translator_model = initialize_gemini_model()

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

            title_en = article.get("title")
            description_en = article.get("description")

            translated_title = translate_to_thai(translator_model, title_en)
            translated_description = translate_to_thai(translator_model, description_en)
            translated_content = translate_to_thai(translator_model, content)

            if not any(
                keyword.lower() in translated_content.lower()
                or keyword.lower() in translated_title.lower()
                for keyword in keywords
            ):
                continue

            estimated_read_time = calculate_read_time(translated_content)

            article_data = {
                "id": str(uuid.uuid4()),
                "title": translated_title,
                "description": translated_description,
                "url": article.get("url"),
                "source": source_name,
                "publishedAt": datetime.strptime(
                    article.get("publishedAt"), "%Y-%m-%dT%H:%M:%SZ"
                )
                if article.get("publishedAt")
                else None,
                "scrapedContent": translated_content,
                "estimatedReadTime": estimated_read_time,
            }
            result = news_service.create_news(article_data)
            if result:
                saved_articles.append(result)

            if len(saved_articles) >= 50:
                break

        if saved_articles:
            try:
                latest_news = news_service.get_latest_news(limit=49)
                if latest_news:
                    summary = generate_ai_news_summary(latest_news)
                    
                    if summary.get('title') != "ไม่สามารถสร้างบทวิเคราะห์ได้":
                        prompt_data = {
                            'title': summary.get('title'),
                            'content': summary.get('content'),
                            'link': summary.get('link'),
                            'articles_count': len(latest_news)
                        }
                        saved_prompt = gemini_prompt_service.create_daily_prompt(prompt_data)
                        if saved_prompt:
                            logger.info("Successfully created daily Gemini prompt")
                    else:
                        logger.warning("AI Summary generation failed, skipping database save.")
                    
            except Exception as prompt_error:
                logger.error(f"Failed to create Gemini prompt: {str(prompt_error)}")

        return jsonify(
            {
                "message": f"Successfully saved {len(saved_articles)} new articles and generated AI summary",
                "articles": saved_articles,
            }
        ), 201

    except Exception as e:
        logger.error(f"Failed to fetch and save news: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    
    
@news_bp.route("/prompt/latest", methods=["GET"])
def get_latest_prompt():
    try:
        prompt = gemini_prompt_service.get_latest_prompt()
        
        if not prompt:
            return jsonify(
                {
                    "title": "ไม่มีบทวิเคราะห์",
                    "content": "ยังไม่มีบทวิเคราะห์ในระบบ กรุณาลองใหม่ภายหลัง",
                    "link": None,
                }
            ), 404
            
        return jsonify(prompt), 200
        
    except Exception as e:
        logger.error(f"Failed to get latest prompt: {str(e)}", exc_info=True)
        return jsonify(
            {
                "title": "เกิดข้อผิดพลาด",
                "content": "ไม่สามารถดึงบทวิเคราะห์ได้ กรุณาลองใหม่ภายหลัง",
                "link": None,
            }
        ), 500
@news_bp.route("/ai", methods=["POST"])
def generate_daily_top_news():
    try:
        latest_news = news_service.get_latest_news(limit=49)

        if not latest_news:
            return jsonify({"error": "ไม่พบข้อมูลข่าวในระบบ"}), 404

        summary = generate_ai_news_summary(latest_news)
        
        if summary.get('title') != "ไม่สามารถสร้างบทวิเคราะห์ได้":
            prompt_data = {
                'title': summary.get('title'),
                'content': summary.get('content'),
                'link': summary.get('link'),
                'articles_count': len(latest_news)
            }
            
            saved_prompt = gemini_prompt_service.create_daily_prompt(prompt_data)
            
            if saved_prompt:
                logger.info("Successfully saved AI summary from /ai endpoint")
                return jsonify(saved_prompt), 200
            
            return jsonify({"error": "บันทึกข้อมูลลงฐานข้อมูลล้มเหลว"}), 500
        
        return jsonify({
            "title": summary.get('title'),
            "content": summary.get('content'),
            "error": "AI Generation Failed"
        }), 503

    except Exception as e:
        logger.error(f"Critical error in /ai endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": "เกิดข้อผิดพลาดภายในระบบ"}), 500


@news_bp.route("/tools/recommend", methods=["GET"])
def recommend_tools():
    try:
        summary_text = request.args.get("summary") or request.args.get("content")

        if not summary_text:
            latest_prompt = gemini_prompt_service.get_latest_prompt()
            if latest_prompt and latest_prompt.get("content"):
                summary_text = latest_prompt.get("content")

        if not summary_text:
            return jsonify({"error": "ไม่พบบทสรุปข่าวสำหรับวิเคราะห์"}), 400

        recommendations = recommend_tools_from_summary(summary_text)
        return jsonify({"tools": recommendations}), 200

    except Exception as e:
        logger.error(f"Failed to recommend tools: {str(e)}", exc_info=True)
        return jsonify({"error": "ไม่สามารถแนะนำเครื่องมือได้"}), 500

def generate_ai_news_summary(articles):
    try:
        model = initialize_gemini_model()

        if not model:
            return {
                "title": "ไม่สามารถสร้างบทวิเคราะห์ได้",
                "content": "ระบบขัดข้อง กรุณาลองใหม่ในภายหลัง",
                "link": None,
            }

        # เตรียมวันที่ปัจจุบัน พ.ศ. 2569
        now = datetime.now()
        thai_months = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
        formatted_date = f"{now.day} {thai_months[now.month]} {now.year + 543}"

        articles_context = "\n\n".join(
            [
                f"ข่าวที่ {idx+1}:\n"
                f"- หัวข้อ: {article.get('title')}\n"
                f"- แหล่งข่าว: {article.get('source')}\n"
                f"- เนื้อหาสำคัญ: {article.get('description')}"
                for idx, article in enumerate(articles[:10])
            ]
        )

        prompt = f"""
        จงสวมบทบาทเป็น "หัวหน้านักกลยุทธ์การลงทุนอาวุโส" (Senior Investment Strategist)
        หน้าที่ของคุณคือเขียนบทวิเคราะห์สถานการณ์ตลาดการเงินโลกประจำวันให้แก่กลุ่มนักลงทุนรุ่นใหม่

        ข้อมูลวันที่ปัจจุบัน: {formatted_date}
        บริบทข่าวสารล่าสุดที่รวบรวมมา:
        {articles_context}

        คำแนะนำในการเขียน (Strict Instructions):
        1. **บรรทัดแรก** ต้องขึ้นต้นด้วย: "บทวิเคราะห์ตลาดการเงินและการลงทุนประจำวัน: {formatted_date}"
        2. **ห้ามใช้ปี พ.ศ. อื่น** นอกจาก {now.year + 543} ในการเกริ่นนำ หากข่าวระบุปีเก่า ให้วิเคราะห์ว่าเป็นผลกระทบต่อเนื่องมาจนถึงปัจจุบัน
        3. ใช้ภาษาไทยระดับทางการที่อ่านง่าย มีความน่าเชื่อถือ และวิเคราะห์ลึกถึง "สาเหตุและผลกระทบ" (Impact Analysis)
        4. หลีกเลี่ยงการสรุปข่าวทีละข่าว แต่ให้ "ร้อยเรียง" ข่าวทั้งหมดเข้าด้วยกันเป็นภาพรวมเดียว

        โครงสร้างบทวิเคราะห์ (ห้ามเปลี่ยนหัวข้อ):
        ---
        บทวิเคราะห์ตลาดการเงิน: แนวโน้มและโอกาสการลงทุนประจำวัน
        บทวิเคราะห์ตลาดการเงินและการลงทุนประจำวัน: {formatted_date}

        [1. สรุปภาพรวมสภาวะตลาดการเงิน]: (วิเคราะห์ความเคลื่อนไหวของตลาดโลกในรอบ 24 ชั่วโมงที่ผ่านมา)
        
        [2. ปัจจัยสำคัญที่ขับเคลื่อนตลาด]: (เจาะลึก 2-3 ประเด็นที่ส่งผลกระทบต่อจิตวิทยานักลงทุนในขณะนี้)
        
        [3. กลยุทธ์การบริหารพอร์ตการลงทุน]: (คำแนะนำในการปรับสัดส่วนสินทรัพย์หรือการรับมือความเสี่ยง)
        
        [4. มุมมองและคาดการณ์ระยะสั้น]: (การพยากรณ์ทิศทางตลาดในช่วงสัปดาห์นี้)
        ---

        ข้อกำหนดพิเศษ:
        - ความยาว 20-30 บรรทัด
        - ในแต่ละหัวข้อย่อยสรุปให้กระชับในย่อหน้าเดียวห้ามมีหลายย่อหน้า
        - เน้นการเว้นวรรคและย่อหน้าที่อ่านง่ายบนมือถือ
        - หากมีข่าวเกี่ยวกับ Warren Buffett หรือการเปลี่ยนผ่านผู้นำ ให้เน้นวิเคราะห์เรื่อง "ความเชื่อมั่นเชิงโครงสร้าง" (Structural Confidence)
        """

        response = model.generate_content(prompt)

        recommended_link = next(
            (article.get("url") for article in articles if article.get("url")),
            "https://www.set.or.th/th/market/market-highlight",
        )

        return {
            "title": "บทวิเคราะห์ตลาดการเงิน: แนวโน้มและโอกาสการลงทุนประจำวัน",
            "content": response.text.strip(),
            "link": recommended_link,
        }

    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการสร้างบทวิเคราะห์: {e}", exc_info=True)
        return {
            "title": "บทวิเคราะห์ตลาดการเงิน",
            "content": "ขออภัย ระบบไม่สามารถประมวลผลบทวิเคราะห์ได้ในขณะนี้",
            "link": "https://www.set.or.th/th/market/market-highlight",
        }