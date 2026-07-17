import json
import re
from dataclasses import asdict, dataclass, field

from scraper.instrument_types import normalize_instrument_type
from scraper.text import clean_html_fragment

SECTION_RE = re.compile(
    r"<b>\*([^:<]+):</b>\s*(?:<pre>)?(.*?)(?=</pre>|<p>\s*<b>\*|<b>\*|\Z)",
    re.I | re.S,
)
H2_RE = re.compile(r"<H2[^>]*>(.*?)</H2>", re.I | re.S)
FIRST_PRE_RE = re.compile(r"<pre>\s*(.+?)\s*</pre>", re.I | re.S)


def _clean_html(text: str) -> str:
    return clean_html_fragment(text)


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return text.strip()


@dataclass
class ParsedSite:
    site_id: str
    page_filename: str
    page_url: str
    short_name: str = ""
    full_title: str = ""
    location_text: str = ""
    latitude: float | None = None
    longitude: float | None = None
    country_code: str = ""
    state_province: str = ""
    carillonist: str = ""
    past_carillonists: str = ""
    contact: str = ""
    schedule: str = ""
    remarks: str = ""
    technical_data: str = ""
    instrument_type: str = ""
    bell_count: int | None = None
    heaviest_pitch: str = ""
    keyboard_range: str = ""
    transposition: str = ""
    missing_bass_semitone: str = ""
    practice_console: str = ""
    retuned_year: int | None = None
    retuned_by: str = ""
    prior_history: str = ""
    auxiliary_mechanisms: str = ""
    tower_details: str = ""
    tech_info_year: int | None = None
    status_text: str = ""
    textual_data_updated: str = ""
    technical_data_updated: str = ""
    page_built_date: str = ""
    sections: dict[str, str] = field(default_factory=dict)

    def to_row(self) -> dict:
        row = asdict(self)
        row.pop("sections")
        return row


def _parse_short_name(header: str) -> tuple[str, str, str]:
    """Parse 'CHICAGO - UC : USA - IL' into display, country, state."""
    header = re.sub(r"\s+", " ", header).strip()
    if ":" not in header:
        return header, "", ""
    left, right = header.split(":", 1)
    right = right.strip()
    parts = [p.strip() for p in right.split("-")]
    country = parts[0] if parts else ""
    state = parts[1] if len(parts) > 1 else ""
    return left.strip(), country, state


LL_COORD_RE = re.compile(
    r"LL:\s*([NS])\s*([0-9.+-]+)\s*,\s*([EW])\s*([0-9.+-]+)",
    re.I,
)
FIGS_COORD_RE = re.compile(
    r"figs=['\"]?:?Exact:([A-Z0-9_&;]+):(-?\d+\.\d+)[&:;](-?\d+\.\d+)",
    re.I,
)


def parse_coordinates_from_text(text: str) -> tuple[float | None, float | None]:
    """Extract lat/lon from LL: lines or figs= JavaScript in a site page."""
    if not text:
        return None, None

    m = LL_COORD_RE.search(text)
    if m:
        ns, lat_s, ew, lon_s = m.groups()
        lat = float(lat_s) * (-1 if ns.upper() == "S" else 1)
        lon = float(lon_s) * (-1 if ew.upper() == "W" else 1)
        return lat, lon

    m = FIGS_COORD_RE.search(text)
    if m:
        lon = float(m.group(2))
        lat = float(m.group(3))
        return lat, lon

    return None, None


def _parse_coords(location_text: str) -> tuple[float | None, float | None]:
    return parse_coordinates_from_text(location_text)


