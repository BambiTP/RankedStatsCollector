#!/usr/bin/env python3
import sys
import pandas as pd
import os
import re
from openpyxl.utils import get_column_letter

# ─── CONFIG ────────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 1:
    INPUT_CSV = sys.argv[1]
else:
    INPUT_CSV = os.path.join(ROOT_DIR, "outputs", "main", "combinedStatsMaster.csv")
# ────────────────────────────────────────────────────────────────────────────────

raw_stats = [
    'Captures','Grabs','Hold','Drops','Pops','Returns','Tags','Prevent',
    'Pups','Pups Available','Block','Button','Support','Hold Against',
    'Long Holds','Flaccids','Handoffs','Good Handoffs','Captures off Handoffs',
    'Quick Returns','Key Returns','Returns in Base','NDPops','NRTags','KF','CD'
]

derived_stats = {
    'CD/Min': ('CD','Minutes'), 'Caps/Min':('Captures','Minutes'),
    'Grabs/Min':('Grabs','Minutes'), 'Hold/Min':('Hold','Minutes'),
    'Drops/Min':('Drops','Minutes'),'Pops/Min':('Pops','Minutes'),
    'Returns/Min':('Returns','Minutes'),'Tags/Min':('Tags','Minutes'),
    'Prevent/Min':('Prevent','Minutes'),'Pups/Min':('Pups','Pups Available'),
    'Win %':('Wins','Games'),'Pup %':('Pups','Pups Available'),
    'Score %':('Captures','Grabs'),'Flaccid %':('Flaccids','Grabs'),
    'Chain %':('Good Handoffs','Grabs'),'QR %':('Quick Returns','Returns'),
    'RIB %':('Returns in Base','Returns'),'K/D':('Tags','Pops'),
    'Hold/Grab':('Hold','Grabs'),'Prevent/Return':('Prevent','Returns'),
    'Prevent/Hold Against':('Prevent','Hold Against')
}

def new_entry(name):
    return {
        'Name': name, 'Games':0,'RedGames':0,'BlueGames':0,
        'Wins':0,'Losses':0,'RedWins':0,'BlueWins':0,
        'Minutes':0,'Totals':{stat:0 for stat in raw_stats}
    }

def update_entry(entry,row,caps_for,caps_against,result,winner_color):
    tc = row.get('Team','').strip().lower()
    entry['Games'] += 1
    if tc=='red':   entry['RedGames']+=1
    elif tc=='blue':entry['BlueGames']+=1
    entry['Minutes'] += float(row.get('Minutes') or 0)
    for stat in raw_stats:
        entry['Totals'][stat] += float(row.get(stat) or 0)
    if result=='win':
        entry['Wins'] += 1
        if tc==winner_color:
            if winner_color=='red': entry['RedWins']+=1
            else:                   entry['BlueWins']+=1
    else:
        entry['Losses'] += 1

def compute_derived(entry):
    dv = {}
    # existing per-unit derived stats
    for label,(num_key,den_key) in derived_stats.items():
        num = entry['Totals'].get(num_key,entry.get(num_key,0))
        den = entry['Totals'].get(den_key,entry.get(den_key,0))
        dv[label] = (num/den) if den else 0

    # new: per-8-minute stats using total / (minutes/8)
    minutes = entry['Minutes']
    if minutes:
        for stat in raw_stats:
            total = entry['Totals'].get(stat, 0)
            dv[f"{stat}/8Min"] = total / (minutes / 8)
    else:
        for stat in raw_stats:
            dv[f"{stat}/8Min"] = 0

    return dv

def build_record(entry):
    rec = {
        'Player':entry['Name'],'Minutes':entry['Minutes'],
        'Games':entry['Games'],'Wins':entry['Wins'],
        'Losses':entry['Losses'],'Win %':entry['Wins']/entry['Games'] if entry['Games'] else 0,
        'Red Games':entry['RedGames'],'Blue Games':entry['BlueGames'],
        'Red Wins':entry['RedWins'],'Blue Wins':entry['BlueWins'],
        'Red Win %':entry['RedWins']/entry['RedGames'] if entry['RedGames'] else 0,
        'Blue Win %':entry['BlueWins']/entry['BlueGames'] if entry['BlueGames'] else 0
    }
    for stat in raw_stats:
        rec[stat] = entry['Totals'][stat]
    rec.update(compute_derived(entry))
    return rec

