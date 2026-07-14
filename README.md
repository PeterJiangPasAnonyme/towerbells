# towerbells

A modern rebuild of [towerbells.org](http://www.towerbells.org/) — starting with a scraper that mirrors the site's carillon data into a queryable SQLite database.

**Current dataset (last full scrape):** 2,099 sites · 82 list pages · 6,535 list entries

## Quick start

```bash
# Full scrape (list indexes + all site pages; ~50 min at 0.3s/request)
python3 scripts/scrape.py

# Re-parse from cached HTML after parser fixes (no network)
python3 scripts/reparse_cached.py
```

## Data organization

```
data/
├── towerbells.db      # SQLite database (structured records)
├── scrape_progress.json  # Live scrape progress (written during runs)
├── scrape.log         # Optional stdout capture from scrape runs
└── raw_html/          # Cached site page HTML (one file per site)
    └── ilchicuc.htm   # Lowercase filename from towerbells.org
```

### Scrape phases

1. **lists** — Fetches regional index pages and list pages (`IX*.html`, `Mstones*.html`), storing each site's rank and display name on regional lists.
2. **sites** — Fetches every individual site page (`.HTM`), parses structured fields, and upserts into `sites`.

Run both phases (default):

```bash
python3 scripts/scrape.py
```

Options:

```bash
python3 scripts/scrape.py --phase lists   # list pages only
python3 scripts/scrape.py --phase sites   # site pages only
python3 scripts/scrape.py --limit 10        # cap pages per phase (testing)
python3 scripts/scrape.py --no-cache        # skip saving raw HTML
```

### Live progress tracking

During a scrape, `scripts/scrape.py` prints progress after every page (with `flush=True`) and writes `data/scrape_progress.json`:

```json
{
  "phase": "sites",
  "current": 142,
  "total": 890,
  "site_id": "ILCHICUC",
  "updated_at": "2026-07-14T12:34:56+00:00"
}
```

- `phase` — `"lists"` or `"sites"`
- `current` / `total` — pages completed vs. total in the current phase
- `site_id` — current list filename (lists phase) or site ID (sites phase)
- `updated_at` — UTC ISO timestamp of last update

## Database schema

### `sites` (one row per carillon site)

| Column | Description |
|--------|-------------|
| `site_id` | Primary key, e.g. `ILCHICUC` |
| `page_filename` | Source `.HTM` filename |
| `page_url` | Full URL on towerbells.org |
| `short_name` | H2 header name (e.g. `CHICAGO - UC`) |
| `full_title` | First `<pre>` block title |
| `location_text` | Raw Location section text |
| `latitude`, `longitude` | Parsed from `LL: N …, W …` in location |
| `country_code`, `state_province` | Parsed from H2 suffix (e.g. `USA`, `IL`) |
| `carillonist` | Current carillonist |
| `past_carillonists` | Past carillonists |
| `contact` | Contact information |
| `schedule` | Performance / visiting schedule |
| `remarks` | Free-form remarks |
| `technical_data` | Full Technical data section text |
| `instrument_type` | e.g. `Traditional carillon` |
| `bell_count` | Number of bells |
| `heaviest_pitch` | Pitch of heaviest bell |
| `keyboard_range` | Keyboard range |
| `transposition` | Transposition |
| `missing_bass_semitone` | Missing bass semitone note |
| `practice_console` | Whether a practice console exists |
| `retuned_year`, `retuned_by` | Re-tuning details |
| `prior_history` | Prior history text |
| `auxiliary_mechanisms` | Auxiliary mechanisms |
| `tower_details` | Tower details |
| `tech_info_year` | Year of latest technical info source |
| `status_text` | Full Status section text |
| `textual_data_updated` | Last textual data update date |
| `technical_data_updated` | Last technical data update date |
| `page_built_date` | Page build date from status |
| `sections_json` | JSON map of all `*Section:` blocks (raw parsed text) |
| `scraped_at` | UTC ISO timestamp of last scrape |

### `list_pages` (one row per regional list page)

| Column | Description |
|--------|-------------|
| `filename` | List page filename (unique), e.g. `IXNATRwt.html` |
| `region` | Two-letter region code from filename |
| `list_type` | List subtype (e.g. `wt`, `milestones`) |
| `entry_count` | Number of sites on the list |
| `scraped_at` | UTC ISO timestamp |

### `list_entries` (site appearances on list pages)

| Column | Description |
|--------|-------------|
| `list_page_id` | FK to `list_pages.id` |
| `site_id` | Site identifier |
| `display_name` | Name as shown on the list |
| `rank` | Position on the list |
| `line_suffix` | Trailing text after the link on the list line |
| `scraped_at` | UTC ISO timestamp |

## Per-site stored data

For each site page scrape we store:

1. **Raw HTML cache** — `data/raw_html/<filename>.htm` (lowercase), unless `--no-cache` is passed.
2. **Structured SQLite row** — All fields in the `sites` table above, populated by parsing these page sections:
   - Location (coords, address text)
   - Carillonist / Past carillonists
   - Contact / Schedule / Remarks
   - Technical data (instrument type, bell count, keyboard, transposition, tuning history, tower details, etc.)
   - Status (page build and update dates)
3. **`sections_json`** — Complete backup of every `*Section:` block as key→text, including any sections not mapped to dedicated columns.

List-phase scrapes additionally store index metadata in `list_pages` and per-line entries in `list_entries`.

## Example queries

```bash
sqlite3 data/towerbells.db
```

```sql
-- Rockefeller Chapel Carillon
SELECT full_title, bell_count, heaviest_pitch, keyboard_range, transposition,
       latitude, longitude
FROM sites WHERE site_id = 'ILCHICUC';

-- All list appearances for one site (rankings, sort keys)
SELECT lp.filename, lp.list_type, le.rank, le.line_suffix
FROM list_entries le
JOIN list_pages lp ON lp.id = le.list_page_id
WHERE le.site_id = 'ILCHICUC'
ORDER BY lp.list_type;

-- Heaviest North American traditional carillons
SELECT short_name, bell_count, heaviest_pitch
FROM sites
WHERE country_code = 'USA' AND instrument_type = 'Traditional carillon'
ORDER BY bell_count DESC LIMIT 20;
```

## Scope note

The scraper follows towerbells.org's index graph starting from [TR_type_ixs.html](http://www.towerbells.org/data/TR_type_ixs.html). That yields **~2,000+ site pages** (mostly traditional carillons, plus chimes and hybrids linked from regional lists), not only the ~797 core traditional carillon IDs. Filter on `instrument_type` when you need traditional carillons only.

## Project layout

```
scraper/
├── config.py      # Paths, base URL, request delay
├── fetch.py       # HTTP fetch with rate limiting
├── discover.py    # Find list pages and site IDs from indexes
├── parse_site.py  # Parse site HTML into structured fields
└── db.py          # SQLite schema and upsert helpers

scripts/
├── scrape.py           # CLI entry point (network scrape)
├── enrich_metadata.py  # Build site_index table for search/filters
├── run_web.py          # Start the web explorer
└── reparse_cached.py   # Re-parse raw_html/ into DB (offline)

server/                 # FastAPI backend (reads towerbells.db)
web/static/             # Map + search UI (HTML/JS/CSS, no Node build)
```

## Web explorer

Interactive map + search UI with filters (location, year, bellfounder, bourdon pitch, transposition, range class, denomination, institution type).

```bash
# One-time: build search index (after scraping)
python3 scripts/enrich_metadata.py

# Start server (creates .venv and installs deps on first run)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/run_web.py
```

Open **http://127.0.0.1:8000** — map on the right, search and filters on the left. Click a pin or list item to open the carillon detail page.
