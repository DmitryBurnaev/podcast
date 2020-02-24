import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.dirname(BASE_DIR)
ENVIRONMENT = os.getenv("ENVIRONMENT", "develop")
TEST_MODE = ENVIRONMENT == "test" or "test" in sys.argv[0]

db_name = os.getenv("DATABASE_NAME", "podcast")
if TEST_MODE:
    db_name = os.getenv("DATABASE_NAME_TEST", "podcast_test")

DATABASE = {
    "host": os.getenv("DATABASE_HOST", "127.0.0.1"),
    "port": os.getenv("DATABASE_PORT", "3302"),
    "name": db_name,
    "username": os.getenv("DATABASE_USERNAME", "podcast"),
    "password": os.getenv("DATABASE_PASSWORD", "podcast"),
}
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = os.getenv("APP_PORT", "8000")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)

REDIS_CON = REDIS_HOST, REDIS_PORT

DEBUG = os.getenv("APP_DEBUG", "") in ("1", "True")
RESULT_AUDIO_PATH = os.path.join(PROJECT_ROOT_DIR, "media", "audio")
RESULT_RSS_PATH = os.path.join(PROJECT_ROOT_DIR, "media", "rss")
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates")
STATIC_PATH = os.path.join(PROJECT_ROOT_DIR, "static")

YANDEX_STORAGE_URL = os.getenv("YANDEX_STORAGE_URL")
YANDEX_AWS_ACCESS_KEY_ID = os.getenv("YANDEX_AWS_ACCESS_KEY_ID")
YANDEX_AWS_SECRET_ACCESS_KEY = os.getenv("YANDEX_AWS_SECRET_ACCESS_KEY")
YANDEX_BUCKET_NAME = os.getenv("YANDEX_BUCKET_NAME", "podcast")
YANDEX_BUCKET_AUDIO_PATH = os.getenv("YANDEX_BUCKET_AUDIO_PATH", "/audio/")
YANDEX_BUCKET_IMAGES_PATH = os.getenv("YANDEX_BUCKET_IMAGES_PATH", "/images/")

LOCALES_PATH = os.path.join(BASE_DIR, "i18n")
LOCALES_BY_DEFAULT = "en"
LOCALES = ["en", "ru"]

os.makedirs(RESULT_AUDIO_PATH, exist_ok=True)
os.makedirs(RESULT_RSS_PATH, exist_ok=True)
os.makedirs(STATIC_PATH, exist_ok=True)


MEDIA_URL = "/media/audio/"
STATIC_URL = "/static/"
SITE_URL = os.getenv("SITE_URL", "http://podcast.site.com/")

DOWNLOAD_EVENT_REDIS_TTL = 20 * 60  # 20 minutes
RQ_DEFAULT_TIMEOUT = 8 * 3600  # 8 hours


TESTING = "nosetests" in sys.argv[0]
SENTRY_DSN = os.getenv("SENTRY_DSN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%d.%m.%Y %H:%M:%S",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "loggers": {
        "modules": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "common": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "app": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "youtube_dl": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "rq.worker": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
