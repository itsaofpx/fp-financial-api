import uuid
from datetime import date
from app import db
from app.models.gemini_prompt_model import GeminiPrompt
import logging

logger = logging.getLogger(__name__)


class GeminiPromptService:
    
    def create_daily_prompt(self, prompt_data):
        """สร้าง prompt รายวัน"""
        try:
            new_prompt = GeminiPrompt(
                id=str(uuid.uuid4()),
                date=date.today(),
                title=prompt_data.get('title'),
                content=prompt_data.get('content'),
                link=prompt_data.get('link'),
                articles_count=prompt_data.get('articles_count', 0)
            )
            
            db.session.add(new_prompt)
            db.session.commit()
            
            logger.info(f"Created new daily prompt for date: {date.today()}")
            return new_prompt.to_dict()
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating daily prompt: {str(e)}")
            return None

    def get_latest_prompt(self):
        """ดึง prompt ล่าสุด"""
        try:
            prompt = GeminiPrompt.query.order_by(GeminiPrompt.createdAt.desc()).first()
            return prompt.to_dict() if prompt else None
        except Exception as e:
            logger.error(f"Error getting latest prompt: {str(e)}")
            return None
