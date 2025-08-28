from datetime import datetime, timezone
from app import db


class NewsArticle(db.Model):
    __tablename__ = "NewsArticle"
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.Text, nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.Text, unique=True, index=True)
    source = db.Column(db.Text, nullable=True)
    publishedAt = db.Column(db.DateTime, nullable=True)
    scrapedContent = db.Column(db.Text, nullable=True)
    estimatedReadTime = db.Column(db.Integer, nullable=True)
    createdAt = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
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
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "publishedAt": self.publishedAt.isoformat() if self.publishedAt else None,
            "scrapedContent": self.scrapedContent,
            "estimatedReadTime": self.estimatedReadTime,
            "createdAt": self.createdAt.isoformat() if self.createdAt else None,
            "updatedAt": self.updatedAt.isoformat() if self.updatedAt else None,
        }
