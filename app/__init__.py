import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize Flask and SQLAlchemy
db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # Database configuration
    DB_USER = os.getenv("DB_USERNAME", "fp-finance")
    DB_PASS = os.getenv("DB_PASSWORD", "0000")
    DB_HOST = os.getenv("DB_HOST", "host.docker.internal")
    DB_PORT = os.getenv("DB_PORT", "5433")
    DB_NAME = os.getenv("DB_NAME", "fp-admin")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        # Import routes - Remove 'app.' prefix since we're already in the app directory
        from .routes.news_route import news_bp

        # Register blueprints
        app.register_blueprint(news_bp, url_prefix="/news")

        # Create database tables
        db.create_all()

    return app
