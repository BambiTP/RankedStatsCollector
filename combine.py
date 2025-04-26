# File: combine.py
#!/usr/bin/env python3
import os
import csv
import shutil
import subprocess
from os.path import join

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
ROOT_DIR            = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_ROOT        = join(ROOT_DIR, "outputs")
MASTER_COMBINED_CSV = join(ROOT_DIR, "combinedStatsMaster.csv")
STATS_SCRIPT        = join(ROOT_DIR, "stats.py")
# ────────────────────────────────────────────────────────────────────────────────

def find_latest_run() -> str:
    runs = sorted(
        d for d in os.listdir(OUTPUTS_ROOT)
        if os.path.isdir(join(OUTPUTS_ROOT, d)) and d.startswith("run_")
    )
    if not runs:
        raise RuntimeError("No run_* folders in outputs/")
    return join(OUTPUTS_ROOT, runs[-1])

def append_to_master(new_csv: str, master_csv: str):
    with open(master_csv, "a", newline="") as out, \
         open(new_csv,    "r", newline="") as inp:
        reader = csv.reader(inp)
        writer = csv.writer(out)
        next(reader, None)  # skip header
        count = 0
        for row in reader:
            writer.writerow(row)
            count += 1
    print(f"[combine] appended {count} rows from {new_csv} → {master_csv}")

def main():
    run_dir     = find_latest_run()
    combined_csv= join(run_dir, "CombinedStatsOutput.csv")
    if not os.path.exists(combined_csv):
        raise RuntimeError(f"{combined_csv} not found")

    # 1) Append into master CSV
    append_to_master(combined_csv, MASTER_COMBINED_CSV)

    # 2) Copy updated master into this run folder
    dest = join(run_dir, os.path.basename(MASTER_COMBINED_CSV))
    shutil.copy2(MASTER_COMBINED_CSV, dest)
    print(f"[combine] copied master CSV → {dest}")

    # 3) Invoke stats.py on the copied master
    print(f"[combine] ▶ running stats.py on {dest}")
    res = subprocess.run(["python3", STATS_SCRIPT, dest], check=False)
    if res.returncode != 0:
        print(f"[combine] ✖ stats.py failed with code {res.returncode}")
        sys.exit(res.returncode)

if __name__ == "__main__":
    main()
