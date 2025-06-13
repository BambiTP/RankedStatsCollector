#!/usr/bin/env python3
import os
import sys
import json
import requests
import xml.etree.ElementTree as ET
from io import BytesIO

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
ROOT_DIR          = os.path.dirname(os.path.abspath(__file__))
BULK_MATCHES_FILE = os.path.join(ROOT_DIR, "bulkmatches.json")
LATEST_MATCH_FILE = os.path.join(ROOT_DIR, "latest_match.txt")
# ────────────────────────────────────────────────────────────────────────────────

def get_last_loc_from_xml(url: str) -> str:
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    last = None
    for event, elem in ET.iterparse(BytesIO(resp.content), events=("end",)):
        if elem.tag.endswith("loc"):
            last = elem.text
        elem.clear()
    if last is None:
        raise RuntimeError(f"No <loc> tags found at {url}")
    return last

def get_latest_sitemap_url() -> str:
    idx = "https://tagpro.eu/sitemaps.xml"
    loc = get_last_loc_from_xml(idx)
    print(f"[latest_match] sitemap index → latest sitemap URL: {loc}")
    return loc

def get_latest_match_id(sitemap_url: str) -> int:
    loc = get_last_loc_from_xml(sitemap_url)
    print(f"[latest_match] latest sitemap URL → last match URL: {loc}")
    if "?match=" not in loc:
        raise RuntimeError("Could not find '?match=' in sitemap URL")
    mid = int(loc.split("?match=")[-1])
    print(f"[latest_match] extracted latest match ID: {mid}")
    return mid

def read_previous_match_id() -> int:
    if not os.path.exists(LATEST_MATCH_FILE):
        print(f"[latest_match] {LATEST_MATCH_FILE} not found; nothing to do.")
        sys.exit(0)
    with open(LATEST_MATCH_FILE) as f:
        prev = int(f.read().strip())
    print(f"[latest_match] previous match ID: {prev}")
    return prev

def update_latest_match_file(new_id: int) -> None:
    nxt = new_id + 1
    with open(LATEST_MATCH_FILE, "w") as f:
        f.write(str(nxt))
    print(f"[latest_match] {LATEST_MATCH_FILE} ← {nxt}")

def download_matches(first: int, last: int) -> dict:
    url = "https://tagpro.eu/data/"
    payload = {"bulk": "matches", "first": str(first), "last": str(last)}
    print(f"[latest_match] downloading matches {first}→{last}")
    resp = requests.get(url, params=payload)
    resp.raise_for_status()
    return resp.json()

def overwrite_bulk_matches(bulk_file: str, new_data: dict) -> None:
    """
    Completely replace bulk_file with new_data,
    discarding any prior contents.
    """
    with open(bulk_file, "w") as f:
        json.dump(new_data, f, indent=2)
    print(f"[latest_match] overwrote {bulk_file} with {len(new_data)} matches")

def main():
    sitemap_url = get_latest_sitemap_url()
    latest_id   = get_latest_match_id(sitemap_url)
    prev_id     = read_previous_match_id()
    if latest_id < prev_id:
        print("[latest_match] no new matches to fetch. Exiting.")
        sys.exit(0)

    new_data = download_matches(prev_id, latest_id)
    overwrite_bulk_matches(BULK_MATCHES_FILE, new_data)
    update_latest_match_file(latest_id)

if __name__ == "__main__":
    main()