def _parse_technical(technical: str, parsed: ParsedSite) -> None:
    parsed.technical_data = technical

    m = re.search(
        r"(Traditional carillon|Concert class carillon|Non-traditional carillon|"
        r"Hybrid carillon|Travelling carillon|Chime|Ring|Peal|Bell tower)"
        r"[^\d]*(\d+)\s+bells",
        technical,
        re.I,
    )
    if m:
        parsed.instrument_type = normalize_instrument_type(m.group(1))
        parsed.bell_count = int(m.group(2))

    m = re.search(r"Pitch of heaviest bell is (.+?)(?:\n|$)", technical, re.I)
    if m:
        parsed.heaviest_pitch = m.group(1).strip()

    m = re.search(r"Keyboard range:\s*(.+?)(?:\n|$)", technical, re.I)
    if m:
        parsed.keyboard_range = m.group(1).strip()

    m = re.search(r"Transposition is (.+?)(?:\n|$)", technical, re.I)
    if m:
        parsed.transposition = m.group(1).strip()

    m = re.search(r"(There is one missing bass semitone|No missing bass semitone)", technical, re.I)
    if m:
        parsed.missing_bass_semitone = m.group(1).strip()

    m = re.search(r"practice console is (\w+)", technical, re.I)
    if m:
        parsed.practice_console = m.group(1).strip()

    m = re.search(r"re-tuned in (\d{4})\s+by\s+(.+?)(?:\n|$)", technical, re.I)
    if m:
        parsed.retuned_year = int(m.group(1))
        parsed.retuned_by = m.group(1 + 1).strip()

    m = re.search(r"Prior history:(.*)", technical, re.I | re.S)
    if m:
        parsed.prior_history = _clean_html(m.group(1))

    m = re.search(r"Auxiliary mechanisms:\s*(.+?)(?:\n|$)", technical, re.I)
    if m:
        parsed.auxiliary_mechanisms = m.group(1).strip()

    m = re.search(r"Tower details (.+?)(?:\n|$)", technical, re.I)
    if m:
        parsed.tower_details = m.group(1).strip()

    m = re.search(r"Year of latest technical information source is (\d{4})", technical, re.I)
    if m:
        parsed.tech_info_year = int(m.group(1))


def _parse_status(status: str, parsed: ParsedSite) -> None:
    parsed.status_text = status
    m = re.search(r"built from the database on (\d{1,2}-[A-Za-z]{3}-\d{2})", status, re.I)
    if m:
        parsed.page_built_date = m.group(1)
    m = re.search(r"textual data last updated on (\d{4}/\d{2}/\d{2})", status, re.I)
    if m:
        parsed.textual_data_updated = m.group(1)
    m = re.search(r"technical data last updated on (\d{4}/\d{2}/\d{2})", status, re.I)
    if m:
        parsed.technical_data_updated = m.group(1)


def parse_site_page(site_id: str, html: str, page_filename: str, page_url: str) -> ParsedSite:
    parsed = ParsedSite(
        site_id=site_id.upper(),
        page_filename=page_filename.upper(),
        page_url=page_url,
    )

    h2 = H2_RE.search(html)
    if h2:
        parsed.short_name = re.sub(r"\s+", " ", _clean_html(h2.group(1))).strip()
        parsed.short_name, parsed.country_code, parsed.state_province = _parse_short_name(
            parsed.short_name
        )

    title = FIRST_PRE_RE.search(html)
    if title:
        parsed.full_title = re.sub(r"\s+", " ", _clean_html(title.group(1))).strip()

    sections: dict[str, str] = {}
    for match in SECTION_RE.finditer(html):
        key = match.group(1).strip()
        value = _clean_html(match.group(2))
        sections[key] = value

    parsed.sections = sections

    if "Location" in sections:
        parsed.location_text = sections["Location"]
        parsed.latitude, parsed.longitude = _parse_coords(parsed.location_text)
    if parsed.latitude is None:
        parsed.latitude, parsed.longitude = parse_coordinates_from_text(html)
    if "Carillonist" in sections:
        parsed.carillonist = sections["Carillonist"]
    if "Past carillonists" in sections:
        parsed.past_carillonists = sections["Past carillonists"]
    if "Contact" in sections:
        parsed.contact = sections["Contact"]
    if "Schedule" in sections:
        parsed.schedule = sections["Schedule"]
    if "Remarks" in sections:
        parsed.remarks = sections["Remarks"]
    if "Technical data" in sections:
        _parse_technical(sections["Technical data"], parsed)
    if "Status" in sections:
        _parse_status(sections["Status"], parsed)

    return parsed


def parsed_site_sections_json(parsed: ParsedSite) -> str:
    return json.dumps(parsed.sections, ensure_ascii=False)
