#!/usr/bin/env python3
"""Generate a continent → country → region checklist of all carillon detail pages."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.display_titles import display_title_for_site
from server.db import connect
from server.geo_labels import format_country, format_region

CONTINENT_ORDER = [
    "Africa & Mideast",
    "Asia-Pacific",
    "Europe",
    "North America",
    "South America",
    "Other",
]

DEFAULT_BASE_URL = "http://127.0.0.1:8000/carillon"


def load_sites() -> list[dict]:
    conn = connect()
    rows = conn.execute(
        """
        SELECT s.site_id, s.country_code, s.state_province, s.full_title,
               s.display_title_override, s.short_name,
               i.continent
        FROM sites s
        LEFT JOIN site_index i ON i.site_id = s.site_id
        ORDER BY s.site_id
        """
    ).fetchall()
    conn.close()

    sites: list[dict] = []
    for row in rows:
        site = dict(row)
        continent = site.get("continent") or "Other"
        country_code = site.get("country_code") or ""
        region_code = site.get("state_province") or ""
        sites.append(
            {
                "site_id": site["site_id"],
                "title": display_title_for_site(site),
                "continent": continent,
                "country_code": country_code,
                "country": format_country(country_code) or country_code or "Unknown",
                "region_code": region_code,
                "region": format_region(country_code, region_code) or "",
            }
        )
    return sites


def build_tree(sites: list[dict]) -> dict:
    tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for site in sites:
        continent = site["continent"] or "Other"
        country = site["country"]
        region = site["region"] or ""
        tree[continent][country][region].append(site)
    return tree


def sort_key_continent(name: str) -> tuple:
    try:
        return (0, CONTINENT_ORDER.index(name))
    except ValueError:
        return (1, name.lower())


def render_markdown(tree: dict, *, base_url: str) -> str:
    lines: list[str] = [
        "# Carillon site checklist",
        "",
        "All detail pages sorted by continent, country, and region.",
        "Use the checkboxes as you review each location display.",
        "",
        f"Base URL: `{base_url}/{{site_id}}`",
        "",
    ]

    total = 0
    for continent in sorted(tree.keys(), key=sort_key_continent):
        continent_sites = [
            site for country in tree[continent].values() for region in country.values() for site in region
        ]
        total += len(continent_sites)
        lines.append(f"## {continent} ({len(continent_sites)})")
        lines.append("")

        for country in sorted(tree[continent].keys(), key=str.lower):
            country_regions = tree[continent][country]
            country_count = sum(len(sites) for sites in country_regions.values())
            lines.append(f"### {country} ({country_count})")
            lines.append("")

            regions = sorted(country_regions.keys(), key=lambda r: (r == "", r.lower()))
            for region in regions:
                sites = sorted(country_regions[region], key=lambda s: s["site_id"])
                if region:
                    lines.append(f"#### {region} ({len(sites)})")
                    lines.append("")
                for site in sites:
                    url = f"{base_url}/{site['site_id']}"
                    lines.append(
                        f"- [ ] [{site['site_id']} — {site['title']}]({url})"
                    )
                lines.append("")

    lines.insert(5, f"**Total sites:** {total}")
    lines.insert(6, "")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "data" / "site_checklist.md",
        help="Output markdown path (default: data/site_checklist.md)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Detail page base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing a file",
    )
    args = parser.parse_args()

    sites = load_sites()
    tree = build_tree(sites)
    markdown = render_markdown(tree, base_url=args.base_url.rstrip("/"))

    if args.stdout:
        print(markdown)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"Wrote {len(sites)} sites to {args.output}")


if __name__ == "__main__":
    main()
