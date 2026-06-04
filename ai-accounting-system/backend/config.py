import os
import sys
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _require_env(key: str) -> str:
    """Require an environment variable, exit if missing."""
    value = os.environ.get(key)
    if not value:
        print(f"[FATAL] Missing required environment variable: {key}")
        print(f"        Please set it in .env file. See .env.example for reference.")
        sys.exit(1)
    return value


class Config:
    """Base configuration - all secrets read from environment variables."""

    # Flask
    SECRET_KEY = _require_env('SECRET_KEY')
    DEBUG = False

    # Database
    SQLALCHEMY_DATABASE_URI = _require_env('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '10')),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '3600')),
        'pool_pre_ping': True,
    }

    # JWT
    JWT_SECRET_KEY = _require_env('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get('JWT_ACCESS_MINUTES', '15')))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get('JWT_REFRESH_DAYS', '30')))

    # DeepSeek AI
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')

    # LLM Configuration
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'deepseek')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'deepseek-chat')
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '2000'))
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '30'))

    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Celery
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)

    # Cache (Flask-Caching)
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'RedisCache')
    CACHE_REDIS_URL = os.environ.get('CACHE_REDIS_URL', REDIS_URL)
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '300'))

    # Rate Limiting (defaults to REDIS_URL so production uses Redis)
    RATELIMIT_STORAGE_URI = os.environ.get(
        'RATELIMIT_STORAGE_URI',
        os.environ.get('REDIS_URL', 'memory://')
    )

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_DIR = os.environ.get('LOG_DIR', 'logs')

    # Frontend URL (for email links)
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

    # Account lockout
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', '5'))
    LOCKOUT_DURATION_MINUTES = int(os.environ.get('LOCKOUT_DURATION_MINUTES', '30'))

    # Avatar upload
    AVATAR_MAX_SIZE_MB = int(os.environ.get('AVATAR_MAX_SIZE_MB', '2'))
    AVATAR_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

    # Object Storage
    STORAGE_PROVIDER = os.environ.get('STORAGE_PROVIDER', 'local')  # local|minio|oss|cos
    STORAGE_COMPRESS_QUALITY = int(os.environ.get('STORAGE_COMPRESS_QUALITY', '85'))
    STORAGE_THUMBNAIL_SIZES = [150, 300]

    # MinIO
    MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'localhost:9000')
    MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', '')
    MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', '')
    MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'ai-accounting')
    MINIO_SECURE = os.environ.get('MINIO_SECURE', 'false').lower() == 'true'

    # Alibaba Cloud OSS
    OSS_ACCESS_KEY_ID = os.environ.get('OSS_ACCESS_KEY_ID', '')
    OSS_ACCESS_KEY_SECRET = os.environ.get('OSS_ACCESS_KEY_SECRET', '')
    OSS_ENDPOINT = os.environ.get('OSS_ENDPOINT', '')
    OSS_BUCKET = os.environ.get('OSS_BUCKET', '')

    # Tencent Cloud COS
    COS_SECRET_ID = os.environ.get('COS_SECRET_ID', '')
    COS_SECRET_KEY = os.environ.get('COS_SECRET_KEY', '')
    COS_REGION = os.environ.get('COS_REGION', '')
    COS_BUCKET = os.environ.get('COS_BUCKET', '')

    # Stripe
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Alipay
    ALIPAY_APP_ID = os.environ.get('ALIPAY_APP_ID', '')
    ALIPAY_PRIVATE_KEY = os.environ.get('ALIPAY_PRIVATE_KEY', '')
    ALIPAY_PUBLIC_KEY = os.environ.get('ALIPAY_PUBLIC_KEY', '')
    ALIPAY_NOTIFY_URL = os.environ.get('ALIPAY_NOTIFY_URL', '')
    ALIPAY_RETURN_URL = os.environ.get('ALIPAY_RETURN_URL', '')

    # Security
    FERNET_KEY = os.environ.get('FERNET_KEY', '')
    TOTP_ISSUER = os.environ.get('TOTP_ISSUER', 'AI Accounting')
    REQUEST_SIGNING_SECRET = os.environ.get('REQUEST_SIGNING_SECRET', '')

    # SMTP Email
    SMTP_HOST = os.environ.get('SMTP_HOST', '')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL', '')
    SMTP_FROM_NAME = os.environ.get('SMTP_FROM_NAME', 'AI 智能记账')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
    SMTP_USE_SSL = os.environ.get('SMTP_USE_SSL', 'false').lower() == 'true'


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True

    # In development, allow fallback defaults for secrets
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-not-for-production')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret-not-for-production')

    # Security (dev defaults)
    FERNET_KEY = os.environ.get('FERNET_KEY', '')  # Optional in dev


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False

    # Stricter CORS in production
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')

    # Production DB pool
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '20')),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '1800')),
        'pool_pre_ping': True,
        'pool_timeout': 10,
        'max_overflow': 5,
    }


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}  # SQLite doesn't support pool_size
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-jwt-secret-key'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
