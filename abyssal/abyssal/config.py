import os

API_KEY = os.getenv("API_KEY", "dev-key-12345")
I2PD_HTTP_PROXY = os.getenv("I2PD_HTTP_PROXY", "http://i2pd:4444")
DB_PATH = os.getenv("DB_PATH", "/data/crawler.db")
ARCHIVE_ROOT = os.getenv("ARCHIVE_ROOT", "/data/archive")
