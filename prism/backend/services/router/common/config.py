"""
Shared configuration for all Prism microservices.
All values come from environment variables (set in docker-compose.yml or .env).
"""

import os

# ── Authentication ──
API_KEY = os.getenv("API_KEY", "dev-key-12345")

# ── I2P Services (hostnames resolved via Docker network) ──
I2PD_HTTP_PROXY = os.getenv("I2PD_HTTP_PROXY", "http://i2pd:4444")
I2PD_API_URL = os.getenv("I2PD_API_URL", "https://i2pd:7650")
I2PD_PASSWORD = os.getenv("I2PD_PASSWORD", "itoopie")
WEBCONSOLE_URL = os.getenv("WEBCONSOLE_URL", "http://i2pd:7070")

# ── Data paths (shared volumes) ──
DB_PATH = os.getenv("DB_PATH", "/data/crawler.db")
ARCHIVE_ROOT = os.getenv("ARCHIVE_ROOT", "/data/archive")

# ── i2pd config (for addressbook service) ──
I2PD_CONF_PATH = os.getenv("I2PD_CONF_PATH", "/i2pd-data/i2pd.conf")
I2PD_DATA_PATH = os.getenv("I2PD_DATA_PATH", "/i2pd-data")
