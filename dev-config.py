import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite').replace('postgres://', 'postgresql://')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'user_uploads')
    # MAX_CONTENT_LENGTH = 4 * 1024 * 1024 * 1024  # 4GB

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Дополнительные настройки для продакшена