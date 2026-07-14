import re
from dataclasses import dataclass

from scraper.fetch import fetch

REGION_INDEX_RE = re.compile(r'href=["\']?([A-Za-z0-9_]+_car_ixs\.html)["\']?', re.I)
LIST_PAGE_RE = re.compile(
    r'href=["\']?(IX[A-Za-z0-9_]+\.html|Mstones[A-Za-z0-9_]+\.html)["\']?',
    re.I,
)
SITE_LINK_RE = re.compile(r'<A NAME=(\w+) HREF=(\w+\.HTM)>([^<]+)</A>\s*(.*)', re.I)
SITE_LINK_ALT_RE = re.compile(r'HREF=([A-Z0-9_]+\.HTM)', re.I)


@dataclass(frozen=True)
class ListPageRef:
    filename: str
    region: str | None
    list_type: str | None


@dataclass(frozen=True)
class ListEntry:
    site_id: str
    page_filename: str
    display_name: str
    line_suffix: str
    rank: int


def parse_list_page_meta(filename: str) -> ListPageRef:
    """Infer region and list type from filenames like IXNATRwt.html."""
    region = None
    list_type = None

    m = re.match(r"IX([A-Z]{2})TR([a-zA-Z]+)\.html", filename, re.I)
    if m:
        region, list_type = m.group(1).upper(), m.group(2).lower()
    elif filename.upper().startswith("MSTONES"):
        region = filename[7:9].upper() if len(filename) >= 9 else None
        list_type = "milestones"

    return ListPageRef(filename=filename, region=region, list_type=list_type)


def discover_region_indexes() -> list[str]:
    html = fetch("TR_type_ixs.html")
    return sorted(set(REGION_INDEX_RE.findall(html)), key=str.lower)


def discover_list_pages(region_indexes: list[str] | None = None) -> list[ListPageRef]:
    region_indexes = region_indexes or discover_region_indexes()
    pages: dict[str, ListPageRef] = {}

    for region_index in region_indexes:
        html = fetch(region_index)
        for filename in LIST_PAGE_RE.findall(html):
            pages.setdefault(filename, parse_list_page_meta(filename))

    return sorted(pages.values(), key=lambda p: p.filename.lower())


def parse_list_page(filename: str) -> tuple[ListPageRef, list[ListEntry]]:
    html = fetch(filename)
    meta = parse_list_page_meta(filename)
    entries: list[ListEntry] = []
    seen: set[str] = set()

    for rank, match in enumerate(SITE_LINK_RE.finditer(html), start=1):
        site_id, page_file, display_name, suffix = match.groups()
        site_id = site_id.upper()
        if site_id in seen:
            continue
        seen.add(site_id)
        entries.append(
            ListEntry(
                site_id=site_id,
                page_filename=page_file.upper(),
                display_name=re.sub(r"\s+", " ", display_name).strip(),
                line_suffix=re.sub(r"\s+", " ", suffix).strip(),
                rank=rank,
            )
        )

    if not entries:
        for rank, page_file in enumerate(dict.fromkeys(SITE_LINK_ALT_RE.findall(html)), start=1):
            site_id = page_file.rsplit(".", 1)[0].upper()
            entries.append(
                ListEntry(
                    site_id=site_id,
                    page_filename=page_file.upper(),
                    display_name="",
                    line_suffix="",
                    rank=rank,
                )
            )

    return meta, entries


def discover_site_ids(list_pages: list[ListPageRef] | None = None) -> dict[str, str]:
    """Return {site_id: page_filename} from all list pages."""
    list_pages = list_pages or discover_list_pages()
    site_pages: dict[str, str] = {}

    for page in list_pages:
        try:
            _, entries = parse_list_page(page.filename)
        except RuntimeError:
            continue
        for entry in entries:
            site_pages.setdefault(entry.site_id, entry.page_filename)

    return site_pages
