#!/usr/bin/env python3
"""
update_feeds.py
---------------
Fetches RSS feeds for The Sauber-Tribune and injects the headlines
directly into index.html as static HTML. Run by GitHub Actions daily.
"""

import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html as html_lib
import sys

# ── Feed configuration ──────────────────────────────────────────────────────
FEEDS = {
    "RSS_PLACEHOLDER_RSS_FRONT": {
        "url":   "https://growagoodlife.com/feed",
        "label": "Grow a Good Life",
        "count": 6,
    },
    "RSS_PLACEHOLDER_RSS_WOODWORKING": {
        "url":   "https://www.finewoodworking.com/feed",
        "label": "Fine Woodworking",
        "count": 6,
    },
    "RSS_PLACEHOLDER_RSS_GARDENING": {
        "url":   "https://harvesttotable.com/feed",
        "label": "Harvest to Table",
        "count": 6,
    },
    "RSS_PLACEHOLDER_RSS_TRACTORS": {
        "url":   "https://thecontraryfarmer.wordpress.com/feed",
        "label": "The Contrary Farmer",
        "count": 6,
    },
}

TEMPLATE_FILE = "index.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SauberTribune/1.0)"}


def fetch_feed(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def strip_tags(text: str) -> str:
    """Very simple tag stripper — no dependencies needed."""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


def format_date(date_str: str) -> str:
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%b %-d, %Y")
    except Exception:
        return ""


def parse_items(xml_bytes: bytes, count: int) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []

    for item in root.iter("item"):
        title_el   = item.find("title")
        link_el    = item.find("link")
        date_el    = item.find("pubDate")
        desc_el    = item.find("description")

        title = html_lib.unescape(title_el.text or "") if title_el is not None else "Untitled"
        link  = (link_el.text or "").strip() if link_el is not None else "#"
        date  = format_date(date_el.text or "") if date_el is not None else ""
        raw   = strip_tags(html_lib.unescape(desc_el.text or "")) if desc_el is not None else ""
        desc  = (raw[:110] + "…") if len(raw) > 110 else raw

        items.append({"title": title, "link": link, "date": date, "desc": desc})
        if len(items) >= count:
            break

    return items


def render_items(items: list[dict]) -> str:
    if not items:
        return '<div class="rss-error">No items found in feed.</div>'
    parts = []
    for item in items:
        desc_html = f'<span class="rss-desc">{html_lib.escape(item["desc"])}</span>' if item["desc"] else ""
        parts.append(
            f'<div class="rss-item">'
            f'<a href="{html_lib.escape(item["link"])}" target="_blank" rel="noopener">'
            f'{html_lib.escape(item["title"])}</a>'
            f'<span class="rss-meta">{item["date"]}</span>'
            f'{desc_html}'
            f'</div>'
        )
    return "\n".join(parts)


def main():
    # Read the template
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    errors = []

    for placeholder, cfg in FEEDS.items():
        print(f"Fetching: {cfg['url']} …", end=" ", flush=True)
        try:
            xml_bytes = fetch_feed(cfg["url"])
            items     = parse_items(xml_bytes, cfg["count"])
            rendered  = render_items(items)
            marker    = f"<!-- {placeholder} -->"
            if marker not in content:
                print(f"WARNING: placeholder '{marker}' not found in HTML — skipping.")
                continue
            content = content.replace(marker, rendered)
            print(f"OK ({len(items)} items)")
        except Exception as e:
            print(f"FAILED — {e}")
            errors.append(cfg["label"])
            # Leave a graceful error message in place
            marker = f"<!-- {placeholder} -->"
            fallback = f'<div class="rss-error">Feed temporarily unavailable.<br>Visit <a href="{cfg["url"]}">{cfg["label"]}</a> directly.</div>'
            content = content.replace(marker, fallback)

    # Inject last-updated timestamp
    now = datetime.now(timezone.utc).strftime("%B %-d, %Y at %-I:%M %p UTC")
    timestamp_html = (
        f'<div style="text-align:center;font-family:\'Courier Prime\',monospace;'
        f'font-size:0.65em;color:var(--ink-faint);padding:6px 0 2px;'
        f'border-top:1px solid var(--rule);">'
        f'Feeds last refreshed: {now}</div>'
    )
    content = content.replace("<!-- LAST_UPDATED_PLACEHOLDER -->", timestamp_html)

    # Write back
    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nDone. index.html updated.")
    if errors:
        print(f"Feeds with errors: {', '.join(errors)}")
        sys.exit(1)  # non-zero so GitHub Actions flags it


if __name__ == "__main__":
    main()
