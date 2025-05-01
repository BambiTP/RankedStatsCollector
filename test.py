#!/usr/bin/env python3
import os
import sys
import json
import requests
import logging
import csv
from datetime import datetime
from os.path import join, dirname, abspath

# ─── CONSTANTS ───────────────────────────────────────────────────────────
ROOT_DIR          = dirname(abspath(__file__))
MATCH_IDS         = [3961011,
3962107,
3962221,
]
BULK_MATCHES_FILE = join(ROOT_DIR, "bulktest.json")
BULK_MAPS_FILE    = join(ROOT_DIR, "bulkmaps.json")
SINGLEMATCH_DIR   = join(ROOT_DIR, "singlematch")
os.makedirs(SINGLEMATCH_DIR, exist_ok=True)

# ─── DEPENDENCIES ──────────────────────────────────────────────
REQUIRED = [("requests", "requests"), ("tagpro_eu", "tagpro-eu")]

def check_deps():
    missing = []
    for mod, pkg in REQUIRED:
        try: __import__(mod)
        except ImportError: missing.append(pkg)
    if missing:
        print(f"Missing: {', '.join(missing)}; install: pip install {' '.join(missing)}")
        sys.exit(1)

# ─── HELPERS ──────────────────────────────────────────────

def to_seconds(time_str, fmt='%M:%S.%f'):
    t = datetime.strptime(time_str, fmt)
    return t.minute*60 + t.second + t.microsecond/1e6

FLAG_EVENTS = [
    'Grab Opponent flag','Return','Drop Opponent flag','Capture Opponent flag',
    'Grab Temporary flag','Drop Temporary flag','Capture Temporary flag'
]
JOIN_EVT = 'Join team'

def classify_events(match):
    timeline = match.create_timeline()
    team_map = {}
    for ts, ev, ply in timeline:
        if JOIN_EVT in ev: team_map[ply.name] = ev.split()[-1]

    raw=[]
    for ts, ev, ply in timeline:
        if ev in FLAG_EVENTS:
            name = ev.replace('Temporary flag','Opponent flag')
            sec  = to_seconds(str(ts))
            tm   = team_map.get(ply.name,'?')
            raw.append((sec,name,ply.name,tm))

    blue = match.team_blue.name; red = match.team_red.name
    sb= []; eb= []; sr= []; er= []
    for sec,name,ply,tm in raw:
        if name=='Grab Opponent flag':
            (sb if tm==blue else sr).append((sec,ply,tm))
        else:
            if name in ('Drop Opponent flag','Capture Opponent flag','Return'):
                (eb if tm==blue else er).append((sec,ply,tm,name))
    return raw, sb, eb, sr, er

def pretty_print(raw, sb, eb, sr, er):
    print("\nALL FLAG EVENTS:")
    print(f"{'Time':>6} | {'Event':<22} | {'Player':<15} | Team")
    print('-'*60)
    for sec,ev,pl,tm in raw:
        print(f"{sec:6.2f} | {ev:<22} | {pl:<15} | {tm}")

    def section(name,st,en):
        print(f"\n{name} START/END:")
        print(f"Role  | {'Time':>6} | {'Player':<15} | Team | Note")
        print('-'*60)
        for s in st: print(f"Start | {s[0]:6.2f} | {s[1]:<15} | {s[2]} |   ")
        for e in en: print(f"End   | {e[0]:6.2f} | {e[1]:<15} | {e[2]} | {e[3]}")

    section('BLUE', sb, eb)
    section('RED', sr, er)

def save_to_csv(mid, raw, sb, eb, sr, er):
    path = join(SINGLEMATCH_DIR, f"{mid}.csv")
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time', 'Event', 'Player', 'Team'])
        for row in raw:
            writer.writerow(row)
        writer.writerow([])
        writer.writerow(['BLUE START AND END EVENTS'])
        writer.writerow(['Role', 'Time', 'Player', 'Team', 'Note'])
        for s in sb: writer.writerow(['Start', f"{s[0]:.2f}", s[1], s[2], ''])
        for e in eb: writer.writerow(['End',   f"{e[0]:.2f}", e[1], e[2], e[3]])
        writer.writerow([])
        writer.writerow(['RED START AND END EVENTS'])
        writer.writerow(['Role', 'Time', 'Player', 'Team', 'Note'])
        for s in sr: writer.writerow(['Start', f"{s[0]:.2f}", s[1], s[2], ''])
        for e in er: writer.writerow(['End',   f"{e[0]:.2f}", e[1], e[2], e[3]])
    print(f"Saved CSV to {path}")

# ─── MAIN ──────────────────────────────────────────────

def download_matches(first, last):
    url = "https://tagpro.eu/data/"
    params = {"bulk":"matches","first":str(first),"last":str(last)}
    print(f"Downloading {first}→{last}")
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def main():
    check_deps()
    first_id = min(MATCH_IDS); last_id = max(MATCH_IDS)
    bulk = download_matches(first_id, last_id)
    with open(BULK_MATCHES_FILE,'w') as f: json.dump(bulk,f,indent=2)
    print(f"Saved {len(bulk)} matches to {BULK_MATCHES_FILE}")

    from eu_ctf import load_bulk_matches, load_bulk_maps, read_match_from_bulk
    bulk_matches = load_bulk_matches(BULK_MATCHES_FILE)
    bulk_maps    = load_bulk_maps(BULK_MAPS_FILE)

    for mid in MATCH_IDS:
        print(f"\n=== Match {mid} ===")
        try:
            match = read_match_from_bulk(mid, bulk_matches, bulk_maps)
            raw, sb, eb, sr, er = classify_events(match)
            pretty_print(raw, sb, eb, sr, er)
            save_to_csv(mid, raw, sb, eb, sr, er)
        except Exception as e:
            print(f"Failed {mid}: {e}")

if __name__=='__main__':
    main()
