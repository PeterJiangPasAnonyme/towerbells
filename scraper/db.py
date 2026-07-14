import sqlite3
from pathlib import Path

from scraper.config import DB_PATH, RAW_HTML_DIR
from scraper.parse_site import ParsedSite, parsed_site_sections_json


SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    site_id TEXT PRIMARY KEY,
    page_filename TEXT NOT NULL,
    page_url TEXT NOT NULL,
    short_name TEXT,
    full_title TEXT,
    location_text TEXT,
    latitude REAL,
    longitude REAL,
    country_code TEXT,
    state_province TEXT,
    carillonist TEXT,
    past_carillonists TEXT,
    contact TEXT,
    schedule TEXT,
    remarks TEXT,
    technical_data TEXT,
    instrument_type TEXT,
    bell_count INTEGER,
    heaviest_pitch TEXT,
    keyboard_range TEXT,
    transposition TEXT,
    missing_bass_semitone TEXT,
    practice_console TEXT,
    retuned_year INTEGER,
    retuned_by TEXT,
    prior_history TEXT,
    auxiliary_mechanisms TEXT,
    tower_details TEXT,
    tech_info_year INTEGER,
    status_text TEXT,
    textual_data_updated TEXT,
    technical_data_updated TEXT,
    page_built_date TEXT,
    sections_json TEXT,
    scraped_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS list_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    region TEXT,
    list_type TEXT,
    entry_count INTEGER,
    scraped_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS list_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_page_id INTEGER NOT NULL REFERENCES list_pages(id),
    site_id TEXT NOT NULL,
    display_name TEXT,
    rank INTEGER,
    line_suffix TEXT,
    scraped_at TEXT NOT NULL,
    UNIQUE(list_page_id, site_id)
);

CREATE INDEX IF NOT EXISTS idx_list_entries_site ON list_entries(site_id);
CREATE INDEX IF NOT EXISTS idx_list_entries_page ON list_entries(list_page_id);
CREATE INDEX IF NOT EXISTS idx_sites_country ON sites(country_code);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_site(conn: sqlite3.Connection, parsed: ParsedSite, scraped_at: str) -> None:
    row = parsed.to_row()
    row["sections_json"] = parsed_site_sections_json(parsed)
    row["scraped_at"] = scraped_at
    columns = list(row.keys())
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{col}=excluded.{col}" for col in columns if col != "site_id")
    sql = (
        f"INSERT INTO sites ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(site_id) DO UPDATE SET {updates}"
    )
    conn.execute(sql, [row[col] for col in columns])


def upsert_list_page(
    conn: sqlite3.Connection,
    filename: str,
    region: str | None,
    list_type: str | None,
    entry_count: int,
    scraped_at: str,
) -> int:
    conn.execute(
        """
        INSERT INTO list_pages (filename, region, list_type, entry_count, scraped_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(filename) DO UPDATE SET
            region=excluded.region,
            list_type=excluded.list_type,
            entry_count=excluded.entry_count,
            scraped_at=excluded.scraped_at
        """,
        (filename, region, list_type, entry_count, scraped_at),
    )
    row = conn.execute("SELECT id FROM list_pages WHERE filename = ?", (filename,)).fetchone()
    return int(row["id"])


def replace_list_entries(
    conn: sqlite3.Connection,
    list_page_id: int,
    entries: list[tuple[str, str, int, str]],
    scraped_at: str,
) -> None:
    conn.execute("DELETE FROM list_entries WHERE list_page_id = ?", (list_page_id,))
    conn.executemany(
        """
        INSERT INTO list_entries (list_page_id, site_id, display_name, rank, line_suffix, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (list_page_id, site_id, display_name, rank, line_suffix, scraped_at)
            for site_id, display_name, rank, line_suffix in entries
        ],
    )
