from pathlib import Path

BASE_URL = "http://www.towerbells.org/data/"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "towerbells.db"
RAW_HTML_DIR = DATA_DIR / "raw_html"
REQUEST_DELAY_SECONDS = 0.3
