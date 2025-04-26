Collects All Ranked Stats From tagpro.eu (Collects Public Games that are 8 mins from tagpro.eu)


pip install requests pandas openpyxl tagpro-eu

python3 ctf_statistics.py

"Stats/Stats(x)/combined_stats.xlsx" has all the stats

"outputs/run_xxxxxx/combinedStatsMaster.csv" has the combined individual matches csv 

xxxxxx in run_xxxxx = the final match id in your run. You can check which one it is in latest_match.txt after the run is complete.


No need to change anything just do "python3 ctf_statistics.py" in the console and it will make a new folder with all the stats
