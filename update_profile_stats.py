import json
import requests
import pandas as pd
import time
import sys
from bs4 import BeautifulSoup
import requests.utils

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
SEARCH_BASE       = "https://tagpro.koalabeast.com"
REQUEST_DELAY     = 3  # seconds between HTTP requests
PROFILES_FILE     = "profiles.json"
LEADERBOARD_FILE  = "leaderboard.json"

# ─── UTILITIES ────────────────────────────────────────────────────────────────
def get_profile_url(name: str) -> str:
    """
    Given a TagPro player name, search Koalabeast’s playersearch?q= page.
    Returns the first profile URL whose displayed name matches case-insensitively `name`,
    or an empty string if none is found.
    """
    encoded = requests.utils.quote(name)
    search_url = f"{SEARCH_BASE}/playersearch?q={encoded}"
    try:
        resp = requests.get(search_url)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[get_profile_url] request failed for {name}: {e}")
        time.sleep(REQUEST_DELAY)
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    target = name.strip().lower()
    # find all profile links and match inner text case-insensitively
    for link in soup.find_all("a", href=lambda h: h and h.startswith("/profile/")):
        display_name = link.get_text(strip=True)
        if display_name.lower() == target:
            time.sleep(REQUEST_DELAY)
            return f"{SEARCH_BASE}{link['href']}"

    # fallback: no case-insensitive match
    time.sleep(REQUEST_DELAY)
    return ""


def ensure_profile_urls(players: list, profiles: dict) -> bool:
    """
    Ensure each player has a 'url' in profiles; if missing, look up via get_profile_url()
    and add to profiles dict. Returns True if profiles was modified.
    """
    updated = False
    for name in players:
        if profiles.get(name, {}).get('url'):
            continue

        print(f"Searching profile URL for '{name}'...")
        url = get_profile_url(name)
        if url:
            profiles[name] = profiles.get(name, {})
            profiles[name]['url'] = url
            updated = True
            print(f"  -> Found URL: {url}")
        else:
            print(f"  -> No match found for '{name}'.")
    return updated


def fetch_profile_stats(profile_url: str):
    """
    Fetch tier, skill, rank from Ranked CTF (NA) row of a profile.
    Returns (tier, skill, rank) or empty strings on failure.
    """
    try:
        resp = requests.get(profile_url)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[fetch_profile_stats] failed for {profile_url}: {e}")
        time.sleep(REQUEST_DELAY)
        return "", "", ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2 and "Ranked CTF (NA)" in cells[0].get_text(strip=True):
            container = cells[1].find("div", class_="profile-tier-display")
            if not container:
                break
            tier  = container.find("span", class_="tier-badge").get_text(strip=True) if container.find("span", class_="tier-badge") else ""
            skill = container.find("span", class_="skill-value").get_text(strip=True) if container.find("span", class_="skill-value") else ""
            rank  = container.find("span", class_="rank-value").get_text(strip=True)  if container.find("span", class_="rank-value")  else ""
            time.sleep(REQUEST_DELAY)
            return tier, skill, rank

    time.sleep(REQUEST_DELAY)
    return "", "", ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python update_profile_stats.py <AggregatedStatsOutput.csv>")
        sys.exit(1)
    agg_csv = sys.argv[1]

    try:
        df = pd.read_csv(agg_csv)
    except Exception as e:
        print(f"Error reading '{agg_csv}': {e}")
        sys.exit(1)
    players = df['Player'].dropna().unique().tolist()
    print(f"Loaded {len(players)} players from '{agg_csv}'.")

    try:
        with open(PROFILES_FILE, 'r') as f:
            profiles = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        profiles = {}
        print(f"Initialized new '{PROFILES_FILE}'.")

    if ensure_profile_urls(players, profiles):
        with open(PROFILES_FILE, 'w') as f:
            json.dump(profiles, f, indent=4)
        print(f"Saved new URLs to '{PROFILES_FILE}'.")

    try:
        with open(LEADERBOARD_FILE, 'r') as f:
            leaderboard = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        leaderboard = {}
        print(f"Initialized new '{LEADERBOARD_FILE}'.")

    for name in players:
        url = profiles.get(name, {}).get('url')
        if not url:
            print(f"Skipping '{name}': no URL available.")
            continue
        print(f"Fetching stats for '{name}'...")
        tier, skill, rank = fetch_profile_stats(url)
        leaderboard[name] = {
            'tier': tier,
            'skill': skill,
            'rank': rank
        }

    with open(LEADERBOARD_FILE, 'w') as f:
        json.dump(leaderboard, f, indent=4)
    print(f"All stats updated in '{LEADERBOARD_FILE}'.")

if __name__ == "__main__":
    main()
