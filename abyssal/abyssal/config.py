from pathlib import Path
import os


def _flag(name: str, default: bool = True) -> bool:
    """Read a boolean env var, accepting 0/false/no/off as false."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


API_KEY = os.getenv("API_KEY", "dev-key-12345")
I2PD_HTTP_PROXY = os.getenv("I2PD_HTTP_PROXY", "http://i2pd:4444")
DB_PATH = os.getenv("DB_PATH", "/data/crawler.db")
ARCHIVE_ROOT = Path(os.getenv("ARCHIVE_ROOT", "/data/archive"))

# Background crawlers that start on their own. They are convenient for a real
# deployment and hostile for a demo box: an ungated registry crawler walks the
# whole network and will happily pull in whatever it finds. Set these to false
# when you want the API to serve existing data and nothing else.
AUTOSEED_ENABLED = _flag("AUTOSEED_ENABLED", True)
SCHEDULER_ENABLED = _flag("SCHEDULER_ENABLED", True)
REGISTRY_CRAWLER_ENABLED = _flag("REGISTRY_CRAWLER_ENABLED", True)