if __name__=='__main__':
    if not os.path.isfile(INPUT_CSV):
        raise FileNotFoundError(f"{INPUT_CSV} not found")
    df = pd.read_csv(INPUT_CSV)
    df.dropna(subset=['matchId','Player','Team'],inplace=True)
    rows = df.to_dict('records')

    # Aggregate
    matches, overall, per_map, map_results = {}, {}, {}, {}
    for r in rows:
        matches.setdefault(r['matchId'], []).append(r)

    for players in matches.values():
        caps = {}
        for p in players:
            t = p['Team'].strip().lower()
            caps[t] = caps.get(t, 0) + int(p.get('Captures') or 0)
        if len(caps) != 2 or len(set(caps.values())) != 2:
            continue
        winner = max(caps, key=caps.get)
        for p in players:
            p['caps_for'] = int(p.get('Captures') or 0)
            opp = next(t for t in caps if t != p['Team'].strip().lower())
            p['caps_against'] = caps[opp]
        for p in players:
            key = p['Player'].strip().lower()
            overall.setdefault(key, new_entry(p['Player']))
            res = 'win' if p['Team'].strip().lower() == winner else 'loss'
            update_entry(overall[key], p, p['caps_for'], p['caps_against'], res, winner)

        m = players[0].get('mapName', '')
        if not m:
            continue
        per_map.setdefault(m, {'red_team': new_entry('Red'), 'blue_team': new_entry('Blue')})
        map_results.setdefault(m, {'Games': 0, 'RedWins': 0, 'BlueWins': 0})
        map_results[m]['Games']   += 1
        map_results[m]['RedWins'] += (1 if winner == 'red' else 0)
        map_results[m]['BlueWins']+= (1 if winner == 'blue' else 0)

        for p in players:
            k = p['Player'].strip().lower()
            per_map[m].setdefault(k, new_entry(p['Player']))
            res = 'win' if p['Team'].strip().lower() == winner else 'loss'
            update_entry(per_map[m][k], p, p['caps_for'], p['caps_against'], res, winner)
            team_entry = per_map[m]['red_team'] if p['Team'].strip().lower() == 'red' else per_map[m]['blue_team']
            update_entry(team_entry, p, p['caps_for'], p['caps_against'], res, winner)

    # Output folder
    base = 'Stats'
    os.makedirs(base, exist_ok=True)
    idxs = [
        int(m.group(1)) for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d))
        and (m := re.match(r'^Stats\((\d+)\)$', d))
    ]
    idx = max(idxs) + 1 if idxs else 1
    out = os.path.join(base, f"Stats({idx})")
    os.makedirs(out)

    # Build DataFrames
    overall_df = pd.DataFrame([build_record(e) for e in overall.values()])
    overall_df.sort_values('Minutes', ascending=False, inplace=True)

    mr_df = pd.DataFrame([{
        'Map': m,
        'Games': v['Games'],
        'RedWins': v['RedWins'],
        'BlueWins': v['BlueWins'],
        'Red Win %': v['RedWins']/v['Games'] if v['Games'] else 0,
        'Blue Win %': v['BlueWins']/v['Games'] if v['Games'] else 0
    } for m, v in map_results.items()])

    per_csvs = []
    for m, mp in per_map.items():
        dfm = pd.DataFrame([build_record(e) for e in mp.values()])
        dfm.sort_values('Minutes', ascending=False, inplace=True)
        safe = m.replace(' ', '_').replace('/', '_')[:31]
        fn = f"stats_{safe}.csv"
        dfm.to_csv(os.path.join(out, fn), index=False)
        per_csvs.append((fn, dfm))

    # Save standalone CSVs
    overall_df.to_csv(os.path.join(out, 'players_stats_overall.csv'), index=False)
    mr_df.to_csv(os.path.join(out, 'map_results.csv'), index=False)

    # Write Excel with formatted widths
    from openpyxl import Workbook
    excel = os.path.join(out, 'combined_stats.xlsx')
    with pd.ExcelWriter(excel, engine='openpyxl') as writer:
        overall_df.to_excel(writer, sheet_name='OverallPlayers', index=False)
        mr_df.to_excel(writer, sheet_name='MapResults', index=False)
        for fn, dfm in per_csvs:
            sheet = fn[:-4][:31]
            dfm.to_excel(writer, sheet_name=sheet, index=False)

        for sheet_name, ws in writer.sheets.items():
            if sheet_name == 'OverallPlayers':
                df_ref = overall_df
            elif sheet_name == 'MapResults':
                df_ref = mr_df
            else:
                df_ref = dict(per_csvs).get(f"{sheet_name}.csv")

            if df_ref is None:
                continue

            # Identify percent vs decimal
            percent_cols = [c for c in derived_stats if '%' in c] + ['Red Win %', 'Blue Win %']
            decimal_cols = (
                [c for c in derived_stats if '%' not in c]
              + ['Minutes']
              + [c for c in df_ref.columns if c.endswith('/8Min')]
            )

            # For each column, build its _display_ strings
            for idx_col, col in enumerate(df_ref.columns, start=1):
                # header
                candidate_widths = [len(col)]
                # format each cell for measurement
                for val in df_ref[col].fillna('').tolist():
                    if col in percent_cols:
                        s = f"{val:.2%}"
                    elif col in decimal_cols:
                        s = f"{val:.2f}"
                    else:
                        s = str(val)
                    candidate_widths.append(len(s))
                # take the max, add padding
                max_len = max(candidate_widths) + 2
                ws.column_dimensions[get_column_letter(idx_col)].width = max_len

                # apply the number_format
                if col in percent_cols:
                    fmt = '0.00%'
                elif col in decimal_cols:
                    fmt = '0.00'
                else:
                    fmt = None

                if fmt:
                    for cell in ws[get_column_letter(idx_col)]:
                        cell.number_format = fmt

            ws.freeze_panes = 'B2'

    print(f"Generated sorted stats and Excel workbook in {out}")
