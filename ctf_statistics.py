import os
import sys
import subprocess
from glob import glob
from os.path import join, dirname, abspath, exists

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
ROOT_DIR               = dirname(abspath(__file__))
OUTPUTS_ROOT           = join(ROOT_DIR, "outputs")
MAIN_OUTPUT_DIR        = join(OUTPUTS_ROOT, "main")

BULK_MATCHES_FILE      = join(ROOT_DIR, "bulkmatches.json")
BULK_MAPS_FILE         = join(ROOT_DIR, "bulkmaps.json")
MASTER_COMBINED_CSV    = join(ROOT_DIR, "combinedStatsMaster.csv")

LATEST_MATCH_SCRIPT    = join(ROOT_DIR, "latest_match.py")
COMBINE_SCRIPT         = join(ROOT_DIR, "combine.py")
STATS_SCRIPT           = join(ROOT_DIR, "stats.py")
UPDATE_PROFILE_SCRIPT  = join(ROOT_DIR, "update_profile_stats.py")

# ─── REQUIRED DEPENDENCIES ─────────────────────────────────────────────────────
REQUIRED_PACKAGES = [
    ("requests", "requests"),
    ("pandas", "pandas"),
    ("openpyxl", "openpyxl"),
    ("tagpro_eu", "tagpro-eu"),
    ("bs4", "beautifulsoup4")
]

# ────────────────────────────────────────────────────────────────────────────────
def check_dependencies():
    missing = []
    for module, pkg_name in REQUIRED_PACKAGES:
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg_name)
    if missing:
        print(f"[ctf_statistics] ✖ Missing dependencies: {', '.join(missing)}")
        print("Install them with: pip install " + " ".join(missing))
        sys.exit(1)


def run_subscript(path: str, *args):
    cmd = [sys.executable, path] + list(args)
    print(f"[ctf_statistics] ▶ running {' '.join(cmd)}")
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        print(f"[ctf_statistics] ✖ {path} failed with code {res.returncode}")
        sys.exit(res.returncode)


def main():
    # 0) Ensure all required packages are installed
    check_dependencies()

    # 1) Fetch & merge new matches
    run_subscript(LATEST_MATCH_SCRIPT)

    # 2) Build a fresh run folder
    with open(join(ROOT_DIR, "latest_match.txt")) as f:
        next_first = int(f.read().strip())
    run_id = f"run_{next_first}"
    RUN_DIR = join(OUTPUTS_ROOT, run_id)
    os.makedirs(RUN_DIR, exist_ok=True)

    # 3) Run the eu_ctf pipeline
    from eu_ctf import (
        load_bulk_matches, load_bulk_maps,
        extract_match_data, compile_data,
        combine_stats_csv, failed_match_ids
    )

    print("[ctf_statistics] loading bulk JSON data...")
    bulk_matches = load_bulk_matches(BULK_MATCHES_FILE)
    bulk_maps    = load_bulk_maps(BULK_MAPS_FILE)

    print(f"[ctf_statistics] processing {len(bulk_matches)} matches...")
    for mid in bulk_matches:
        print(f"[ctf_statistics] ▶ processing match {mid}")
        try:
            extract_match_data(mid, bulk_matches, bulk_maps, RUN_DIR)
            print(f"[ctf_statistics] ✓ match {mid} processed successfully")
        except Exception as e:
            print(f"[ctf_statistics] ✖ match {mid} failed: {e}")
            if mid not in failed_match_ids:
                failed_match_ids.append(mid)

    # 4) Compile aggregated + combined CSVs
    AGG_CSV  = join(RUN_DIR, "AggregatedStatsOutput.csv")
    COMB_CSV = join(RUN_DIR, "CombinedStatsOutput.csv")

    print("[ctf_statistics] compiling aggregated CSV…")
    compile_data(RUN_DIR, AGG_CSV)
    print(f"[ctf_statistics] ✓ aggregated CSV compiled: {AGG_CSV}")

    print("[ctf_statistics] compiling combined CSV…")
    combine_stats_csv(RUN_DIR, AGG_CSV, COMB_CSV, bulk_matches, bulk_maps)
    print(f"[ctf_statistics] ✓ combined CSV compiled: {COMB_CSV}")

    # 5) Update profiles using aggregated CSV
    print(f"[ctf_statistics] updating profiles from {AGG_CSV}…")
    run_subscript(UPDATE_PROFILE_SCRIPT, AGG_CSV)
    print("[ctf_statistics] ✓ profiles update complete")

    # 6) Write failures list if any
    if failed_match_ids:
        txt = join(RUN_DIR, "failed_matches.txt")
        print("[ctf_statistics] writing failure list…")
        with open(txt, "w") as f:
            for m in failed_match_ids:
                f.write(f"{m}\n")
        print(f"[ctf_statistics] ✓ failure list written: {txt}")


    # 8) Kick off combine.py
    run_subscript(COMBINE_SCRIPT)

    print("[ctf_statistics] all done.")


if __name__ == "__main__":
    main()
