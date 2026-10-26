"""
Seed URLs crawled automatically on a fresh database.
Edit this list to add/remove sites that should be crawled first on startup.
"""

SEED_URLS = [
    "http://notbob.i2p",
    "http://stats.i2p",
    "http://reg.i2p",
    "http://i2pd.i2p",
]

# Per-seed crawl settings
SEED_MAX_PAGES = 200     # 0 = unlimited, which is how a seed crawl eats the network
SEED_MAX_DEPTH = 3
SEED_CONCURRENCY = 3
SEED_DELAY = 2.0
