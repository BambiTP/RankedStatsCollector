Collects All Ranked Stats From tagpro.eu (Collects Public Games that are 8 mins from tagpro.eu)

gh repo clone BambiTP/RankedStatsCollector

cd RankedStatsCollector

pip install requests pandas openpyxl tagpro-eu

python3 ctf_statistics.py

"Stats/Stats(x)/combined_stats.xlsx" has all the stats

"outputs/run_xxxx/combinedStatsMaster.csv" has the individual match stats csv

the "xxxx" in run_xxxx = the final match id in your run. You can check which one it is in latest_match.txt after the run is complete.


No need to change anything just do "python3 ctf_statistics.py" in the console while in the RankedStatsCollector directory and it will make a new folder with all the stats


https://tagpro.eu/?science

- latest_match.py
  - Gets latest match from "https://tagpro.eu/sitemaps.xml"
  - Downloads Bulk Matches from latest_match.txt to the new latest_match
  - Updates latest_match.txt
- ctf_eu.py & ctf_statistics.py
  - load_bulk_matches(bulk_matches_file)
    What it does: Reads your saved JSON of raw match data (bulkmatches.json) and returns it as a Python dictionary keyed by match ID.

   - load_bulk_maps(bulk_maps_file)
    What it does: Reads your saved JSON of map data (bulkmaps.json) and returns it as a Python dictionary keyed by map ID.

   - extract_match_data(match_id, bulk_matches, bulk_maps, RUN_DIR)
    What it does: For one match ID, pulls out every player’s basic and advanced stats (using the tagpro-eu library), writes them to RUN_DIR/{match_id}.csv, and logs any      failures.
  
     - compile_data(RUN_DIR, AGG_CSV)

       What it does: Scans all the per-match CSVs in RUN_DIR, stitches them together into a single table (normalizing player names and recomputing cumulative stats),   
       and writes out AggregatedStatsOutput.csv (plus a TXT copy).

     - combine_stats_csv(RUN_DIR, AGG_CSV, COMB_CSV, bulk_matches, bulk_maps)

      What it does: Reads every per-match CSV (except the aggregated file), looks up each match’s map name, merges them into one big DataFrame, and writes             
      CombinedStatsOutput.csv (plus a formatted TXT).

   - stats.py

    - reads the CombinedStatsOutput.csv and does some math and stuff to it to turn them into the stats.

(missing a a lot of steps but it's the basic gist(lol) of things.)  (somewhere along the way it combines the CombinedStatsMaster.csv with the newly generated CombinedStatsOutput.csv)

https://chatgpt.com/share/683040a2-dd68-800a-bb8f-7e3a8f6ea3a8



