from datetime import datetime, timezone, date
from app import db
import uuid


class GeminiPrompt(db.Model):
    __tablename__ = "GeminiPrompt"
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    date = db.Column(db.Date, nullable=False, index=True)
    title = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    link = db.Column(db.Text, nullable=True)
    articles_count = db.Column(db.Integer, nullable=False, default=0)
    createdAt = db.Column(
        db.DateTime, 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )
    updatedAt = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "title": self.title,
            "content": self.content,
            "link": self.link,
            "articles_count": self.articles_count,
            "createdAt": self.createdAt.isoformat() if self.createdAt else None,
            "updatedAt": self.updatedAt.isoformat() if self.updatedAt else None,
        }
