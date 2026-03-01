#!/usr/bin/env python3
"""
update_feeds.py
---------------
Fetches RSS feeds and current weather for The Sauber-Tribune,
then injects them directly into index.html as static HTML.
Run daily by GitHub Actions.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
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
    "RSS_PLACEHOLDER_RSS_DIY": {
        "url":   "https://www.familyhandyman.com/feed/",
        "label": "Family Handyman",
        "count": 6,
    },
}

# Tiffin, OH coordinates for Open-Meteo (free, no API key)
WEATHER_LAT  = 41.1148
WEATHER_LON  = -83.1779
WEATHER_CITY = "Tiffin, Ohio"

TEMPLATE_FILE = "index.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SauberTribune/1.0)"}


def fetch_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def strip_tags(text: str) -> str:
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
    items = []
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el  = item.find("link")
        date_el  = item.find("pubDate")
        desc_el  = item.find("description")
        title = html_lib.unescape(title_el.text or "") if title_el is not None else "Untitled"
        link  = (link_el.text or "").strip()           if link_el  is not None else "#"
        date  = format_date(date_el.text or "")        if date_el  is not None else ""
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


def fetch_weather() -> str:
    """Fetch current weather from Open-Meteo (free, no API key required)."""
    params = urllib.parse.urlencode({
        "latitude":         WEATHER_LAT,
        "longitude":        WEATHER_LON,
        "current":          "temperature_2m,weathercode,windspeed_10m,relativehumidity_2m",
        "temperature_unit": "fahrenheit",
        "windspeed_unit":   "mph",
        "timezone":         "America/New_York",
    })
    url  = f"https://api.open-meteo.com/v1/forecast?{params}"
    data = json.loads(fetch_url(url))
    c    = data["current"]

    temp     = round(c["temperature_2m"])
    wind     = round(c["windspeed_10m"])
    humidity = round(c["relativehumidity_2m"])
    code     = c["weathercode"]
    updated  = datetime.now(timezone.utc).strftime("%-I:%M %p UTC, %b %-d")

    code_map = {
        0:  ("Clear skies",          "☀️"),
        1:  ("Mainly clear",         "🌤️"),
        2:  ("Partly cloudy",        "⛅"),
        3:  ("Overcast",             "☁️"),
        45: ("Foggy",                "🌫️"),
        48: ("Icy fog",              "🌫️"),
        51: ("Light drizzle",        "🌦️"),
        53: ("Drizzle",              "🌦️"),
        55: ("Heavy drizzle",        "🌧️"),
        61: ("Slight rain",          "🌧️"),
        63: ("Rain",                 "🌧️"),
        65: ("Heavy rain",           "🌧️"),
        71: ("Slight snow",          "🌨️"),
        73: ("Snow",                 "❄️"),
        75: ("Heavy snow",           "❄️"),
        77: ("Snow grains",          "❄️"),
        80: ("Rain showers",         "🌦️"),
        81: ("Rain showers",         "🌦️"),
        82: ("Violent showers",      "⛈️"),
        85: ("Snow showers",         "🌨️"),
        86: ("Heavy snow showers",   "🌨️"),
        95: ("Thunderstorm",         "⛈️"),
        96: ("Thunderstorm w/ hail", "⛈️"),
        99: ("Thunderstorm w/ hail", "⛈️"),
    }
    desc, icon = code_map.get(code, ("Conditions unknown", "🌡️"))

    return (
        f'<div class="weather-box">'
        f'<span class="w-kicker">Current Conditions</span>'
        f'<div class="w-city">{WEATHER_CITY}</div>'
        f'<div class="w-temp">{icon} {temp}°F</div>'
        f'<div class="w-desc">{desc}</div>'
        f'<div class="w-details">Wind: {wind} mph &nbsp;·&nbsp; Humidity: {humidity}%</div>'
        f'<div class="w-updated">Updated {updated}</div>'
        f'</div>'
    )


def main():
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    errors = []

    # ── Weather ──────────────────────────────────────────────────────────────
    print("Fetching weather for Tiffin, OH …", end=" ", flush=True)
    try:
        weather_html = fetch_weather()
        content = content.replace("<!-- WEATHER_PLACEHOLDER -->", weather_html)
        print("OK")
    except Exception as e:
        print(f"FAILED — {e}")
        errors.append("Weather")
        content = content.replace(
            "<!-- WEATHER_PLACEHOLDER -->",
            '<div class="rss-error">Weather temporarily unavailable.</div>'
        )

    # ── RSS Feeds ─────────────────────────────────────────────────────────────
    for placeholder, cfg in FEEDS.items():
        print(f"Fetching: {cfg['url']} …", end=" ", flush=True)
        try:
            xml_bytes = fetch_url(cfg["url"])
            items     = parse_items(xml_bytes, cfg["count"])
            rendered  = render_items(items)
            marker    = f"<!-- {placeholder} -->"
            if marker not in content:
                print("WARNING: placeholder not found — skipping.")
                continue
            content = content.replace(marker, rendered)
            print(f"OK ({len(items)} items)")
        except Exception as e:
            print(f"FAILED — {e}")
            errors.append(cfg["label"])
            marker   = f"<!-- {placeholder} -->"
            fallback = (
                f'<div class="rss-error">Feed temporarily unavailable.<br>'
                f'Visit <a href="{cfg["url"]}">{cfg["label"]}</a> directly.</div>'
            )
            content = content.replace(marker, fallback)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc).strftime("%B %-d, %Y at %-I:%M %p UTC")
    timestamp_html = (
        f'<div style="text-align:center;font-family:\'Courier Prime\',monospace;'
        f'font-size:0.65em;color:var(--ink-faint);padding:6px 0 2px;'
        f'border-top:1px solid var(--rule);">'
        f'Feeds last refreshed: {now}</div>'
    )
    content = content.replace("<!-- LAST_UPDATED_PLACEHOLDER -->", timestamp_html)

    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nDone. index.html updated.")
    if errors:
        print(f"Items with errors: {', '.join(errors)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
